#!/usr/bin/env python3
"""Run one real Chromium getUserMedia/WebRTC smoke without test frameworks."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from typing import Any


class DevToolsSocket:
    """Small RFC 6455 client sufficient for local Chrome DevTools JSON messages."""

    def __init__(self, url: str) -> None:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "ws" or parsed.hostname is None or parsed.port is None:
            raise ValueError("expected a local ws:// DevTools URL")
        self.connection = socket.create_connection((parsed.hostname, parsed.port), 5)
        self.connection.settimeout(15)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        self.connection.sendall(request)
        response = self._until(b"\r\n\r\n")
        if not response.startswith(b"HTTP/1.1 101"):
            raise RuntimeError("Chrome rejected the DevTools WebSocket handshake")
        expected = base64.b64encode(
            hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii"),
                usedforsecurity=False,
            ).digest()
        )
        if b"sec-websocket-accept: " + expected.lower() not in response.lower():
            raise RuntimeError("Chrome returned an invalid WebSocket accept digest")
        self.next_id = 1

    def command(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        command_id = self.next_id
        self.next_id += 1
        self._send(1, json.dumps({"id": command_id, "method": method, "params": params}))
        while True:
            opcode, payload = self._receive()
            if opcode == 9:
                self._send(10, payload)
                continue
            if opcode != 1:
                continue
            message = json.loads(payload)
            if message.get("id") == command_id:
                if "error" in message:
                    raise RuntimeError(str(message["error"]))
                return message.get("result", {})

    def close(self) -> None:
        try:
            self._send(8, b"")
        finally:
            self.connection.close()

    def _send(self, opcode: int, value: str | bytes) -> None:
        payload = value.encode("utf-8") if isinstance(value, str) else value
        mask = os.urandom(4)
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65_536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask)
        masked = bytes(item ^ mask[index % 4] for index, item in enumerate(payload))
        self.connection.sendall(header + masked)

    def _receive(self) -> tuple[int, bytes]:
        first, second = self._exact(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._exact(8))[0]
        mask = self._exact(4) if second & 0x80 else None
        payload = self._exact(length)
        if mask is not None:
            payload = bytes(
                item ^ mask[index % 4] for index, item in enumerate(payload)
            )
        return opcode, payload

    def _until(self, marker: bytes) -> bytes:
        captured = bytearray()
        while marker not in captured:
            captured.extend(self.connection.recv(4096))
        return bytes(captured)

    def _exact(self, size: int) -> bytes:
        captured = bytearray()
        while len(captured) < size:
            block = self.connection.recv(size - len(captured))
            if not block:
                raise ConnectionError("Chrome closed the DevTools connection")
            captured.extend(block)
        return bytes(captured)


def evaluate(channel: DevToolsSocket, expression: str) -> Any:
    result = channel.command(
        "Runtime.evaluate",
        {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True,
            "userGesture": True,
        },
    )
    if "exceptionDetails" in result:
        raise RuntimeError(str(result["exceptionDetails"]))
    return result.get("result", {}).get("value")


def browser_smoke(base_url: str, init_token: str) -> dict[str, Any]:
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if chrome is None:
        raise RuntimeError("Chrome/Chromium is not installed")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        debug_port = reservation.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="keplerops-camera-chrome-") as profile:
        process = subprocess.Popen(
            [
                chrome,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--use-fake-device-for-media-stream",
                "--use-fake-ui-for-media-stream",
                "--autoplay-policy=no-user-gesture-required",
                f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={profile}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        channel: DevToolsSocket | None = None
        try:
            version_url = f"http://127.0.0.1:{debug_port}/json/version"
            deadline = time.monotonic() + 10
            while True:
                try:
                    with urllib.request.urlopen(version_url, timeout=1):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Chrome DevTools did not start")
                    time.sleep(0.1)
            target_request = urllib.request.Request(
                f"http://127.0.0.1:{debug_port}/json/new?"
                + urllib.parse.quote("about:blank", safe=""),
                method="PUT",
            )
            with urllib.request.urlopen(target_request, timeout=5) as response:
                target = json.load(response)
            channel = DevToolsSocket(target["webSocketDebuggerUrl"])
            channel.command("Page.enable", {})
            channel.command("Runtime.enable", {})
            channel.command("Page.navigate", {"url": base_url})
            time.sleep(0.5)
            evaluate(
                channel,
                "new Promise((resolve,reject)=>{const end=Date.now()+10000;"
                "const wait=setInterval(()=>{if(document.readyState==='complete'&&"
                "window.kepleropsCamera){clearInterval(wait);resolve(true);}"
                "else if(Date.now()>end){clearInterval(wait);reject(new Error('page timeout'));}"
                "},50);})",
            )
            evaluate(
                channel,
                "document.getElementById('init-token').value="
                + json.dumps(init_token)
                + "; window.kepleropsCamera.start()",
            )
            connected = evaluate(
                channel,
                "new Promise((resolve)=>{const end=Date.now()+15000;"
                "const wait=setInterval(()=>{const s=window.kepleropsCamera.getState();"
                "if(s==='connected'||s==='error'||Date.now()>end){clearInterval(wait);"
                "resolve({state:s,text:document.getElementById('status').textContent});}"
                "},100);})",
            )
            if connected["state"] != "connected":
                raise RuntimeError(f"WebRTC did not connect: {connected}")
            evaluate(channel, "window.kepleropsCamera.captureControl()")
            captured = evaluate(
                channel,
                "new Promise((resolve)=>{const end=Date.now()+15000;"
                "const wait=setInterval(()=>{const s=window.kepleropsCamera.getState();"
                "if(s==='captured'||s==='error'||Date.now()>end){clearInterval(wait);"
                "resolve({state:s,text:document.getElementById('status').textContent});}"
                "},100);})",
            )
            evaluate(channel, "window.kepleropsCamera.stop(false)")
            return {"connected": connected, "capture": captured}
        finally:
            if channel is not None:
                channel.close()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8480")
    parser.add_argument("--init-token", default="keplerops-platform-camera-session")
    arguments = parser.parse_args()
    print(json.dumps(browser_smoke(arguments.base_url, arguments.init_token), sort_keys=True))


if __name__ == "__main__":
    main()
