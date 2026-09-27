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
            "bound_plan": None, "reserve_ml": 12.4, "released_ml": 0.0,
            "bind_response": None, "release_response": None,
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
        "mapping": load_json(PROCESS_EVIDENCE / "historian" / "W18-map.json"),
        "revision": load_json(PROCESS_EVIDENCE / "engineering" / "W21-revision.json"),
        "envelope": load_json(PROCESS_EVIDENCE / "hmi" / "W25-envelope.json"),
        "mode": load_json(PROCESS_EVIDENCE / "hmi" / "W25-practice.json"),
        "plan": load_json(PROCESS_EVIDENCE / "hmi" / "W29-plan.json"),
    }
    if any(value is None for value in records.values()):
        return None
    result = {key: value for key, value in records.items() if value is not None}
    if (result["mapping"].get("record_id") != "MAP-OG2-R8" or
            result["revision"].get("record_id") != "CMP-CRR-R21" or
            result["revision"].get("deployed_project") != "CRR-CTRL-R21" or
            result["envelope"].get("record_id") != "ENV-OG2-R6" or
            result["mode"].get("record_id") != "PRACTICE-OG2-07" or
            result["plan"].get("record_id") != "PLAN-CRR-LOSS-1000" or
            result["plan"].get("mode") != "MODE-CRR-17" or
            result["plan"].get("released_volume_ml") != 1.0 or
            result["plan"].get("reserve_after_ml") != 11.4):
        return None
    return result


def command_timeline() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for second in range(0, 1101, 20):
        if second <= 100:
            flow = 0.5 * second / 100
        elif second <= 1000:
            flow = 0.5
        else:
            flow = 0.5 * (1100 - second) / 100
        result.append({
            "elapsed_seconds": second,
            "GT-CRR-02A_m3s": round(flow, 2),
            "GT-CRR-02B_m3s": round(flow, 2),
        })
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
        if (self.headers.get("X-ARWC-Internal") != "instruments-w30" or
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
        if path == "/internal/w30-bind":
            self.bind_plan(request)
        elif path == "/internal/w30-open":
            self.open_gates(request)
        else:
            self.send_json(404, {"error": "record not found"})

    def bind_plan(self, request: dict[str, object]) -> None:
        correlation = request.get("correlation")
        binding = request.get("request")
        if set(request) != {"correlation", "request"} or not valid_uuid(correlation) or \
                not isinstance(binding, dict):
            self.send_json(409, {"error": "command-plan request is not bound"})
            return
        expected = {
            "control_client": binding.get("control_client"),
            "asset": "AST-CRR-017", "outlet_group": "OG-CRR-02",
            "project": "CRR-CTRL-R21", "project_revision": 21,
            "map": "MAP-OG2-R8", "map_revision": 8,
            "mode": "MODE-CRR-17", "mode_revision": 17,
            "envelope": "ENV-OG2-R6", "envelope_revision": 6,
            "plan": "PLAN-CRR-LOSS-1000",
            "units": {"flow": "m3/s", "volume": "ML", "time": "s"},
        }
        authority = control_authority(binding.get("control_client"))
        context = process_context()
        if authority is None:
            self.send_json(403, {"error": "current scoped control authority required"})
            return
        if binding != expected or context is None:
            self.send_json(409, {"error": "current command-plan bindings do not agree"})
            return
        record = {
            "record_id": "CMD-PLAN-CRR-30-R1", "revision": 1,
            "request_correlation": correlation, "authority": authority["record_id"],
            "asset": "AST-CRR-017", "outlet_group": "OG-CRR-02",
            "project": "CRR-CTRL-R21", "project_revision": 21,
            "map": "MAP-OG2-R8", "map_revision": 8,
            "mode": "MODE-CRR-17", "mode_revision": 17,
            "envelope": "ENV-OG2-R6", "envelope_revision": 6,
            "plan": "PLAN-CRR-LOSS-1000", "status": "bound",
            "units": binding["units"],
            "limits": {"per_gate_max_m3s": 0.5, "aggregate_max_m3s": 1.0,
                       "ramp_max_m3s_per_20s": 0.1, "hold_max_seconds": 1200,
                       "volume_max_ml": 1.2},
        }
        state = load_state()
        existing = state.get("bind_response")
        if isinstance(existing, dict):
            existing_record = existing.get("record")
            if (isinstance(existing_record, dict) and
                    existing_record.get("request_correlation") == correlation and
                    existing_record.get("authority") == authority.get("record_id")):
                self.send_json(201, existing)
            else:
                self.send_json(409, {"error": "command plan already bound under another correlation"})
            return
        state["bound_plan"] = record
        response = {
            "audit_id": append_audit("bind-the-plan-to-the-plant", record, str(correlation)),
            "record": record,
        }
        state["bind_response"] = response
        atomic_json(STATE, state)
        atomic_json(ROOT / "results" / "CMD-PLAN-CRR-30-R1.json", record)
        self.send_json(201, response)

    def open_gates(self, request: dict[str, object]) -> None:
        correlation = request.get("correlation")
        action = request.get("request")
        if set(request) != {"correlation", "request"} or not valid_uuid(correlation) or \
                not isinstance(action, dict):
            self.send_json(409, {"error": "release request is not bound"})
            return
        expected = {
            "control_client": action.get("control_client"),
            "command_plan": "CMD-PLAN-CRR-30-R1",
            "expected_reserve_before_ml": 12.4, "expected_release_ml": 1.0,
        }
        authority = control_authority(action.get("control_client"))
        state = load_state()
        bound = state.get("bound_plan")
        if authority is None:
            self.send_json(403, {"error": "current scoped control authority required"})
            return
        if (action != expected or not isinstance(bound, dict) or
                bound.get("record_id") != "CMD-PLAN-CRR-30-R1" or
                bound.get("authority") != authority.get("record_id")):
            self.send_json(409, {"error": "bound command plan required"})
            return
        existing = state.get("release_response")
        if isinstance(existing, dict):
            existing_record = existing.get("record")
            if (isinstance(existing_record, dict) and
                    existing_record.get("request_correlation") == correlation):
                self.send_json(201, existing)
            else:
                self.send_json(409, {"error": "release already recorded under another correlation"})
            return
        timeline = command_timeline()
        integrated = round(sum(
            ((timeline[index - 1]["GT-CRR-02A_m3s"] + timeline[index]["GT-CRR-02A_m3s"]) +
             (timeline[index - 1]["GT-CRR-02B_m3s"] + timeline[index]["GT-CRR-02B_m3s"]))
            * 0.5 * 20 / 1000
            for index in range(1, len(timeline))
        ), 2)
        if integrated != 1.0:
            self.send_json(409, {"error": "command timeline did not integrate to the bound volume"})
            return
        record = {
            "record_id": "ACT-CRR-OG2-30", "revision": 1,
            "request_correlation": correlation, "command_plan": "CMD-PLAN-CRR-30-R1",
            "authority": authority["record_id"], "asset": "AST-CRR-017",
            "outlet_group": "OG-CRR-02", "project": "CRR-CTRL-R21",
            "permissive": "PERM-OG2-LIVE-R4", "mode": "MODE-CRR-17",
            "timeline": timeline, "elapsed_seconds": 1100,
            "integrated_command_volume_ml": integrated,
            "reserve_before_ml": 12.4, "reserve_after_ml": 11.4,
            "final_gate_positions_percent": {"GT-CRR-02A": 0.0, "GT-CRR-02B": 0.0},
            "status": "complete", "safety_systems_bypassed": False,
        }
        state["reserve_ml"] = 11.4
        state["released_ml"] = 1.0
        audit_id = append_audit("open-the-gates", record, str(correlation))
        response = {"audit_id": audit_id, "record": record}
        state["release_response"] = response
        atomic_json(STATE, state)
        atomic_json(ROOT / "results" / "ACT-CRR-OG2-30.json", record)
        self.send_json(201, response)


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
