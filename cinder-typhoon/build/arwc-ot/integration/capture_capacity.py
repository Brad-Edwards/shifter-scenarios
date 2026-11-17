"""Bounded host and native container measurements; no process arguments or secrets."""
import argparse
import datetime as dt
import json
import os
import pathlib
import socket
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


def cpu_ticks():
    values = [int(value) for value in pathlib.Path("/proc/stat").read_text().splitlines()[0].split()[1:9]]
    return sum(values), values[3] + values[4]


def main():
    if socket.gethostname() != "cinder-arwc-ot-compat-363":
        raise SystemExit("Use the approved development VM")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if not 10 <= args.seconds <= 3600:
        parser.error("Use a duration from 10 through 3600 seconds")
    directory = ROOT / ".operator/capacity"
    directory.mkdir(mode=0o700, exist_ok=True)
    start = dt.datetime.now(dt.timezone.utc)
    path = directory / (start.strftime("%Y%m%dT%H%M%SZ") + ".jsonl")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    previous = cpu_ticks()
    deadline = time.monotonic() + args.seconds
    with os.fdopen(descriptor, "w") as output:
        while time.monotonic() < deadline:
            started = time.monotonic()
            record = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "label": args.label,
                      "logical_cpus": os.cpu_count(), "load_average": os.getloadavg()}
            current = cpu_ticks()
            total, idle = current[0] - previous[0], current[1] - previous[1]
            record["host_cpu_percent"] = 100 * (total-idle)/total if total else None
            previous = current
            memory = {name: int(value.split()[0])*1024 for name, value in
                      (line.split(":", 1) for line in pathlib.Path("/proc/meminfo").read_text().splitlines())}
            record["memory_total_bytes"] = memory["MemTotal"]
            record["memory_available_bytes"] = memory["MemAvailable"]
            disk = os.statvfs(ROOT)
            record["disk_available_bytes"] = disk.f_bavail * disk.f_frsize
            try:
                stats = subprocess.run(["sudo", "-n", "docker", "stats", "--no-stream", "--format", "{{json .}}"],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=True)
                record["containers"] = [json.loads(line) for line in stats.stdout.splitlines()]
                size = subprocess.run(["sudo", "-n", "docker", "exec", "arwc-ot-compat-postgres-1", "psql",
                    "--no-psqlrc", "-U", "historian", "-d", "historian", "-At", "-c",
                    "SELECT pg_database_size(current_database())"],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, check=True)
                record["historian_database_bytes"] = int(size.stdout.strip())
            except (subprocess.SubprocessError, OSError, ValueError) as error:
                record["measurement_error"] = type(error).__name__
            output.write(json.dumps(record)+"\n")
            output.flush()
            time.sleep(max(0, min(5-(time.monotonic()-started), deadline-time.monotonic())))
    print("Capacity measurements saved to " + str(path))


if __name__ == "__main__":
    main()
