"""Trusted controller for isolated FieldKest report-provider workers."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import socketserver
import subprocess
import uuid


SOCKET = Path("/run/fieldkest-runner/runner.sock")
WORKER_IMAGE = os.environ["FIELDKEST_WORKER_IMAGE"]
NODE_WORKER_IMAGE = os.environ["FIELDKEST_NODE_WORKER_IMAGE"]
MAX_REQUEST = 800_000
WRAPPER = r"""
import base64, json, sys
payload = json.loads(base64.urlsafe_b64decode(sys.argv[1] + '=' * (-len(sys.argv[1]) % 4)))
namespace = {'__builtins__': __builtins__}
exec(payload['source'], namespace, namespace)
function = namespace.get('render_report')
if not callable(function):
    raise TypeError('render_report function required')
result = function(payload['fixture'])
sys.stdout.write(json.dumps({'ok': True, 'output': result}, sort_keys=True, separators=(',', ':')) + '\n')
"""
NODE_WRAPPER = r"""
const fs = require('node:fs');
const path = require('node:path');
const child = require('node:child_process');
let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => raw += chunk);
process.stdin.on('end', async () => {
  try {
    const request = JSON.parse(raw);
    const work = fs.mkdtempSync('/tmp/fieldlink-consumer-');
    const archive = path.join(work, 'package.tgz');
    fs.writeFileSync(archive, Buffer.from(request.archive_base64, 'base64'));
    child.execFileSync('/usr/local/bin/npm', [
      'install', '--offline', '--no-audit', '--no-fund', '--no-package-lock',
      '--prefix', work, archive
    ], {
      env: {...process.env, HOME: work, npm_config_cache: path.join(work, 'cache')},
      timeout: 7000, stdio: 'pipe'
    });
    const root = path.join(work, 'node_modules', '@keplerops', 'fieldlink-connector');
    const consumer = require(root);
    const metadata = require(path.join(root, 'package.json'));
    if (typeof consumer.consume !== 'function') throw new Error('consume export required');
    const output = await consumer.consume(request.input);
    process.stdout.write(JSON.stringify({ok: true, output,
      package: {name: metadata.name, version: metadata.version}}) + '\n');
  } catch (error) {
    process.stdout.write(JSON.stringify({ok: false, error: 'consumer_failed',
      details: {message: String(error.message).slice(0, 1024),
        stderr: error.stderr ? error.stderr.toString().slice(-4096) : ''}}) + '\n');
  }
});
"""
class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline(MAX_REQUEST + 1)
        if len(raw) > MAX_REQUEST or not raw.endswith(b"\n"):
            self.wfile.write(b'{"ok":false,"error":"invalid_runner_request"}\n')
            return
        try:
            request = json.loads(raw)
            if set(request) == {"source", "fixture"} and isinstance(request["source"], str) and isinstance(request["fixture"], dict):
                kind = "report"
            elif set(request) == {"kind", "archive_base64", "input"} and request["kind"] == "node-package" and isinstance(request["archive_base64"], str) and isinstance(request["input"], dict):
                kind = "node-package"
            else:
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            self.wfile.write(b'{"ok":false,"error":"invalid_runner_request"}\n')
            return
        if kind == "report":
            payload = base64.urlsafe_b64encode(json.dumps(request, separators=(",", ":")).encode()).decode().rstrip("=")
            name = "fieldkest-report-" + uuid.uuid4().hex[:16]
            image = WORKER_IMAGE
            entrypoint = ["--entrypoint", "/usr/local/bin/python3", image, "-I", "-c", WRAPPER, payload]
            input_bytes = None
        else:
            name = "fieldkest-consumer-" + uuid.uuid4().hex[:16]
            image = NODE_WORKER_IMAGE
            entrypoint = ["--entrypoint", "/usr/local/bin/node", image, "-e", NODE_WRAPPER]
            input_bytes = json.dumps({"archive_base64": request["archive_base64"], "input": request["input"]}, separators=(",", ":")).encode()
        command = [
            "docker", "run", "--rm", "-i", "--name", name,
            "--network", "none", "--read-only", "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777" if kind == "node-package" else "/tmp:rw,noexec,nosuid,nodev,size=8m,mode=1777",
            "--memory", "256m" if kind == "node-package" else "128m",
            "--memory-swap", "256m" if kind == "node-package" else "128m", "--pids-limit", "32", "--cpus", "0.5",
            "--user", "65534:65534", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            *entrypoint,
        ]
        try:
            result = subprocess.run(command, input=input_bytes, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "--force", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            self.wfile.write(b'{"ok":false,"error":"worker_timeout"}\n')
            return
        lines = result.stdout.splitlines()
        if result.returncode or len(lines) != 1 or len(lines[0]) > 1_000_000:
            self.wfile.write(b'{"ok":false,"error":"worker_failed"}\n')
            return
        try:
            response = json.loads(lines[0])
        except json.JSONDecodeError:
            response = {"ok": False, "error": "worker_invalid_response"}
        self.wfile.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


def main() -> None:
    SOCKET.parent.mkdir(parents=True, exist_ok=True)
    SOCKET.unlink(missing_ok=True)
    with Server(str(SOCKET), Handler) as server:
        SOCKET.chmod(0o666)
        server.serve_forever()


if __name__ == "__main__":
    main()
