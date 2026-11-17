#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import tempfile
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import reporting_schedule


ROOT = pathlib.Path("/var/lib/arwc-reservoir")
STATE = ROOT / "state" / "reservoir.json"
AUDIT = ROOT / "audit" / "events.jsonl"
PROCESS_EVIDENCE = pathlib.Path("/run/arwc-process-evidence")
AUTHORITY_EVIDENCE = pathlib.Path("/run/arwc-control-authority")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_json(path: pathlib.Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def initialize() -> None:
    if not STATE.exists():
        atomic_json(STATE, {
            "reserve_ml": 12.4, "released_ml": 0.0,
            "reporting_handover_response": None,
        })
    AUDIT.touch(mode=0o600, exist_ok=True)
    os.chmod(AUDIT, 0o600)


def load_state() -> dict[str, object]:
    return json.loads(STATE.read_text(encoding="utf-8"))


def append_audit(action: str, result: dict[str, object], correlation: str) -> str:
    event = {
        "audit_id": correlation,
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tenant": "arwc", "principal": "reservoir-operator-principal",
        "action": action, "object": result.get("record_id"),
        "revision": result.get("revision"),
        "result_digest": hashlib.sha256(canonical(result)).hexdigest(),
    }
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return correlation


def valid_uuid(value: object) -> bool:
    try:
        return str(uuid.UUID(str(value))) == str(value)
    except (TypeError, ValueError):
        return False


def control_authority(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, str):
        return None
    digest = hashlib.sha256(raw.encode()).hexdigest()
    for identity, revision in (("CTRL-CLIENT-CRR-26", 1), ("CTRL-CLIENT-CRR-28", 4)):
        record = load_json(AUTHORITY_EVIDENCE / f"{identity}.json")
        if record is None:
            continue
        try:
            expires = datetime.fromisoformat(str(record["expires_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if (record.get("record_id") == identity and record.get("revision") == revision and
                record.get("outlet_group") == "OG-CRR-02" and
                record.get("project") == "CRR-CTRL-R21" and
                record.get("actions") == ["plan-execute", "readback"] and
                isinstance(record.get("token_sha256"), str) and
                hmac.compare_digest(digest, str(record["token_sha256"])) and
                datetime.now(timezone.utc) < expires):
            return record
    return None


def process_context() -> dict[str, dict[str, object]] | None:
    records = {
        "plan": load_json(PROCESS_EVIDENCE / "hmi" / "loss-plan.json"),
    }
    if any(value is None for value in records.values()):
        return None
    result = {key: value for key, value in records.items() if value is not None}
    if (result["plan"].get("record_id") != "PLAN-CRR-LOSS-1000" or
            result["plan"].get("mode") != "MODE-CRR-17" or
            result["plan"].get("released_volume_ml") != 1.0 or
            result["plan"].get("reserve_after_ml") != 11.4):
        return None
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Reservoir-Controller/1.0"
    sys_version = ""

    def log_message(self, message: str, *args: object) -> None:
        print(f"{self.client_address[0]} {message % args}", flush=True)

    def send_json(self, status: int, body: dict[str, object]) -> None:
        encoded = canonical(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def body(self) -> dict[str, object] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 65536:
                raise ValueError
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (ValueError, json.JSONDecodeError):
            self.send_json(409, {"error": "invalid reservoir request"})
            return None

    def authorized(self) -> bool:
        if (self.headers.get("X-ARWC-Internal") != "instruments-reporting" or
                self.headers.get("X-ARWC-Tenant") != "arwc" or
                self.client_address[0] != "10.77.64.40"):
            self.send_json(403, {"error": "independent instrument service context required"})
            return False
        return True

    def do_POST(self) -> None:
        if not self.authorized():
            return
        request = self.body()
        if request is None:
            return
        path = urlsplit(self.path).path
        if path == "/internal/control-handovers":
            self.w34_handover(request)
        else:
            self.send_json(404, {"error": "record not found"})

    def w34_handover(self, request: dict[str, object]) -> None:
        correlation = request.get("correlation"); binding = request.get("request"); supplied = request.get("evaluation")
        schedule = binding.get("schedule") if isinstance(binding, dict) else None
        evaluated = None if not isinstance(schedule, dict) else reporting_schedule.evaluate_schedule(
            schedule.get("reservoir_release_m3s"), schedule.get("alternate_supply_m3s"), schedule.get("demand_m3s"))
        if (set(request) != {"correlation", "request", "evaluation"} or not valid_uuid(correlation) or
                not isinstance(binding, dict) or evaluated is None or supplied != evaluated):
            self.send_json(409, {"error": "reservoir reporting request is not bound"}); return
        authority = control_authority(binding.get("control_client")); context = process_context()
        if authority is None:
            self.send_json(403, {"error": "current scoped control authority required"}); return
        if (context is None or binding.get("checkpoint") != "REH-REPORT-34" or
                binding.get("decision") != "ALLOC-EXPAND-R2" or binding.get("view") != "VIEW-CRR-34" or
                evaluated.get("reservoir_volume_ml") != 0.81 or evaluated.get("final_buffer_m3") != 180.0):
            self.send_json(409, {"error": "current reporting checkpoint bindings do not agree"}); return
        state = load_state(); existing = state.get("reporting_handover_response")
        if isinstance(existing, dict):
            if existing.get("audit_id") == correlation: self.send_json(201, existing)
            else: self.send_json(409, {"error": "reporting handover already recorded under another correlation"})
            return
        record = {"record_id": "RES-REPORT-CRR-34", "revision": 1,
                  "request_correlation": correlation, "authority": authority["record_id"],
                  "checkpoint": "REH-REPORT-34", "release_volume_ml": 0.81,
                  "reserve_before_ml": 12.4, "reserve_after_ml": 11.59,
                  "live_reserve_ml": state["reserve_ml"], "live_released_ml": state["released_ml"],
                  "live_state_changed": False}
        response = {"audit_id": append_audit("reporting-handover-created", record, str(correlation)),
                    "record": record}
        state["reporting_handover_response"] = response; atomic_json(STATE, state)
        atomic_json(ROOT / "results" / "RES-REPORT-CRR-34.json", record); self.send_json(201, response)


def main() -> None:
    initialize()
    server = ThreadingHTTPServer(("0.0.0.0", 443), Handler)
    import ssl
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain("/tmp/server.crt", "/tmp/server.key")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
