#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import ssl
import tempfile
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import schedule33


ROOT = pathlib.Path("/var/lib/arwc-distribution")
STATE = ROOT / "state" / "distribution.json"
AUDIT = ROOT / "audit" / "events.jsonl"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":")); handle.write("\n")
            handle.flush(); os.fsync(handle.fileno())
        os.chmod(temporary, 0o600); os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def initialize() -> None:
    if not STATE.exists():
        atomic_json(STATE, {"rehearsal_response": None, "policy_response": None})
    AUDIT.touch(mode=0o600, exist_ok=True); os.chmod(AUDIT, 0o600)


def load_state() -> dict[str, object]:
    return json.loads(STATE.read_text(encoding="utf-8"))


def valid_uuid(value: object) -> bool:
    try: return str(uuid.UUID(str(value))) == str(value)
    except (TypeError, ValueError): return False


def append_audit(action: str, record: dict[str, object], correlation: str) -> str:
    event = {"audit_id": correlation, "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
             "tenant": "arwc", "principal": "distribution-rehearsal-principal", "action": action,
             "object": record.get("record_id"), "revision": record.get("revision"),
             "result_digest": hashlib.sha256(canonical(record)).hexdigest()}
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush(); os.fsync(handle.fileno())
    return correlation


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Distribution-Rehearsal/1.0"; sys_version = ""

    def log_message(self, message: str, *args: object) -> None:
        print(f"{self.client_address[0]} {message % args}", flush=True)

    def send_json(self, status: int, body: dict[str, object]) -> None:
        encoded = canonical(body); self.send_response(status)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers(); self.wfile.write(encoded)

    def body(self) -> dict[str, object] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 65536: raise ValueError
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict): raise ValueError
            return value
        except (ValueError, json.JSONDecodeError):
            self.send_json(409, {"error": "invalid distribution request"}); return None

    def do_POST(self) -> None:
        if (self.headers.get("X-ARWC-Internal") != "instruments-w33" or
                self.headers.get("X-ARWC-Tenant") != "arwc" or self.client_address[0] != "10.77.64.40"):
            self.send_json(403, {"error": "independent instrument service context required"}); return
        request = self.body()
        if request is None: return
        path = urlsplit(self.path).path
        if path == "/internal/w33-schedule": self.schedule(request)
        elif path == "/internal/w33-policy": self.policy(request)
        else: self.send_json(404, {"error": "record not found"})

    def schedule(self, request: dict[str, object]) -> None:
        correlation = request.get("correlation"); binding = request.get("request"); schedule = request.get("schedule")
        evaluated = None if not isinstance(schedule, dict) else schedule33.evaluate_schedule(
            schedule.get("reservoir_release_m3s"), schedule.get("alternate_supply_m3s"), schedule.get("demand_m3s"))
        if (set(request) != {"correlation", "request", "schedule"} or not valid_uuid(correlation) or
                not isinstance(binding, dict) or evaluated is None or schedule.get("record_id") != "SCHED-CRR-33" or
                binding.get("schedule_sha256") != evaluated.get("schedule_sha256")):
            self.send_json(409, {"error": "distribution rehearsal request is not bound"}); return
        state = load_state(); existing = state.get("rehearsal_response")
        if isinstance(existing, dict):
            if existing.get("audit_id") == correlation: self.send_json(201, existing)
            else: self.send_json(409, {"error": "rehearsal already recorded under another correlation"})
            return
        record = {"record_id": "DIST-REH-CRR-33", "revision": 1, "request_correlation": correlation,
                  "checkpoint": schedule33.CHECKPOINT, "schedule": "SCHED-CRR-33",
                  "initial_buffer_m3": evaluated["initial_buffer_m3"],
                  "final_buffer_m3": evaluated["final_buffer_m3"],
                  "minimum_buffer_m3": evaluated["minimum_buffer_m3"],
                  "maximum_buffer_m3": evaluated["maximum_buffer_m3"],
                  "distribution_state_changed": False}
        response = {"audit_id": append_audit("the-schedule-the-service-accepts", record, str(correlation)),
                    "record": record}
        state["rehearsal_response"] = response; atomic_json(STATE, state)
        atomic_json(ROOT / "results" / "DIST-REH-CRR-33.json", record); self.send_json(201, response)

    def policy(self, request: dict[str, object]) -> None:
        correlation = request.get("correlation"); binding = request.get("request"); supplied = request.get("evaluation")
        evaluated = None if not isinstance(binding, dict) else schedule33.evaluate_policy(binding.get("policy"))
        state = load_state()
        if (set(request) != {"correlation", "request", "evaluation"} or not valid_uuid(correlation) or
                not isinstance(state.get("rehearsal_response"), dict) or evaluated is None or supplied != evaluated):
            self.send_json(409, {"error": "accepted rehearsal and valid policy required"}); return
        existing = state.get("policy_response")
        if isinstance(existing, dict):
            if existing.get("audit_id") == correlation: self.send_json(201, existing)
            else: self.send_json(409, {"error": "policy already recorded under another correlation"})
            return
        record = {"record_id": "DIST-POL-CRR-33", "revision": 1, "request_correlation": correlation,
                  "policy_sha256": evaluated["policy_sha256"], "case_count": evaluated["case_count"],
                  "scenario_steps": evaluated["scenario_steps"],
                  "minimum_buffer_m3": evaluated["minimum_buffer_m3"],
                  "maximum_buffer_m3": evaluated["maximum_buffer_m3"],
                  "distribution_state_changed": False}
        response = {"audit_id": append_audit("when-the-forecast-moves", record, str(correlation)), "record": record}
        state["policy_response"] = response; atomic_json(STATE, state)
        atomic_json(ROOT / "results" / "DIST-POL-CRR-33.json", record); self.send_json(201, response)


def main() -> None:
    initialize(); server = ThreadingHTTPServer(("0.0.0.0", 443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain("/tmp/server.crt", "/tmp/server.key")
    server.socket = context.wrap_socket(server.socket, server_side=True); server.serve_forever()


if __name__ == "__main__": main()
