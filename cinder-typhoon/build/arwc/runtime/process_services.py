#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import http.client
import grp
import json
import os
import pathlib
import ssl
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
        self.send_json(404, {"error": "record not found"})

    def owner_get(self, path: str) -> None:
        state = load_state()
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
