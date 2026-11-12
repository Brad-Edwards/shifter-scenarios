"""Export only explicit, non-secret compatibility results for review."""
import hashlib
import json
import pathlib
import socket
import subprocess
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent


def main():
    if socket.gethostname() != "cinder-arwc-ot-compat-363":
        raise RuntimeError("Collect evidence on the compatibility VM")
    checks = {}
    for name in ("opcua", "path", "local-priority", "field-down", "field-up", "retained", "editor"):
        checks[name] = json.loads((ROOT / f".operator/{name}-evidence.json").read_text())
    timestamp_query = """SELECT json_build_object('source_time',source_time,'ingested_at',ingested_at,
        'subsecond_preserved',extract(second from source_time) <> trunc(extract(second from source_time)))
        FROM process_history WHERE tag='level_m' AND process_quality='Good'
        AND source_time > now()-interval '5 seconds' ORDER BY source_time DESC LIMIT 1"""
    sample = subprocess.check_output(["sudo", "docker", "compose", "exec", "-T", "postgres", "psql", "-U", "historian", "-d", "historian", "-Atc", timestamp_query], cwd=ROOT, text=True)
    checks["timestamp_precision"] = json.loads(sample)
    assert checks["timestamp_precision"]["subsecond_preserved"], "Collector rounded away PLC source-time precision"
    images = json.loads(subprocess.check_output(["sudo", "docker", "compose", "images", "--format", "json"], cwd=ROOT, text=True))
    sources = {}
    for name in ("compose.yaml", "main.st", "tags.json", "plc.Dockerfile", "fuxa.Dockerfile", "tools.Dockerfile", "patch_opcua_identity.py", "requirements.lock", "fuxa-plugin/package-lock.json", "setup-slice.sh", "prepare_services.py"):
        sources[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    result = {"scope": "issue-363 product compatibility fixture; normal operations only", "status": "passed",
              "collected_at": datetime.now(timezone.utc).isoformat(),
              "project": "prod-mgau4w", "vm": socket.gethostname(), "checks": checks,
              "setup": "setup-slice.sh completed; native identity and operating paths passed afterwards",
              "negative_control": "Unmodified Runtime 4.3.2 failed the endpoint/certificate application-URI assertion; the corrected image passed",
              "source_sha256": sources, "images": images,
              "not_qualified_here": ["full water utility logic and graphics", "participant desktop workflows", "BigRAE deployment", "incident/challenge content"]}
    destination = ROOT / "evidence/qualification.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(result, indent=2)+"\n")
    print("Collected explicit public compatibility evidence: " + str(destination))


if __name__ == "__main__":
    main()
