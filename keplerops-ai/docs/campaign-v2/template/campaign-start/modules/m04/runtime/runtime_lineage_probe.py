from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import ssl
import urllib.parse

from fastapi import FastAPI, HTTPException
import websockets


app = FastAPI(title="Orion runtime lineage probe")
K8S_URL = os.getenv("K8S_API_URL", "https://192.168.78.30:6443").rstrip("/")
TOKEN_FILE = Path(os.getenv("K8S_TOKEN_FILE", "/var/run/keplerops/k3s-token"))
CA_FILE = Path(os.getenv("K8S_CA_FILE", "/var/run/keplerops/k3s-ca.crt"))


async def process_command(namespace: str, pod: str, container: str) -> str:
    query = urllib.parse.urlencode([
        ("container", container), ("command", "/bin/sh"), ("command", "-c"),
        ("command", "tr '\\0' ' ' </proc/1/cmdline"),
        ("stdin", "false"), ("stdout", "true"), ("stderr", "true"), ("tty", "false"),
    ])
    websocket_url = K8S_URL.replace("https://", "wss://").replace("http://", "ws://")
    url = f"{websocket_url}/api/v1/namespaces/{urllib.parse.quote(namespace)}/pods/{urllib.parse.quote(pod)}/exec?{query}"
    context = ssl.create_default_context(cafile=str(CA_FILE))
    stdout, stderr = bytearray(), bytearray()
    async with websockets.connect(
        url, ssl=context, subprotocols=["v4.channel.k8s.io"],
        additional_headers={"Authorization": f"Bearer {TOKEN_FILE.read_text().strip()}"},
        open_timeout=20, close_timeout=5,
    ) as socket:
        while True:
            try:
                message = await asyncio.wait_for(socket.recv(), timeout=20)
            except websockets.ConnectionClosed:
                break
            data = message.encode() if isinstance(message, str) else message
            if not data:
                continue
            if data[0] == 1:
                stdout.extend(data[1:])
            elif data[0] == 2:
                stderr.extend(data[1:])
            elif data[0] == 3:
                status = json.loads(data[1:] or b"{}")
                if status.get("status") not in {None, "Success"}:
                    raise RuntimeError(status.get("message") or "Kubernetes exec failed")
    if stderr or not stdout.strip():
        raise RuntimeError(stderr.decode(errors="replace") or "empty /proc/1/cmdline")
    return stdout.decode(errors="strict").strip()


@app.post("/v1/process")
async def inspect_process(request: dict[str, object]) -> dict[str, str]:
    if set(request) != {"namespace", "pod", "container"}:
        raise HTTPException(400, "exact namespace, pod, and container fields are required")
    namespace, pod, container = (str(request[name]) for name in ("namespace", "pod", "container"))
    if namespace != "orion-runtime" or not pod or not container:
        raise HTTPException(400, "runtime process selector is outside the Orion namespace")
    try:
        command = await process_command(namespace, pod, container)
    except Exception as exc:
        raise HTTPException(502, f"native Kubernetes process inspection failed: {exc}") from exc
    return {
        "namespace": namespace, "pod": pod, "container": container,
        "process_command": command,
        "process_command_sha256": hashlib.sha256(command.encode()).hexdigest(),
        "source": "kubernetes-pods-exec:/proc/1/cmdline",
    }
