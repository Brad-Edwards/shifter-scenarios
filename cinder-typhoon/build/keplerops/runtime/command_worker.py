"""Trusted wrapper for one bounded Build Operations command job."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time


WORKSPACE = Path("/workspace")
CONFIG = Path("/run/fieldlink-ci")
PROOF = Path("/run/fieldkest-proof")
MAX_CAPTURE = 262_144
URLS = {
    "SOURCE": "https://source.keplerops.test",
    "PACKAGES": "https://packages.keplerops.test",
    "STAFF": "https://staff.keplerops.test",
    "CLOUD_POLICY": "https://cloud-api.keplerops.test",
    "BUILD_RECORDS": "https://cloud-api.keplerops.test",
    "MAINTENANCE": "https://workload.keplerops.test",
}
AUDIENCES = {
    "source": "source",
    "packages": "packages",
    "staff": "staff",
    "cloud-policy": "cloud-policy",
    "build-records": "build-records",
    "maintenance": "maintenance",
}


def decode_environment(name: str) -> object:
    raw = os.environ[name]
    return json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))


def write_runtime(tokens: dict[str, str]) -> None:
    CONFIG.mkdir(mode=0o550, parents=True, exist_ok=True)
    ca = base64.b64decode(os.environ["FIELDKEST_CA_B64"], validate=True)
    (CONFIG / "ca.crt").write_bytes(ca)
    lines = [f"FIELDLINK_{name}_URL={url}" for name, url in URLS.items()]
    (CONFIG / "connections.env").write_text("\n".join(lines) + "\n")
    for service, audience in AUDIENCES.items():
        token = tokens[audience]
        (CONFIG / f"{service}.curl").write_text(
            "cacert = \"/run/fieldlink-ci/ca.crt\"\n"
            "proto = \"=https\"\n"
            f"header = \"Authorization: Bearer {token}\"\n"
        )
    os.chmod(CONFIG / "ca.crt", 0o440)
    os.chmod(CONFIG / "connections.env", 0o440)
    for path in CONFIG.glob("*.curl"):
        os.chmod(path, 0o440)
    os.chown(CONFIG, 0, 2100)
    for path in CONFIG.iterdir():
        os.chown(path, 0, 2100)


def saved_files() -> list[dict[str, object]]:
    result = []
    for root, directories, files in os.walk(WORKSPACE, followlinks=False):
        directories[:] = [name for name in directories if not (Path(root) / name).is_symlink()]
        for name in files:
            path = Path(root) / name
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(WORKSPACE).as_posix()
            payload = path.read_bytes()
            result.append({"path": relative, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
    return sorted(result, key=lambda item: str(item["path"]))


def main() -> None:
    argv = decode_environment("FIELDKEST_COMMAND_B64")
    tokens = decode_environment("FIELDKEST_TOKENS_B64")
    if (not isinstance(argv, list) or not argv or len(argv) > 64 or
            not all(isinstance(item, str) and item and len(item.encode()) <= 16_384 for item in argv)):
        raise SystemExit("invalid command")
    if not isinstance(tokens, dict) or set(tokens) != set(AUDIENCES.values()):
        raise SystemExit("invalid worker credentials")
    PROOF.mkdir(mode=0o700, parents=True, exist_ok=True)
    WORKSPACE.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chown(WORKSPACE, 2100, 2100)
    for network in ("10.77.50.0/24", "10.77.51.0/24", "10.77.52.0/24", "10.77.60.0/24"):
        subprocess.run(["ip", "route", "replace", network, "via", "10.77.53.254"], check=True)
    write_runtime(tokens)
    stdout_path = PROOF / "stdout"
    stderr_path = PROOF / "stderr"
    trace_path = PROOF / "trace"
    started = time.monotonic()
    timed_out = False
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            ["strace", "-f", "-qq", "-s", "256", "-e", "trace=openat,execve", "-u", "fieldkest-worker", "-o", str(trace_path), "--", *argv],
            cwd=WORKSPACE,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        try:
            returncode = process.wait(timeout=int(os.environ.get("FIELDKEST_TIMEOUT", "20")))
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            returncode = process.wait(timeout=5)
    trace = trace_path.read_text(errors="replace")[:1_048_576]
    opened = sorted(set(re.findall(r'openat\([^,]+, "([^"]+)"', trace)))
    opened = [path for path in opened if path.startswith("/srv/fieldlink-ci/") or path.startswith("/workspace/")]
    stdout_bytes = stdout_path.read_bytes()[:MAX_CAPTURE]
    stderr_bytes = stderr_path.read_bytes()[:MAX_CAPTURE]
    result = {
        "schema": "fieldkest.runner-proof/v1",
        "run_id": os.environ["FIELDKEST_RUN_ID"],
        "lease_id": os.environ["FIELDKEST_LEASE_ID"],
        "process_identity": "fieldkest-worker",
        "argv": argv,
        "exit_status": returncode,
        "timed_out": timed_out,
        "duration_milliseconds": int((time.monotonic() - started) * 1000),
        "stdout": stdout_bytes.decode("utf-8", errors="replace"),
        "stderr": stderr_bytes.decode("utf-8", errors="replace"),
        "stdout_truncated": stdout_path.stat().st_size > MAX_CAPTURE,
        "stderr_truncated": stderr_path.stat().st_size > MAX_CAPTURE,
        "opened_paths": opened,
        "saved_files": saved_files(),
        "child_processes_terminated": True,
    }
    serialized = json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
    (PROOF / "result.json").write_text(serialized)
    os.chmod(PROOF / "result.json", 0o600)
    print(serialized, end="", flush=True)


if __name__ == "__main__":
    main()
