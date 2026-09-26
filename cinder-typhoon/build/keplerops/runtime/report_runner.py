"""Trusted controller for isolated FieldKest report-provider workers."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import socketserver
import subprocess
import sys
import threading
import uuid


SOCKET = Path("/run/fieldkest-runner/runner.sock")
WORKER_IMAGE = os.environ["FIELDKEST_WORKER_IMAGE"]
NODE_WORKER_IMAGE = os.environ["FIELDKEST_NODE_WORKER_IMAGE"]
COMMAND_WORKER_IMAGE = os.environ["FIELDKEST_COMMAND_WORKER_IMAGE"]
MAX_REQUEST = 800_000
ACTIVE_COMMANDS: dict[str, str] = {}
ACTIVE_LOCK = threading.RLock()
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
const vm = require('node:vm');
let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => raw += chunk);
process.stdin.on('end', () => {
  try {
    const request = JSON.parse(raw);
    const sandbox = {exports: {}};
    vm.createContext(sandbox, {codeGeneration: {strings: false, wasm: false}});
    new vm.Script(request.source, {filename: 'package/index.js'}).runInContext(sandbox, {timeout: 1000});
    if (typeof sandbox.exports.consume !== 'function') throw new Error('consume export required');
    const output = sandbox.exports.consume(request.input);
    process.stdout.write(JSON.stringify({ok: true, output}) + '\n');
  } catch (error) {
    process.stdout.write(JSON.stringify({ok: false, error: 'consumer_failed'}) + '\n');
  }
});
"""
WORKLOAD_WRAPPER = r"""
import base64, json, os, sys
request = json.loads(base64.urlsafe_b64decode(sys.argv[1] + '=' * (-len(sys.argv[1]) % 4)))
profile = request['profile']
identity = 'svc-support-export' if profile == 'support-export' else 'svc-fieldlink-maintenance'
output = {
  'runtime_identity': identity,
  'assignment': request['assignment'],
  'marker': request['marker'],
  'container_process': os.getpid(),
  'container_network': 'none',
  'execution_backend': 'isolated-container',
}
sys.stdout.write(json.dumps(output, sort_keys=True, separators=(',', ':')) + '\n')
"""
COMPLETION_WRAPPER = r"""
import hashlib, json, os
from pathlib import Path
request = json.loads(os.environ['FIELDKEST_COMPLETION_REQUEST'])
if request != {'handover_id': 'HANDOVER-COMP-2841', 'script': 'read_assigned_handover'}:
    raise SystemExit(64)
path = Path('/handover/HANDOVER-COMP-2841.json')
raw = path.read_bytes()
handover = json.loads(raw)
if handover.get('handover_id') != request['handover_id']:
    raise SystemExit(65)
result = {
  'runtime_identity': 'svc-assistant-completion',
  'handover': handover,
  'handover_sha256': hashlib.sha256(raw).hexdigest(),
  'container_process': os.getpid(),
  'container_network': 'none',
  'execution_backend': 'isolated-container',
  'destination_read': True,
}
print(json.dumps(result, sort_keys=True, separators=(',', ':')))
"""


def encoded_environment(value: object) -> str:
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")


def run_command(request: dict[str, object]) -> dict[str, object]:
    run_id = str(request["run_id"])
    lease_id = str(request["lease_id"])
    name = "fieldkest-command-" + run_id.lower().replace("_", "-")
    ca_b64 = base64.b64encode(Path("/run/fieldkest-auth/ca.crt").read_bytes()).decode()
    create = [
        "docker", "create", "--name", name,
        "--network", "cinder-keplerops-jobs",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m,mode=1777",
        "--tmpfs", "/run/fieldlink-ci:rw,noexec,nosuid,nodev,size=2m,mode=0750",
        "--tmpfs", "/run/fieldkest-proof:rw,noexec,nosuid,nodev,size=4m,mode=0700",
        "--mount", "type=volume,src=cinder-keplerops-ci-rowan-workspace,dst=/workspace",
        "--memory", "256m", "--memory-swap", "256m", "--pids-limit", "64", "--cpus", "1.0",
        "--cap-drop", "ALL", "--cap-add", "CHOWN", "--cap-add", "NET_ADMIN", "--cap-add", "SETUID", "--cap-add", "SETGID", "--cap-add", "SYS_PTRACE",
        "--security-opt", "no-new-privileges:true",
        "--add-host", "source.keplerops.test:10.77.51.20",
        "--add-host", "packages.keplerops.test:10.77.51.30",
        "--add-host", "staff.keplerops.test:10.77.50.30",
        "--add-host", "cert.keplerops.test:10.77.50.50",
        "--add-host", "cloud-api.keplerops.test:10.77.52.20",
        "--add-host", "workload.keplerops.test:10.77.52.30",
        "--env", f"FIELDKEST_RUN_ID={run_id}",
        "--env", f"FIELDKEST_LEASE_ID={lease_id}",
        "--env", "FIELDKEST_TIMEOUT=20",
        "--env", f"FIELDKEST_CA_B64={ca_b64}",
        "--env", f"FIELDKEST_COMMAND_B64={encoded_environment(request['argv'])}",
        "--env", f"FIELDKEST_TOKENS_B64={encoded_environment(request['tokens'])}",
        COMMAND_WORKER_IMAGE,
    ]
    subprocess.run(["docker", "rm", "--force", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    created = subprocess.run(create, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False, timeout=10)
    if created.returncode:
        return {"ok": False, "error": "worker_create_failed"}
    with ACTIVE_LOCK:
        ACTIVE_COMMANDS[run_id] = name
    try:
        started = subprocess.run(["docker", "start", name], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False, timeout=10)
        if started.returncode:
            return {"ok": False, "error": "worker_start_failed"}
        try:
            waited = subprocess.run(["docker", "wait", name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "stop", "--time", "1", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            return {"ok": False, "error": "worker_timeout"}
        logs_result = subprocess.run(
            ["docker", "logs", name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False, timeout=5,
        )
        lines = logs_result.stdout.splitlines()
        if waited.stdout.strip() not in {b"0"} or logs_result.returncode or len(lines) != 1 or len(lines[0]) > 1_000_000:
            logs = logs_result.stdout.decode(errors="replace")[-4096:]
            print(f"command worker {run_id} exited without proof: {logs}", file=sys.stderr, flush=True)
            return {"ok": False, "error": "worker_cancelled" if waited.stdout.strip() in {b"137", b"143"} else "worker_proof_missing"}
        result = json.loads(lines[0])
        return {"ok": True, "result": result}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {"ok": False, "error": "worker_failed"}
    finally:
        with ACTIVE_LOCK:
            ACTIVE_COMMANDS.pop(run_id, None)
        subprocess.run(["docker", "rm", "--force", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def cancel_command(run_id: str) -> dict[str, object]:
    with ACTIVE_LOCK:
        name = ACTIVE_COMMANDS.get(run_id)
    if name is None:
        return {"ok": False, "error": "worker_not_active"}
    stopped = subprocess.run(
        ["docker", "stop", "--time", "1", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=5
    )
    return {"ok": stopped.returncode == 0, "state": "cancelled" if stopped.returncode == 0 else "cancel_failed"}


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline(MAX_REQUEST + 1)
        if len(raw) > MAX_REQUEST or not raw.endswith(b"\n"):
            self.wfile.write(b'{"ok":false,"error":"invalid_runner_request"}\n')
            return
        try:
            request = json.loads(raw)
            if (set(request) == {"kind", "run_id"} and request["kind"] == "command-cancel"
                    and isinstance(request["run_id"], str)):
                self.wfile.write(json.dumps(cancel_command(request["run_id"]), separators=(",", ":")).encode() + b"\n")
                return
            if (set(request) == {"kind", "run_id", "lease_id", "argv", "tokens"}
                    and request["kind"] == "command"
                    and all(isinstance(request[key], str) and request[key] for key in ("run_id", "lease_id"))
                    and isinstance(request["argv"], list) and request["argv"]
                    and all(isinstance(item, str) and item for item in request["argv"])
                    and isinstance(request["tokens"], dict)):
                self.wfile.write(json.dumps(run_command(request), separators=(",", ":")).encode() + b"\n")
                return
            if (set(request) == {"kind", "run_id", "profile", "assignment", "marker"}
                    and request["kind"] == "workload"
                    and isinstance(request["run_id"], str)
                    and request["profile"] in {"support-export", "maintenance"}
                    and isinstance(request["assignment"], str)
                    and isinstance(request["marker"], bool)):
                payload = encoded_environment(request)
                name = "fieldkest-workload-" + request["run_id"].lower().replace("_", "-")
                command = [
                    "docker", "run", "--rm", "--name", name, "--network", "none",
                    "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m",
                    "--memory", "128m", "--memory-swap", "128m", "--pids-limit", "32", "--cpus", "0.5",
                    "--user", "65534:65534", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                    "--entrypoint", "/usr/bin/python3", COMMAND_WORKER_IMAGE, "-I", "-c", WORKLOAD_WRAPPER, payload,
                ]
                result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=15)
                lines = result.stdout.splitlines()
                response = {"ok": False, "error": "workload_failed"}
                if result.returncode == 0 and len(lines) == 1:
                    response = {"ok": True, "result": json.loads(lines[0])}
                self.wfile.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")
                return
            if (set(request) == {"kind", "run_id", "handover_id", "script"}
                    and request["kind"] == "completion"
                    and isinstance(request["run_id"], str)
                    and request["handover_id"] == "HANDOVER-COMP-2841"
                    and request["script"] == "read_assigned_handover"):
                name = "fieldkest-completion-" + request["run_id"].lower().replace("_", "-")
                command = [
                    "docker", "run", "--rm", "--name", name, "--network", "none",
                    "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m",
                    "--mount", "type=volume,src=cinder-keplerops-assistant-handover,dst=/handover,readonly",
                    "--memory", "128m", "--memory-swap", "128m", "--pids-limit", "32", "--cpus", "0.5",
                    "--user", "2100:2100", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                    "--env", "FIELDKEST_COMPLETION_REQUEST=" + json.dumps({
                        "handover_id": request["handover_id"], "script": request["script"]
                    }, separators=(",", ":")),
                    "--entrypoint", "/usr/bin/python3", COMMAND_WORKER_IMAGE, "-I", "-c", COMPLETION_WRAPPER,
                ]
                try:
                    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=15)
                except subprocess.TimeoutExpired:
                    subprocess.run(["docker", "rm", "--force", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                    self.wfile.write(b'{"ok":false,"error":"completion_timeout"}\n')
                    return
                lines = result.stdout.splitlines()
                response = {"ok": False, "error": "completion_failed"}
                if result.returncode == 0 and len(lines) == 1:
                    response = {"ok": True, "result": json.loads(lines[0])}
                self.wfile.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")
                return
            if set(request) == {"source", "fixture"} and isinstance(request["source"], str) and isinstance(request["fixture"], dict):
                kind = "report"
            elif set(request) == {"kind", "source", "input"} and request["kind"] == "node-package" and isinstance(request["source"], str) and isinstance(request["input"], dict):
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
            entrypoint = ["--entrypoint", "/usr/local/bin/node", image, "--disallow-code-generation-from-strings", "-e", NODE_WRAPPER]
            input_bytes = json.dumps({"source": request["source"], "input": request["input"]}, separators=(",", ":")).encode()
        command = [
            "docker", "run", "--rm", "-i", "--name", name,
            "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m",
            "--memory", "128m", "--memory-swap", "128m", "--pids-limit", "32", "--cpus", "0.5",
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
