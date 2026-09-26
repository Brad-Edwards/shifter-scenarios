#!/usr/bin/env python3
"""Trusted controller for one-shot, container-isolated formatter workers."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socketserver
import subprocess
import uuid


SOCKET = Path("/run/cinder-runner/runner.sock")
WORKER_IMAGE = os.environ["CINDER_WORKER_IMAGE"]
MAX_REQUEST = 600_000
WRAPPER = r"""
const payload = JSON.parse(Buffer.from(process.argv[1], 'base64url').toString('utf8'));
for (const key of Object.keys(process.env)) delete process.env[key];
const originalWrite = process.stdout.write.bind(process.stdout);
process.stdout.write = () => true;
console.log = console.info = console.warn = console.error = () => {};
(async () => {
  const module = {exports: {}};
  const exports = module.exports;
  Function('exports', 'module', payload.source)(exports, module);
  if (!module.exports || typeof module.exports.formatDelivery !== 'function') throw new TypeError('formatDelivery export required');
  const output = await module.exports.formatDelivery(payload.input);
  originalWrite(JSON.stringify({ok: true, output}) + '\n');
})().catch((error) => originalWrite(JSON.stringify({ok: false, error: String(error && error.message || error)}) + '\n'));
"""


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline(MAX_REQUEST + 1)
        if len(raw) > MAX_REQUEST or not raw.endswith(b"\n"):
            self.wfile.write(b'{"ok":false,"error":"invalid_runner_request"}\n')
            return
        try:
            request = json.loads(raw)
            if set(request) != {"source", "input"} or not isinstance(request["source"], str) or not isinstance(request["input"], dict):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            self.wfile.write(b'{"ok":false,"error":"invalid_runner_request"}\n')
            return
        import base64

        payload = base64.urlsafe_b64encode(json.dumps(request, separators=(",", ":")).encode()).decode().rstrip("=")
        name = "cinder-formatter-" + uuid.uuid4().hex[:16]
        command = [
            "docker", "run", "--rm", "--name", name,
            "--network", "none", "--read-only",
            "--memory", "64m", "--memory-swap", "64m",
            "--pids-limit", "32", "--cpus", "1",
            "--user", "65534:65534", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--entrypoint", "/usr/local/bin/node", WORKER_IMAGE,
            "--max-old-space-size=32", "--input-type=commonjs", "-e", WRAPPER, payload,
        ]
        try:
            result = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "--force", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            self.wfile.write(b'{"ok":false,"error":"worker_timeout"}\n')
            return
        lines = result.stdout.splitlines()
        if result.returncode != 0 or len(lines) != 1 or len(lines[0]) > 1_000_000:
            self.wfile.write(b'{"ok":false,"error":"worker_failed"}\n')
            return
        try:
            response = json.loads(lines[0])
        except json.JSONDecodeError:
            response = {"ok": False, "error": "worker_invalid_response"}
        self.wfile.write((json.dumps(response, separators=(",", ":")) + "\n").encode())


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


def main() -> None:
    SOCKET.parent.mkdir(parents=True, exist_ok=True)
    if SOCKET.exists():
        SOCKET.unlink()
    with Server(str(SOCKET), Handler) as server:
        SOCKET.chmod(0o666)
        server.serve_forever()


if __name__ == "__main__":
    main()
