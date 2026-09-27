#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import grp
import json
import os
import pathlib
import ssl
import struct
import tempfile
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


ROLE = os.environ["ARWC_PROCESS_ROLE"]
ROOT = pathlib.Path(os.environ["ARWC_STATE_ROOT"])
STATE = ROOT / "state" / "service.json"
AUDIT = ROOT / "audit" / "events.jsonl"
EVIDENCE = pathlib.Path("/run/arwc-process-evidence")
OT_SESSIONS = pathlib.Path("/run/arwc-ot-read")
CA = "/tmp/ca.crt"
INTERNAL = "historian-r21"

OWNERS = {
    "hmi": "10.77.63.20",
    "historian": "10.77.63.30",
    "engineering": "10.77.63.40",
    "instruments": "a-instruments",
}

INITIAL = {
    "hmi": {
        "present_observed": False, "mode_observed": False, "note_observed": False,
        "trace_correlated": False, "envelope_observed": False,
        "practice_conditions_observed": False, "ineffective_requests_observed": False,
        "practice_sequence_observed": False,
    },
    "historian": {
        "tag_export_observed": False, "scale_observed": False,
        "unit_change_interpreted": False, "mapping_observed": False,
    },
    "engineering": {"project_bundle_observed": False, "deployed_revision_observed": False},
    "instruments": {
        "trace_observed": False, "mapping_observed": False,
        "deployment_observed": False, "practice_observed": False,
    },
}

INITIAL["engineering"].update({
    "diagnostic_observed": False, "compatibility_reproduced": False,
    "hidden_check_recovered": False, "legacy_mapping_recovered": False,
    "viewer_observed": False, "vm_reconstructed": False,
    "sealed_project_opened": False, "concealed_reviewer_used": False,
})
INITIAL["instruments"].update({
    "flash_observed": False, "inspection_recovered": False,
    "image_rewrite_accepted": False,
})

ARTIFACTS = pathlib.Path("/opt/process-service/artifacts")
MASK32 = (1 << 32) - 1
MASK64 = (1 << 64) - 1
W19_RECORDS = [
    "OUTLET_A:800", "OUTLET_B:1200", "LEGACY:4294967295", "CRR:204",
    "MIG-OG2-R19-R21",
]
W19_ALTERNATE = "WRAP-FFFFFFFF-OG2"
CRC32C_POLY = 0x82F63B78
W22_PROJECT = "CRR-SEALED-PKG-R7"

PRESENT = {
    "record_id": "PV-CRR-2026-09-25T1400Z", "revision": 21,
    "interval": {"start": "2026-09-25T14:00:00Z", "end": "2026-09-25T14:05:00Z"},
    "outlet_group": "OG-CRR-02", "asset": "AST-CRR-017",
    "requested_setpoints_m3s": {"GT-CRR-02A": 0.0, "GT-CRR-02B": 0.0},
    "measurements": {
        "gate_position_percent": {"GT-CRR-02A": 0.0, "GT-CRR-02B": 0.0},
        "actual_flow_m3s": {"FIT-CRR-204A": 0.0, "FIT-CRR-204B": 0.0},
        "integrated_volume_ml": 0.0, "usable_reserve_ml": 12.40,
    },
}
MODE = {
    "record_id": "MODE-CRR-17", "revision": 17, "mode": "DRY_PERIOD_MANAGED",
    "project": "CRR-CTRL-R21", "outlet_group": "OG-CRR-02", "current": True,
}
NOTE = {
    "record_id": "ENG-CRR-OG2-17", "revision": 1,
    "instrument": "FIT-CRR-204B", "historian_tag": "CRR.OUTLET.02B.FLOW_ACTUAL",
    "description": "Cairn Reach outlet group 2B actual-flow instrument",
}
TRACE = {
    "record_id": "EVT-COMM-OG2-114", "revision": 21,
    "outlet_group": "OG-CRR-02", "project": "CRR-CTRL-R21",
    "sequence": {"ramp_open_seconds": 20, "hold_seconds": 40, "ramp_close_seconds": 20,
                 "each_gate_peak_m3s": 0.10},
    "full_flow_equivalent_seconds": 60, "integrated_volume_ml": 0.012,
    "authority": "read-only recorded commissioning event",
}
TAG_EXPORT = {
    "record_id": "TAGS-CRR-R21", "revision": 21, "project": "CRR-CTRL-R21",
    "tags": [
        {"legacy_group": "OUTLET_A", "kind": "command", "tag": "CRR.OUTLET.02A.FLOW_SP"},
        {"legacy_group": "OUTLET_A", "kind": "position", "tag": "CRR.OUTLET.02A.POS_ACTUAL"},
        {"legacy_group": "OUTLET_A", "kind": "flow", "tag": "CRR.OUTLET.02A.FLOW_ACTUAL"},
        {"legacy_group": "OUTLET_B", "kind": "command", "tag": "CRR.OUTLET.02B.FLOW_SP"},
        {"legacy_group": "OUTLET_B", "kind": "position", "tag": "CRR.OUTLET.02B.POS_ACTUAL"},
        {"legacy_group": "OUTLET_B", "kind": "flow", "tag": "CRR.OUTLET.02B.FLOW_ACTUAL"},
    ],
}
SCALE = {
    "record_id": "SCALE-CRR-R8", "revision": 8, "signed": True,
    "position": {"counts_full_scale": 10000, "engineering_unit": "percent-open"},
    "flow": {"counts_per_m3s": 10000, "engineering_unit": "m3/s"},
}
UNIT_CHANGE = {
    "record_id": "SCALE-CHANGE-OG2-8", "revision": 8,
    "deployment": "CRR-CTRL-R21", "current_divisor": 10000,
    "retained_project": "CRR-CTRL-R19", "retained_divisor": 8000,
    "sample_counts": 1200, "current_m3s": 0.12, "retained_m3s": 0.15,
}
MAPPING = {
    "record_id": "MAP-OG2-R8", "revision": 8, "project": "CRR-CTRL-R21",
    "event": "EVT-COMM-OG2-114", "outlet_group": "OG-CRR-02",
    "map": [
        {"flow_tag": "CRR.OUTLET.02A.FLOW_ACTUAL", "gate": "GT-CRR-02A", "instrument": "FIT-CRR-204A"},
        {"flow_tag": "CRR.OUTLET.02B.FLOW_ACTUAL", "gate": "GT-CRR-02B", "instrument": "FIT-CRR-204B"},
    ],
}
PROJECT_BUNDLE = {
    "record_id": "PROJ-CRR-INDEX-R9", "revision": 9,
    "workspace_claim": "CRR-CTRL-R19",
    "deployment_note": {"record_id": "ENG-DEPLOY-CRR-21", "signed": True,
                        "manifest_project": "CRR-CTRL-R21"},
}
DEPLOYMENT = {
    "record_id": "DEPLOY-OBS-CRR-21", "revision": 21,
    "project": "CRR-CTRL-R21",
    "project_sha256": hashlib.sha256(b"CRR-CTRL-R21/deployed").hexdigest(),
    "source": "independent instrument handshake",
}
ENVELOPE = {
    "record_id": "ENV-OG2-R6", "revision": 6, "outlet_group": "OG-CRR-02",
    "per_gate_m3s": [0.0, 0.50], "aggregate_max_m3s": 1.0,
    "ramp_max_m3s_per_20s": 0.10, "hold_max_seconds": 1200,
    "volume_max_ml": 1.20,
}
CONDITIONS = {
    "record_id": "PRACTICE-PERM-02", "revision": 2, "checkpoint": "PRACTICE-OG2-07",
    "permissive": False, "reason": "simulation reset_complete is not asserted",
    "live_permissive": "PERM-OG2-LIVE-R4", "live_state_separate": True,
}
INEFFECTIVE = {
    "record_id": "PRACTICE-REQUESTS-11-12", "revision": 1,
    "requests": [
        {"request_id": "PRACTICE-REQ-11", "acknowledged": True, "actuated": False},
        {"request_id": "PRACTICE-REQ-12", "acknowledged": True, "actuated": False},
    ],
    "permissive": "PRACTICE-PERM-02", "measured_flow_m3s": 0.0,
}
PRACTICE = {
    "record_id": "PRACTICE-OG2-07", "revision": 7, "live": False,
    "permissive_transition": {"reset_complete": True, "permissive": True},
    "sequence": {"each_gate_target_m3s": 0.15, "ramp_open_seconds": 30,
                 "hold_seconds": 70, "ramp_close_seconds": 30},
    "full_flow_equivalent_seconds": 100, "measured_volume_ml": 0.03,
    "live_reserve_changed": False,
}


def atomic_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o640)
        os.replace(temporary, path)
        if path.is_relative_to(EVIDENCE):
            os.chown(path, -1, grp.getgrnam("arwc-process-evidence").gr_gid)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def initialize() -> None:
    if not STATE.exists():
        atomic_json(STATE, INITIAL[ROLE])
    else:
        state = load_state()
        changed = False
        for key, value in INITIAL[ROLE].items():
            if key not in state:
                state[key] = value
                changed = True
        if changed:
            atomic_json(STATE, state)
    AUDIT.touch(mode=0o640, exist_ok=True)


def load_state() -> dict[str, object]:
    return json.loads(STATE.read_text(encoding="utf-8"))


def save_state(value: dict[str, object]) -> None:
    atomic_json(STATE, value)


def append_audit(action: str, result: dict[str, object]) -> str:
    correlation = str(uuid.uuid4())
    event = {
        "audit_id": correlation,
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tenant": "arwc", "principal": f"svc-{ROLE}", "action": action,
        "object": result.get("record_id"), "revision": result.get("revision"),
        "result_digest": hashlib.sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return correlation


def authored_asset(name: str) -> str:
    return (pathlib.Path("/opt/process-service/assets") / f"{name}.md").read_text(encoding="utf-8")


def rotl(value: int, count: int, width: int) -> int:
    mask = (1 << width) - 1
    count %= width
    return ((value << count) | (value >> (width - count))) & mask


def w19_rolling(record: str) -> int:
    value = 0x6D2B79F5
    for byte in record.encode("ascii"):
        value = (rotl((value ^ byte) & MASK32, 5, 32) + 0x9E3779B9) & MASK32
    return value


def w19_verifier(record: str) -> int:
    rolling = w19_rolling(record)
    value = rotl(0x243F6A8885A308D3 ^ ((rolling * 0x100000001B3) & MASK64), 9, 64)
    return value ^ rolling


def crc32c(data: bytes) -> int:
    value = 0xFFFFFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (CRC32C_POLY if value & 1 else 0)
    return value ^ 0xFFFFFFFF


def decode_flash_record(record: bytes, offset: int) -> dict[str, object] | None:
    if record == b"\xff" * 64:
        return None
    if len(record) != 64 or record[:4] != b"F204" or record[63] != 0:
        return None
    length = struct.unpack_from("<H", record, 8)[0]
    if length > 44 or record[60:63] != b"\xff\xff\xff":
        return None
    expected = struct.unpack_from("<I", record, 56)[0]
    if crc32c(record[:56]) != expected:
        return None
    try:
        record_id, asset, date = record[12:12 + length].decode("ascii").split("\0")
    except (UnicodeDecodeError, ValueError):
        return None
    statuses = {1: "REVIEW", 2: "ACCEPTED"}
    if record[10] not in statuses:
        return None
    return {
        "record_id": record_id, "asset": asset, "inspection_date": date,
        "sequence": struct.unpack_from("<I", record, 4)[0],
        "status": statuses[record[10]], "flags": record[11],
        "crc32c": f"{expected:08x}", "offset": offset,
    }


def parse_flash(image: bytes) -> list[dict[str, object]]:
    if len(image) != 8192:
        raise ValueError("wrong image length")
    records: list[dict[str, object]] = []
    for offset in range(0, len(image), 64):
        decoded = decode_flash_record(image[offset:offset + 64], offset)
        if decoded is not None:
            records.append(decoded)
    return records


def logical_flash(records: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for record in records:
        name = str(record["record_id"])
        if name not in result or int(record["sequence"]) > int(result[name]["sequence"]):
            result[name] = record
    return result


def run_viewer_vm(program: bytes) -> dict[str, object]:
    if len(program) % 6:
        raise ValueError("invalid program length")
    registers = [0, 0, 0, 0]
    memory = bytearray(256)
    zero = False
    pc = 0
    steps = 0
    while 0 <= pc < len(program) // 6 and steps < 4096:
        opcode, dst, src, immediate = struct.unpack_from("<HBBH", program, pc * 6)
        if dst > 3 or src > 3:
            raise ValueError("invalid register")
        steps += 1
        if opcode == 0x01:
            registers[dst] = immediate
            zero = registers[dst] == 0
            pc += 1
        elif opcode == 0x02:
            registers[dst] = memory[(registers[src] + immediate) & 0xFF]
            zero = registers[dst] == 0
            pc += 1
        elif opcode == 0x03:
            registers[dst] = (registers[dst] ^ registers[src] ^ immediate) & 0xFFFF
            zero = registers[dst] == 0
            pc += 1
        elif opcode == 0x04:
            registers[dst] = (registers[dst] + registers[src] + immediate) & 0xFFFF
            zero = registers[dst] == 0
            pc += 1
        elif opcode == 0x05:
            count = immediate & 15
            value = registers[src]
            registers[dst] = value if count == 0 else ((value << count) | (value >> (16 - count))) & 0xFFFF
            zero = registers[dst] == 0
            pc += 1
        elif opcode == 0x06:
            memory[(registers[dst] + immediate) & 0xFF] = registers[src] & 0xFF
            pc += 1
        elif opcode == 0x07:
            pc = pc + struct.unpack("<h", struct.pack("<H", immediate))[0] if not zero else pc + 1
        elif opcode == 0xFF:
            break
        else:
            raise ValueError("invalid opcode")
    if steps >= 4096:
        raise ValueError("instruction limit")
    return {"registers": registers, "memory": bytes(memory), "steps": steps}


def viewer_result(result: dict[str, object]) -> dict[str, object]:
    memory = result["memory"]
    if not isinstance(memory, bytes):
        raise ValueError("invalid VM memory")
    return {"registers": result["registers"],
            "memory_40_80_sha256": hashlib.sha256(memory[0x40:0x80]).hexdigest(),
            "steps": result["steps"]}


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Process-Services/21"
    sys_version = ""

    def log_message(self, message: str, *args: object) -> None:
        print(f"{self.client_address[0]} {message % args}", flush=True)

    def send_json(self, status: int, body: dict[str, object]) -> None:
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
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
            result = json.loads(self.rfile.read(length))
            if not isinstance(result, dict):
                raise ValueError
            return result
        except (ValueError, json.JSONDecodeError):
            self.send_json(409, {"error": "invalid request"})
            return None

    def externally_authorized(self) -> bool:
        if self.headers.get("X-ARWC-Tenant", "arwc") != "arwc":
            self.send_json(403, {"error": "session is not valid for this tenant"})
            return False
        supplied = self.headers.get("Authorization", "")
        if not supplied.startswith("Bearer "):
            self.send_json(403, {"error": "scoped process-read session required"})
            return False
        digest = hashlib.sha256(supplied[7:].encode()).hexdigest()
        for name in ("corporate.json", "contractor.json"):
            try:
                evidence = json.loads((OT_SESSIONS / name).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if (evidence.get("scope") == "OG-CRR-02/read" and
                    hmac.compare_digest(digest, str(evidence.get("token_sha256", "")))):
                return True
        self.send_json(403, {"error": "scoped process-read session required"})
        return False

    def authorized(self) -> bool:
        if ROLE == "historian":
            return self.externally_authorized()
        if self.headers.get("X-ARWC-Internal") != INTERNAL:
            self.send_json(403, {"error": "historian service context required"})
            return False
        return True

    def accepted(self, action: str, record: dict[str, object], status: int = 200,
                 extra: dict[str, object] | None = None) -> None:
        result: dict[str, object] = {"audit_id": append_audit(action, record), "record": record}
        if extra:
            result.update(extra)
        self.send_json(status, result)

    def internal_request(self, owner: str, method: str, path: str,
                         body: dict[str, object] | None = None) -> tuple[int, dict[str, object]]:
        payload = None if body is None else json.dumps(body, separators=(",", ":")).encode()
        headers = {"X-ARWC-Internal": INTERNAL, "X-ARWC-Tenant": "arwc"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(payload))
        context = ssl.create_default_context(cafile=CA)
        connection = http.client.HTTPSConnection(OWNERS[owner], 443, context=context, timeout=5)
        try:
            connection.request(method, path, body=payload, headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def historian_proxy(self, method: str, path: str, body: dict[str, object] | None) -> None:
        owner = "hmi" if path in {
            "/api/the-reservoir-s-present-tense", "/api/the-mode-the-plant-is-in",
            "/api/the-instrument-in-the-note", "/api/the-operating-envelope",
            "/api/conditions-before-movement", "/api/accepted-is-not-actuated",
            "/api/a-sequence-the-process-can-follow",
        } else "instruments" if path in {
            "/api/what-the-image-kept", "/api/a-valid-maintenance-record",
            "/api/change-one-record-keep-the-rest",
        } else "engineering"
        try:
            status, result = self.internal_request(owner, method, path, body)
        except (OSError, json.JSONDecodeError):
            self.send_json(409, {"error": "owning process service unavailable"})
            return
        self.send_json(status, result)

    def do_GET(self) -> None:
        if not self.authorized():
            return
        path = urlsplit(self.path).path
        if ROLE == "historian":
            if path in {"/api/the-tag-export", "/api/the-scale-kept-elsewhere"}:
                self.historian_get(path)
            elif path in {
                "/api/the-reservoir-s-present-tense", "/api/the-mode-the-plant-is-in",
                "/api/the-instrument-in-the-note", "/api/the-operating-envelope",
                "/api/conditions-before-movement", "/api/the-project-and-the-note",
                "/api/the-diagnostic-nobody-retired", "/api/what-the-image-kept",
                "/api/the-viewer-in-the-delivery",
            }:
                self.historian_proxy("GET", path, None)
            else:
                self.send_json(404, {"error": "record not found"})
            return
        self.owner_get(path)

    def do_POST(self) -> None:
        if not self.authorized():
            return
        request = self.body()
        if request is None:
            return
        path = urlsplit(self.path).path
        if ROLE == "historian":
            self.historian_post(path, request)
        else:
            self.owner_post(path, request)

    def historian_get(self, path: str) -> None:
        state = load_state()
        if path == "/api/the-tag-export":
            state["tag_export_observed"] = True
            record, action = TAG_EXPORT, "the-tag-export"
        else:
            state["scale_observed"] = True
            record, action = SCALE, "the-scale-kept-elsewhere"
        save_state(state)
        self.accepted(action, record)

    def historian_post(self, path: str, request: dict[str, object]) -> None:
        if path == "/api/the-first-live-trace":
            expected = {"event": "EVT-COMM-OG2-114", "project": "CRR-CTRL-R21",
                        "hmi_series": "HMI-EVT-114", "instrument_series": "INST-EVT-114"}
            if request != expected:
                self.send_json(409, {"error": "commissioning trace binding does not match"})
                return
            h_status, h_result = self.internal_request("hmi", "POST", path, request)
            if h_status != 201:
                self.send_json(h_status, h_result)
                return
            i_status, i_result = self.internal_request("instruments", "POST", path, request)
            if i_status != 201:
                self.send_json(409, {"error": "independent trace correlation failed"})
                return
            self.send_json(201, {**h_result, "instrument_observation": i_result["record"]})
            return
        if path == "/api/when-the-units-changed":
            state = load_state()
            if not state["tag_export_observed"] or not state["scale_observed"]:
                self.send_json(403, {"error": "tag export and scale table required"})
                return
            if request != {"sample_counts": 1200, "current_divisor": 10000,
                           "retained_divisor": 8000, "deployment": "CRR-CTRL-R21"}:
                self.send_json(409, {"error": "scale interpretation does not match"})
                return
            state["unit_change_interpreted"] = True
            save_state(state)
            self.accepted("when-the-units-changed", UNIT_CHANGE, 201)
            return
        if path == "/api/which-outlet-answers":
            state = load_state()
            if not state["unit_change_interpreted"]:
                self.send_json(403, {"error": "current scale interpretation required"})
                return
            if request != {"event": "EVT-COMM-OG2-114", "scale": "SCALE-CRR-R8",
                           "project": "CRR-CTRL-R21", "outlet_group": "OG-CRR-02"}:
                self.send_json(409, {"error": "mapping evidence does not match"})
                return
            try:
                trace = json.loads((EVIDENCE / "hmi" / "W17-observation.json").read_text())
            except (OSError, json.JSONDecodeError):
                self.send_json(403, {"error": "commissioning observation evidence required"})
                return
            i_status, i_result = self.internal_request("instruments", "POST", path, request)
            if i_status != 201 or trace.get("record_id") != "EVT-COMM-OG2-114":
                self.send_json(409, {"error": "independent mapping observation failed"})
                return
            state["mapping_observed"] = True
            save_state(state)
            atomic_json(EVIDENCE / "historian" / "W18-map.json", MAPPING)
            self.accepted("which-outlet-answers", MAPPING, 201,
                          {"instrument_observation": i_result["record"]})
            return
        if path == "/api/which-project-is-running":
            e_status, e_result = self.internal_request("engineering", "POST", path, request)
            if e_status != 201:
                self.send_json(e_status, e_result)
                return
            i_status, i_result = self.internal_request("instruments", "POST", path, request)
            if i_status != 201:
                self.send_json(409, {"error": "deployed project comparison failed"})
                return
            self.send_json(201, {**e_result, "instrument_observation": i_result["record"]})
            return
        if path == "/api/a-sequence-the-process-can-follow":
            h_status, h_result = self.internal_request("hmi", "POST", path, request)
            if h_status != 201:
                self.send_json(h_status, h_result)
                return
            i_status, i_result = self.internal_request("instruments", "POST", path, request)
            if i_status != 201:
                self.send_json(409, {"error": "practice sequence did not produce independent observation"})
                return
            self.send_json(201, {**h_result, "instrument_observation": i_result["record"]})
            return
        if path in {"/api/accepted-is-not-actuated"}:
            self.historian_proxy("POST", path, request)
            return
        if path in {
            "/api/a-second-interpretation", "/api/the-hidden-check",
            "/api/a-map-from-the-old-diagnostic", "/api/a-valid-maintenance-record",
            "/api/change-one-record-keep-the-rest",
            "/api/the-machine-inside-the-viewer",
            "/api/the-decision-inside-the-sealed-project",
            "/api/the-reviewer-who-was-never-listed",
        }:
            self.historian_proxy("POST", path, request)
            return
        self.send_json(404, {"error": "record not found"})

    def owner_get(self, path: str) -> None:
        state = load_state()
        if ROLE == "engineering" and path == "/api/the-diagnostic-nobody-retired":
            binary = (ARTIFACTS / "diag-crr-mixed-19").read_bytes()
            state["diagnostic_observed"] = True
            save_state(state)
            record = {
                "record_id": "DIAG-CRR-MIXED-19", "revision": 19,
                "project_family": "CRR-CTRL-R19", "format": "ELF64-x86-64-stripped",
                "sha256": hashlib.sha256(binary).hexdigest(),
                "ordinary_traces": [
                    {"record": item, "rolling32": f"{w19_rolling(item):08x}",
                     "verifier64": f"{w19_verifier(item):016x}"}
                    for item in W19_RECORDS[:4]
                ],
                "protected_record": W19_RECORDS[4],
            }
            self.accepted("the-diagnostic-nobody-retired", record,
                          extra={"artifact_b64": base64.b64encode(binary).decode()})
            return
        if ROLE == "engineering" and path == "/api/the-viewer-in-the-delivery":
            if not state["deployed_revision_observed"]:
                self.send_json(403, {"error": "current deployed-revision evidence required"})
                return
            viewer = (ARTIFACTS / "sealed-viewer").read_bytes()
            program = (ARTIFACTS / "viewer-program.bin").read_bytes()
            package = (ARTIFACTS / "sealed-project.bin").read_bytes()
            metadata = json.loads((ARTIFACTS / "sealed-metadata.json").read_text())
            state["viewer_observed"] = True
            save_state(state)
            record = {
                "record_id": "ENG-CRR-SEALED-22", "revision": 22,
                "viewer": "VIEW-CRR-R5", "viewer_language": "Nim 2.0.8",
                "platform": "linux/amd64", "project_id": W22_PROJECT,
                "viewer_sha256": hashlib.sha256(viewer).hexdigest(),
                "program_sha256": hashlib.sha256(program).hexdigest(),
                "package_sha256": hashlib.sha256(package).hexdigest(),
                "ordinary_cases": metadata["cases"],
            }
            self.accepted("the-viewer-in-the-delivery", record, extra={
                "viewer_b64": base64.b64encode(viewer).decode(),
                "program_b64": base64.b64encode(program).decode(),
                "package_b64": base64.b64encode(package).decode(),
            })
            return
        if ROLE == "instruments" and path == "/api/what-the-image-kept":
            image = (ARTIFACTS / "IMG-FIT-204-R6.bin").read_bytes()
            manifest = json.loads((ARTIFACTS / "IMG-FIT-204-R6.json").read_text())
            state["flash_observed"] = True
            save_state(state)
            record = {
                **manifest, "interface": "SIM-FIT-204-R6", "byte_order": "little-endian",
                "record_layout": {
                    "magic": [0, 4], "sequence_u32": 4, "payload_length_u16": 8,
                    "status": 10, "flags": 11, "payload": [12, 56],
                    "crc32c_u32": 56, "reserved": [60, 63], "commit": 63,
                },
            }
            self.accepted("what-the-image-kept", record,
                          extra={"image_b64": base64.b64encode(image).decode()})
            return
        if ROLE == "hmi":
            records = {
                "/api/the-reservoir-s-present-tense": ("present_observed", PRESENT, "the-reservoir-s-present-tense"),
                "/api/the-mode-the-plant-is-in": ("mode_observed", MODE, "the-mode-the-plant-is-in"),
                "/api/the-instrument-in-the-note": ("note_observed", NOTE, "the-instrument-in-the-note"),
                "/api/the-operating-envelope": ("envelope_observed", ENVELOPE, "the-operating-envelope"),
                "/api/conditions-before-movement": ("practice_conditions_observed", CONDITIONS, "conditions-before-movement"),
            }
        elif ROLE == "engineering":
            records = {
                "/api/the-project-and-the-note": ("project_bundle_observed", PROJECT_BUNDLE, "the-project-and-the-note"),
            }
        else:
            records = {}
        if path not in records:
            self.send_json(404, {"error": "record not found"})
            return
        field, record, action = records[path]
        state[field] = True
        save_state(state)
        extra: dict[str, object] = {}
        if path == "/api/the-instrument-in-the-note":
            extra["engineering_context"] = authored_asset("me-engineering-note-01-1")
        elif path == "/api/the-project-and-the-note":
            extra["handover_context"] = authored_asset("me-project-handover-01")
        self.accepted(action, record, extra=extra)

    def owner_post(self, path: str, request: dict[str, object]) -> None:
        state = load_state()
        if ROLE == "engineering" and path in {
            "/api/a-second-interpretation", "/api/the-hidden-check",
            "/api/a-map-from-the-old-diagnostic",
        }:
            self.w19_post(path, request, state)
            return
        if ROLE == "engineering" and path in {
            "/api/the-machine-inside-the-viewer",
            "/api/the-decision-inside-the-sealed-project",
            "/api/the-reviewer-who-was-never-listed",
        }:
            self.w22_post(path, request, state)
            return
        if ROLE == "instruments" and path in {
            "/api/a-valid-maintenance-record", "/api/change-one-record-keep-the-rest",
        }:
            self.w20_post(path, request, state)
            return
        if ROLE == "hmi" and path == "/api/the-first-live-trace":
            if not (state["present_observed"] and state["mode_observed"] and state["note_observed"]):
                self.send_json(403, {"error": "current view, mode, and instrument note required"})
                return
            if request != {"event": "EVT-COMM-OG2-114", "project": "CRR-CTRL-R21",
                           "hmi_series": "HMI-EVT-114", "instrument_series": "INST-EVT-114"}:
                self.send_json(409, {"error": "commissioning trace binding does not match"})
                return
            state["trace_correlated"] = True
            save_state(state)
            atomic_json(EVIDENCE / "hmi" / "W17-observation.json", TRACE)
            self.accepted("the-first-live-trace", TRACE, 201,
                          {"commissioning_context": authored_asset("me-commissioning-01")})
            return
        if ROLE == "hmi" and path == "/api/accepted-is-not-actuated":
            if not state["envelope_observed"] or not state["practice_conditions_observed"]:
                self.send_json(403, {"error": "practice envelope and permissive evidence required"})
                return
            if request != {"requests": ["PRACTICE-REQ-11", "PRACTICE-REQ-12"],
                           "permissive": "PRACTICE-PERM-02", "expected_actuation": False}:
                self.send_json(409, {"error": "practice request interpretation does not match"})
                return
            state["ineffective_requests_observed"] = True
            save_state(state)
            self.accepted("accepted-is-not-actuated", INEFFECTIVE, 201)
            return
        if ROLE == "hmi" and path == "/api/a-sequence-the-process-can-follow":
            if not state["ineffective_requests_observed"] or not state["trace_correlated"]:
                self.send_json(403, {"error": "practice interpretation and current observation evidence required"})
                return
            expected = {"checkpoint": "PRACTICE-OG2-07", "reset_complete": True,
                        "each_gate_target_m3s": 0.15, "ramp_open_seconds": 30,
                        "hold_seconds": 70, "ramp_close_seconds": 30}
            if request != expected:
                self.send_json(409, {"error": "practice sequence is outside the operating envelope"})
                return
            state["practice_sequence_observed"] = True
            save_state(state)
            atomic_json(EVIDENCE / "hmi" / "W25-practice.json", PRACTICE)
            self.accepted("a-sequence-the-process-can-follow", PRACTICE, 201)
            return
        if ROLE == "engineering" and path == "/api/which-project-is-running":
            if not state["project_bundle_observed"]:
                self.send_json(403, {"error": "project index and deployment note required"})
                return
            expected = {"project_index": "PROJ-CRR-INDEX-R9", "workspace_claim": "CRR-CTRL-R19",
                        "deployment_note": "ENG-DEPLOY-CRR-21", "observed_project": "CRR-CTRL-R21",
                        "observed_digest": DEPLOYMENT["project_sha256"]}
            if request != expected:
                self.send_json(409, {"error": "project comparison does not match deployment observation"})
                return
            state["deployed_revision_observed"] = True
            save_state(state)
            result = {"record_id": "CMP-CRR-R21", "revision": 21,
                      "rejected_claim": "CRR-CTRL-R19", "deployed_project": "CRR-CTRL-R21",
                      "observation": "DEPLOY-OBS-CRR-21"}
            atomic_json(EVIDENCE / "engineering" / "W21-revision.json", result)
            self.accepted("which-project-is-running", result, 201)
            return
        if ROLE == "instruments" and path == "/api/the-first-live-trace":
            state["trace_observed"] = True
            save_state(state)
            result = {**TRACE, "record_id": "INST-EVT-114", "source": "independent instruments"}
            atomic_json(EVIDENCE / "instruments" / "W17-observation.json", result)
            self.accepted("the-first-live-trace", result, 201)
            return
        if ROLE == "instruments" and path == "/api/which-outlet-answers":
            if not state["trace_observed"]:
                self.send_json(403, {"error": "independent commissioning trace required"})
                return
            state["mapping_observed"] = True
            save_state(state)
            result = {"record_id": "INST-MAP-OG2-R8", "revision": 8,
                      "outlet_group": "OG-CRR-02", "instruments": ["FIT-CRR-204A", "FIT-CRR-204B"]}
            atomic_json(EVIDENCE / "instruments" / "W18-map.json", result)
            self.accepted("which-outlet-answers", result, 201)
            return
        if ROLE == "instruments" and path == "/api/which-project-is-running":
            state["deployment_observed"] = True
            save_state(state)
            atomic_json(EVIDENCE / "instruments" / "W21-deployment.json", DEPLOYMENT)
            self.accepted("which-project-is-running", DEPLOYMENT, 201)
            return
        if ROLE == "instruments" and path == "/api/a-sequence-the-process-can-follow":
            state["practice_observed"] = True
            save_state(state)
            result = {"record_id": "INST-PRACTICE-OG2-07", "revision": 7,
                      "measured_volume_ml": 0.03, "live_reserve_changed": False,
                      "gate_peak_m3s": {"GT-CRR-02A": 0.15, "GT-CRR-02B": 0.15}}
            atomic_json(EVIDENCE / "instruments" / "W25-practice.json", result)
            self.accepted("a-sequence-the-process-can-follow", result, 201)
            return
        self.send_json(404, {"error": "record not found"})

    def w22_post(self, path: str, request: dict[str, object], state: dict[str, object]) -> None:
        metadata = json.loads((ARTIFACTS / "sealed-metadata.json").read_text())
        if not state["viewer_observed"]:
            self.send_json(403, {"error": "protected viewer delivery required"})
            return
        if path == "/api/the-machine-inside-the-viewer":
            if request != {"cases": [case["result"] for case in metadata["cases"]]}:
                self.send_json(409, {"error": "viewer-machine results do not match"})
                return
            state["vm_reconstructed"] = True
            save_state(state)
            result = {
                "record_id": "VIEW-VM-R5", "revision": 5,
                "encoding": "u16-opcode,u8-dst,u8-src,u16-immediate;little-endian",
                "opcodes": {"MOVI": 1, "LOAD8": 2, "XOR": 3, "ADD": 4,
                            "ROTL": 5, "STORE8": 6, "JNZ": 7, "HALT": 255},
                "registers": 4, "memory_bytes": 256, "instruction_limit": 4096,
                "cases": metadata["cases"],
            }
            self.accepted("the-machine-inside-the-viewer", result, 201)
            return
        if not state["vm_reconstructed"]:
            self.send_json(403, {"error": "reconstructed viewer machine required"})
            return
        if path == "/api/the-decision-inside-the-sealed-project":
            from cryptography.exceptions import InvalidTag
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            if request.get("project_id") != W22_PROJECT or not isinstance(request.get("key_hex"), str):
                self.send_json(409, {"error": "project package authentication failed"})
                return
            try:
                key = bytes.fromhex(str(request["key_hex"]))
                package = (ARTIFACTS / "sealed-project.bin").read_bytes()
                plaintext = AESGCM(key).decrypt(package[:12], package[12:], W22_PROJECT.encode())
                opened = json.loads(plaintext)
            except (ValueError, InvalidTag, json.JSONDecodeError):
                self.send_json(409, {"error": "project package authentication failed"})
                return
            expected = {
                "record_id": "DEC-CRR-OG2-R7", "project": "CRR-CTRL-R21", "revision": 7,
                "decision": "Retain the commissioning flow-scale exception until independent field verification.",
                "review_helper": "REVIEWHELP-R4", "captured_session": "ARCHIVE-REVIEW-R7-ELIAS",
                "comparison": "CMP-CRR-R21-R7",
            }
            if opened != expected:
                self.send_json(409, {"error": "project package authentication failed"})
                return
            helper = (ARTIFACTS / "ReviewHelper.dll").read_bytes()
            state["sealed_project_opened"] = True
            save_state(state)
            atomic_json(EVIDENCE / "engineering" / "W22-decision.json", opened)
            self.accepted("the-decision-inside-the-sealed-project", opened, 201, {
                "review_helper_b64": base64.b64encode(helper).decode(),
                "review_helper_sha256": hashlib.sha256(helper).hexdigest(),
                "archive_context": {"session": opened["captured_session"],
                                    "comparison": opened["comparison"]},
            })
            return
        if not state["sealed_project_opened"]:
            self.send_json(403, {"error": "opened engineering project required"})
            return
        helper = (ARTIFACTS / "ReviewHelper.dll").read_bytes()
        expected_request = {
            "helper_sha256": hashlib.sha256(helper).hexdigest(),
            "reviewer": "elias.vorn-review", "session": "ARCHIVE-REVIEW-R7-ELIAS",
            "comparison": "CMP-CRR-R21-R7", "project": "CRR-CTRL-R21",
        }
        if request != expected_request:
            self.send_json(409, {"error": "retained review context does not match"})
            return
        state["concealed_reviewer_used"] = True
        save_state(state)
        result = {
            "record_id": "CMP-CRR-R21-R7", "revision": 7, "project": "CRR-CTRL-R21",
            "reviewer": "elias.vorn-review", "historical": True,
            "comparison": "The deployed R21 scale differs from the retained R19 interpretation for outlet group 2B.",
            "current_identity": False, "maintenance_approval": False, "control_authority": False,
        }
        atomic_json(EVIDENCE / "engineering" / "W22-review.json", result)
        self.accepted("the-reviewer-who-was-never-listed", result, 201)

    def w19_post(self, path: str, request: dict[str, object], state: dict[str, object]) -> None:
        if not state["diagnostic_observed"]:
            self.send_json(403, {"error": "retained diagnostic package required"})
            return
        if path == "/api/a-second-interpretation":
            expected = {"record": W19_ALTERNATE, "rolling32": f"{w19_rolling(W19_ALTERNATE):08x}"}
            if request != expected:
                self.send_json(409, {"error": "compatibility-decoder result does not match"})
                return
            state["compatibility_reproduced"] = True
            save_state(state)
            self.accepted("a-second-interpretation", {
                "record_id": "DIAG-TRACE-COMPAT-19", "revision": 19,
                "execution": "i386-compatibility", **expected,
            }, 201)
            return
        if not state["compatibility_reproduced"]:
            self.send_json(403, {"error": "compatibility-decoder result required"})
            return
        if path == "/api/the-hidden-check":
            expected = [
                {"record": item, "rolling32": f"{w19_rolling(item):08x}",
                 "verifier64": f"{w19_verifier(item):016x}"}
                for item in W19_RECORDS
            ]
            if request != {"decisions": expected}:
                self.send_json(409, {"error": "mixed-width verifier decisions do not match"})
                return
            state["hidden_check_recovered"] = True
            save_state(state)
            result = {
                "record_id": "MIG-OG2-R19-R21", "revision": 21,
                "rolling32": expected[-1]["rolling32"],
                "verifier64": expected[-1]["verifier64"], "decision": "valid",
            }
            atomic_json(EVIDENCE / "engineering" / "W19-verifier.json", result)
            self.accepted("the-hidden-check", result, 201)
            return
        if not state["hidden_check_recovered"]:
            self.send_json(403, {"error": "recovered diagnostic decisions required"})
            return
        mapping = {
            "legacy_project": "CRR-CTRL-R19", "current_project": "CRR-CTRL-R21",
            "legacy_identifiers": {"OUTLET_A": "OG-CRR-02/GT-CRR-02A",
                                   "OUTLET_B": "OG-CRR-02/GT-CRR-02B"},
            "instruments": {"OUTLET_A": "FIT-CRR-204A", "OUTLET_B": "FIT-CRR-204B"},
        }
        digest = hashlib.sha256(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        expected_request = {"migration_record": "MIG-OG2-R19-R21", "comparison_digest": digest,
                            "observation": "EVT-COMM-OG2-114"}
        if request != expected_request:
            self.send_json(409, {"error": "legacy mapping comparison does not match"})
            return
        state["legacy_mapping_recovered"] = True
        save_state(state)
        result = {"record_id": "MAP-OG2-LEGACY-R21", "revision": 21,
                  "historical": True, "comparison_digest": digest, **mapping}
        atomic_json(EVIDENCE / "engineering" / "W19-map.json", result)
        self.accepted("a-map-from-the-old-diagnostic", result, 201)

    def w20_post(self, path: str, request: dict[str, object], state: dict[str, object]) -> None:
        if not state["flash_observed"]:
            self.send_json(403, {"error": "retained instrument image required"})
            return
        original = (ARTIFACTS / "IMG-FIT-204-R6.bin").read_bytes()
        original_records = parse_flash(original)
        target = logical_flash(original_records)["INSP-FIT-204-118"]
        if path == "/api/a-valid-maintenance-record":
            expected = {"image_sha256": hashlib.sha256(original).hexdigest(), **target}
            if request != expected:
                self.send_json(409, {"error": "maintenance-record interpretation does not match"})
                return
            state["inspection_recovered"] = True
            save_state(state)
            self.accepted("a-valid-maintenance-record", target, 201)
            return
        if not state["inspection_recovered"]:
            self.send_json(403, {"error": "valid last-inspection record required"})
            return
        operations = request.get("operations")
        encoded = request.get("image_b64")
        if not isinstance(operations, list) or not isinstance(encoded, str):
            self.send_json(409, {"error": "complete programming transcript required"})
            return
        try:
            candidate = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error):
            self.send_json(409, {"error": "instrument image encoding is invalid"})
            return
        simulated = bytearray(original)
        expected_shape = [(128, 56), (184, 4), (191, 1)]
        if len(operations) != len(expected_shape):
            self.send_json(409, {"error": "programming order does not match"})
            return
        for operation, (expected_offset, expected_length) in zip(operations, expected_shape):
            if not isinstance(operation, dict) or operation.get("kind") != "program" or operation.get("offset") != expected_offset:
                self.send_json(409, {"error": "programming order does not match"})
                return
            try:
                data = base64.b64decode(str(operation.get("data_b64", "")), validate=True)
            except (ValueError, base64.binascii.Error):
                self.send_json(409, {"error": "programming data is invalid"})
                return
            if len(data) != expected_length:
                self.send_json(409, {"error": "programming extent does not match"})
                return
            old = simulated[expected_offset:expected_offset + len(data)]
            if any((before & after) != after for before, after in zip(old, data)):
                self.send_json(409, {"error": "programming attempted a zero-to-one transition"})
                return
            simulated[expected_offset:expected_offset + len(data)] = data
        if candidate != bytes(simulated):
            self.send_json(409, {"error": "submitted image does not match programming transcript"})
            return
        try:
            records = parse_flash(candidate)
        except ValueError:
            self.send_json(409, {"error": "instrument image dimensions changed"})
            return
        logical = logical_flash(records)
        if set(logical) != set(logical_flash(original_records)):
            self.send_json(409, {"error": "logical maintenance record set changed"})
            return
        updated = logical["INSP-FIT-204-118"]
        if (updated["sequence"] != 119 or updated["status"] != "ACCEPTED" or
                updated["asset"] != target["asset"] or
                updated["inspection_date"] != target["inspection_date"] or
                logical["CAL-FIT-204-R7"] != logical_flash(original_records)["CAL-FIT-204-R7"]):
            self.send_json(409, {"error": "accepted image changed records outside the permitted field"})
            return
        state["image_rewrite_accepted"] = True
        save_state(state)
        result = {**updated, "image_id": "IMG-FIT-204-R6", "wear_counts": [17, 9],
                  "live_telemetry_changed": False}
        atomic_json(EVIDENCE / "instruments" / "W20-image.json", result)
        self.accepted("change-one-record-keep-the-rest", result, 201)


def main() -> None:
    initialize()
    server = ThreadingHTTPServer(("0.0.0.0", 443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain("/tmp/server.crt", "/tmp/server.key")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
