#!/usr/bin/env python3
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import grp
import json
import os
import pathlib
import re
import ssl
import struct
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import psycopg2
import reporting_schedule


ROOT = pathlib.Path("/var/lib/arwc-data")
STATE = ROOT / "state" / "planning.json"
REPORTS_STATE_PATH = pathlib.Path("/run/arwc-reports-state.json")


def _load_reports_state() -> dict:
    """Load Metabase question IDs and URLs from the reports state file seeded at deploy time."""
    try:
        return json.loads(REPORTS_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _metabase_card_url(state: dict, key: str, fallback: str) -> str:
    """Return the Metabase URL for a card ID from state, or fall back to a stable string."""
    metabase_url = state.get("metabase_url", "https://reports.arwc.test")
    card_id = state.get(key, "")
    return f"{metabase_url}/api/card/{card_id}" if card_id else fallback
AUDIT = ROOT / "audit" / "events.jsonl"
TOKEN_HASH = ROOT / "auth" / "corporate-session.sha256"
PLANNER_EVIDENCE = pathlib.Path("/run/arwc-planning-evidence/planner-session.json")
INTEGRATION_EVIDENCE = ROOT / "integration" / "planning-data.json"
ARCHIVE_EVIDENCE = ROOT / "archive" / "archive-lineage.json"
BUSINESS_RELATION_EVIDENCE = pathlib.Path("/run/arwc-business-relation/drawing-association.json")
OT_READ_EVIDENCE = pathlib.Path("/run/arwc-ot-read")
PROCESS_EVIDENCE = pathlib.Path("/run/arwc-process-evidence")
PROCESS_PATHS = {
    "/.well-known/arwc-client",
    "/api/diagnostic-programs/current", "/api/signature-records/current/interpretation",
    "/api/signature-programs/current", "/api/diagnostic-programs/legacy",
    "/api/sealed-projects/current/viewer", "/api/sealed-viewers/current/execute",
    "/api/sealed-projects/current", "/api/unlisted-reviewers/current",
    "/api/control-commands", "/api/control-commands/consequence",
    "/api/estimator-runs",
    "/api/signature-requests", "/api/signature-oracles/current",
    "/api/estimator-tasks/current", "/api/reporting-submissions",
    "/api/firmware-images/current", "/api/maintenance-records/current",
    "/api/signature-programs/current/reproductions", "/api/signature-programs/current/constraints",
    "/api/diagnostic-runs",
    "/api/collision-inputs/current", "/api/release-plans/current/confirmation",
    "/api/control-authority",
    "/api/vault-records/current", "/api/signature-records/current",
    "/api/replay-sessions/current/divergence", "/api/diagnostic-programs/authority",
    "/api/replay-sessions/current", "/api/estimator-tasks/current/inputs",
    "/api/estimator-results/current", "/api/replay-sessions/current/execute",
}

DEFINITION = {
    "record_id": "QRY-RESERVE-R7",
    "revision": 7,
    "database": "PostgreSQL 16.4",
    "view": "reserve_report_current",
    "identifier_quote": '"',
    "policy": "SELECT only",
    "ordinary_request": {"report_name": "reserve_report_current"},
    "ordinary_result": "RPT-CRR-RESERVE-R7",
}

ALLOCATION_ID = "ALLOC-2026-DP3-R9"
METER_ID = "MTR-CRR-DP3-R12"
REPORT_ID = "RPT-CRR-DP3-R7"

BOLT_MAGIC = bytes.fromhex("6060b017")
BOLT_54 = bytes.fromhex("00000405")
BOLT_QUERY = (
    "MATCH (a:Asset {record_id: $asset})-[r:RELATION]->(w:Work) "
    "RETURN r.record_id,w.record_id"
)
LINEAGE_OU = (
    "ASSET_WORK]->(w) WITH a MATCH p=(legacy:Legacy)-[:SUPERSEDES]->"
    "(group:OutletGroup)-[:CURRENT_ASSET]->(a)<-[:ARCHIVED_ASSET]-"
    "(archive:Archive) RETURN p //"
)

RELATION_CONTRACT = {
    "record_id": "RELPROTO-CRR-R3",
    "revision": 3,
    "protocol": "Neo4j Bolt 5.4",
    "magic": "60 60 b0 17",
    "version_bytes": "00 00 04 05",
    "framing": "two-byte big-endian chunks terminated by 00 00",
    "packstream": {
        "HELLO": {"signature": "01", "fields": ["metadata"]},
        "RUN": {"signature": "10", "fields": ["query", "parameters", "extra"]},
        "PULL": {"signature": "3f", "fields": ["extra"]},
    },
    "query": BOLT_QUERY,
    "relation": "ASSET_WORK",
    "association": "ASC-CRR-4417",
}

RELATION_RESPONSE = {
    "record_id": "REL-ASC-CRR-4417-R3",
    "revision": 3,
    "association": "ASC-CRR-4417",
    "relation": "ASSET_WORK",
    "asset": "AST-CRR-017",
    "work_order": "WO-CRR-4417",
}

REPORTING_CONTRACT = {
    "schema": "arwc.reporting-checkpoint/v1",
    "checkpoint": "REH-REPORT-34",
    "view": {
        "refresh_interval_seconds": 300,
        "required": [
            "checkpoint", "consumer", "consumer_revision", "source",
            "estimate", "refresh_interval_seconds", "raw_observations",
        ],
    },
    "decision": {
        "unit": "ML",
        "freshness_seconds": 40,
        "variance_limit_ml": 1.2,
        "required": [
            "view", "checkpoint", "unit", "freshness_seconds", "source_set",
            "unaffected", "meter_reserve_ml", "variance_limit_ml",
        ],
    },
    "handover": {"status": "consistent"},
}

LINEAGE = {
    "record_id": "LIN-AST-CRR-017-R8",
    "revision": 8,
    "legacy": "CRR-OG-LEGACY-2",
    "outlet_group": "OG-CRR-02",
    "current_asset": "AST-CRR-017",
    "archive": "ARC-COLD-CRR-2019",
}


class BoltError(ValueError):
    pass


def unpack_value(data: bytes, offset: int = 0) -> tuple[object, int]:
    if offset >= len(data):
        raise BoltError("truncated PackStream value")
    marker = data[offset]
    offset += 1
    if marker <= 0x7F:
        return marker, offset
    if marker >= 0xF0:
        return marker - 256, offset
    if 0x80 <= marker <= 0x8F:
        length = marker & 0x0F
        end = offset + length
        if end > len(data):
            raise BoltError("truncated PackStream string")
        try:
            return data[offset:end].decode(), end
        except UnicodeDecodeError as error:
            raise BoltError("invalid PackStream UTF-8") from error
    if marker == 0xD0:
        if offset >= len(data):
            raise BoltError("truncated PackStream string length")
        length = data[offset]
        offset += 1
        end = offset + length
        if end > len(data):
            raise BoltError("truncated PackStream string")
        try:
            return data[offset:end].decode(), end
        except UnicodeDecodeError as error:
            raise BoltError("invalid PackStream UTF-8") from error
    if marker == 0xD1:
        if offset + 2 > len(data):
            raise BoltError("truncated PackStream string length")
        length = int.from_bytes(data[offset:offset + 2], "big")
        offset += 2
        end = offset + length
        if end > len(data):
            raise BoltError("truncated PackStream string")
        try:
            return data[offset:end].decode(), end
        except UnicodeDecodeError as error:
            raise BoltError("invalid PackStream UTF-8") from error
    if 0x90 <= marker <= 0x9F:
        values: list[object] = []
        for _ in range(marker & 0x0F):
            value, offset = unpack_value(data, offset)
            values.append(value)
        return values, offset
    if 0xA0 <= marker <= 0xAF:
        values: dict[str, object] = {}
        for _ in range(marker & 0x0F):
            key, offset = unpack_value(data, offset)
            value, offset = unpack_value(data, offset)
            if not isinstance(key, str):
                raise BoltError("PackStream map key is not a string")
            values[key] = value
        return values, offset
    if 0xB0 <= marker <= 0xBF:
        if offset >= len(data):
            raise BoltError("truncated PackStream structure")
        signature = data[offset]
        offset += 1
        fields: list[object] = []
        for _ in range(marker & 0x0F):
            value, offset = unpack_value(data, offset)
            fields.append(value)
        return {"signature": signature, "fields": fields}, offset
    if marker == 0xC0:
        return None, offset
    if marker == 0xC2:
        return False, offset
    if marker == 0xC3:
        return True, offset
    if marker == 0xC8:
        if offset >= len(data):
            raise BoltError("truncated PackStream integer")
        return struct.unpack("b", data[offset:offset + 1])[0], offset + 1
    raise BoltError("unsupported PackStream marker")


def bolt_messages(exchange: bytes) -> list[dict[str, object]]:
    if len(exchange) < 20 or exchange[:4] != BOLT_MAGIC:
        raise BoltError("Bolt magic does not match")
    proposals = [exchange[index:index + 4] for index in range(4, 20, 4)]
    if BOLT_54 not in proposals:
        raise BoltError("Bolt 5.4 was not proposed")
    messages: list[dict[str, object]] = []
    offset = 20
    while offset < len(exchange):
        payload = bytearray()
        while True:
            if offset + 2 > len(exchange):
                raise BoltError("truncated Bolt chunk")
            length = int.from_bytes(exchange[offset:offset + 2], "big")
            offset += 2
            if length == 0:
                break
            if offset + length > len(exchange):
                raise BoltError("truncated Bolt payload")
            payload.extend(exchange[offset:offset + length])
            offset += length
        value, used = unpack_value(bytes(payload))
        if used != len(payload) or not isinstance(value, dict) or "signature" not in value:
            raise BoltError("Bolt message is not one PackStream structure")
        messages.append(value)
    if [value["signature"] for value in messages] != [0x01, 0x10, 0x3F]:
        raise BoltError("expected HELLO, RUN, and PULL")
    hello, run, pull = messages
    if (len(hello["fields"]) != 1 or not isinstance(hello["fields"][0], dict) or
            not isinstance(hello["fields"][0].get("user_agent"), str)):
        raise BoltError("HELLO metadata is incomplete")
    if (len(run["fields"]) != 3 or run["fields"][0] != BOLT_QUERY or
            not isinstance(run["fields"][1], dict) or not isinstance(run["fields"][2], dict)):
        raise BoltError("RUN fields do not match the relation contract")
    if len(pull["fields"]) != 1 or not isinstance(pull["fields"][0], dict):
        raise BoltError("PULL fields do not match the relation contract")
    return messages


def pack_value(value: object) -> bytes:
    if value is None:
        return b"\xc0"
    if value is False:
        return b"\xc2"
    if value is True:
        return b"\xc3"
    if isinstance(value, int) and -16 <= value < 128:
        return bytes([value & 0xFF])
    if isinstance(value, str):
        encoded = value.encode()
        if len(encoded) < 16:
            return bytes([0x80 + len(encoded)]) + encoded
        if len(encoded) < 256:
            return b"\xd0" + bytes([len(encoded)]) + encoded
        return b"\xd1" + len(encoded).to_bytes(2, "big") + encoded
    if isinstance(value, list):
        if len(value) >= 16:
            raise BoltError("response list is too long")
        return bytes([0x90 + len(value)]) + b"".join(pack_value(item) for item in value)
    if isinstance(value, dict):
        if len(value) >= 16:
            raise BoltError("response map is too large")
        return bytes([0xA0 + len(value)]) + b"".join(
            pack_value(str(key)) + pack_value(item) for key, item in value.items()
        )
    raise BoltError("unsupported response value")


def pack_struct(signature: int, *fields: object) -> bytes:
    return bytes([0xB0 + len(fields), signature]) + b"".join(pack_value(field) for field in fields)


def chunk(payload: bytes) -> bytes:
    return len(payload).to_bytes(2, "big") + payload + b"\x00\x00"


def bolt_response(record: dict[str, object]) -> str:
    values = [value for key, value in record.items() if key != "revision"]
    exchange = BOLT_54
    exchange += chunk(pack_struct(0x70, {"server": "ARWC-Relation/5.4"}))
    exchange += chunk(pack_struct(0x70, {"fields": list(record)}))
    exchange += chunk(pack_struct(0x71, values))
    exchange += chunk(pack_struct(0x70, {"has_more": False}))
    return base64.b64encode(exchange).decode()


def atomic_json(path: pathlib.Path, value: object) -> None:
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


def initialize() -> None:
    if not STATE.exists():
        atomic_json(STATE, {
            "query_definition_observed": False,
            "adjustment_observed": False,
            "reconciliation_copy_created": False,
            "allocation_observed": False,
            "meter_observed": False,
            "reserve_reconciled": False,
            "relation_contract_observed": False,
            "relation_exchange_observed": False,
            "lineage_observed": False,
            "diagnostic_estimate_observed": False,
            "reporting_view_observed": False, "reporting_decision_observed": False,
            "reporting_handover_observed": False, "reporting_view_response": None,
            "reporting_decision_response": None, "reporting_handover_response": None,
        })
    else:
        state = load_state()
        changed = False
        for key in (
            "allocation_observed", "meter_observed", "reserve_reconciled",
            "relation_contract_observed", "relation_exchange_observed", "lineage_observed",
            "diagnostic_estimate_observed",
            "reporting_view_observed", "reporting_decision_observed", "reporting_handover_observed",
        ):
            if key not in state:
                state[key] = False
                changed = True
        for key in ("reporting_view_response",
                    "reporting_decision_response", "reporting_handover_response"):
            if key not in state:
                state[key] = None
                changed = True
        if changed:
            save_state(state)
    AUDIT.touch(mode=0o600, exist_ok=True)
    os.chmod(AUDIT, 0o600)


def load_state() -> dict[str, object]:
    return json.loads(STATE.read_text(encoding="utf-8"))


def save_state(value: dict[str, object]) -> None:
    atomic_json(STATE, value)


def relation_prerequisite() -> bool:
    if load_state().get("reserve_reconciled"):
        return True
    try:
        evidence = json.loads(BUSINESS_RELATION_EVIDENCE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return evidence == {
        "association": "ASC-CRR-4417",
        "asset": "AST-CRR-017",
        "record_id": "ASSOC-CRR-4417-R6",
    }


def load_evidence(path: pathlib.Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def ot_read_prerequisite() -> bool:
    expected = {
        "corporate.json": ("OT-READ-CORPORATE-R21", "corporate-integration"),
        "contractor.json": ("OT-READ-CONTRACTOR-R21", "contractor-field"),
    }
    for name, (record_id, branch) in expected.items():
        evidence = load_evidence(OT_READ_EVIDENCE / name)
        if (evidence is not None and evidence.get("record_id") == record_id and
                evidence.get("branch") == branch and
                evidence.get("scope") == "OG-CRR-02/read" and
                isinstance(evidence.get("token_sha256"), str)):
            return True
    return False


def process_interpretation_prerequisite() -> bool:
    if not load_state().get("reserve_reconciled"):
        return False
    integration = load_evidence(INTEGRATION_EVIDENCE)
    return bool(
        integration is not None and
        integration.get("record_id") == "REC-CRR-DP3-17" and
        integration.get("planning_window") == "ALLOC-2026-DP3"
    )


def append_audit(action: str, result: dict[str, object], correlation: str | None = None) -> str:
    correlation = str(uuid.uuid4()) if correlation is None else correlation
    event = {
        "audit_id": correlation,
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tenant": "arwc",
        "principal": "nadia.corvane",
        "action": action,
        "object": result.get("record_id"),
        "revision": result.get("revision"),
        "result_digest": hashlib.sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return correlation


def database() -> psycopg2.extensions.connection:
    return psycopg2.connect(dbname="arwc", user="svc-planner-query", host="/var/run/postgresql")


def row_record(row: tuple[object, ...]) -> dict[str, object]:
    return {
        "record_id": row[0],
        "district": row[1],
        "period": row[2],
        "amount_ml": float(row[3]) if isinstance(row[3], Decimal) else row[3],
        "detail": row[4],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Planning-Data/7.0"
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

    def authorized(self) -> bool:
        if self.headers.get("X-ARWC-Tenant", "arwc") != "arwc":
            self.send_json(403, {"error": "session is not valid for this tenant"})
            return False
        supplied = self.headers.get("Authorization", "")
        if not supplied.startswith("Bearer "):
            self.send_json(403, {"error": "corporate session required"})
            return False
        digest = hashlib.sha256(supplied[7:].encode()).hexdigest()
        if not hmac.compare_digest(digest, TOKEN_HASH.read_text().strip()):
            self.send_json(403, {"error": "corporate session required"})
            return False
        planner = self.headers.get("X-ARWC-Planner-Session", "")
        try:
            evidence = json.loads(PLANNER_EVIDENCE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.send_json(403, {"error": "planner session required"})
            return False
        if (evidence.get("record_id") != "PLN-SESS-OAUTH-882" or
                evidence.get("scope") != "planning-records" or
                not isinstance(evidence.get("expires_at_epoch"), int) or
                evidence["expires_at_epoch"] <= int(time.time()) or
                not hmac.compare_digest(hashlib.sha256(planner.encode()).hexdigest(),
                                        str(evidence.get("token_sha256")))):
            self.send_json(403, {"error": "planner session required"})
            return False
        return True

    def process_authorized(self) -> bool:
        if self.headers.get("X-ARWC-Tenant", "arwc") != "arwc":
            self.send_json(403, {"error": "session is not valid for this tenant"})
            return False
        supplied = self.headers.get("Authorization", "")
        if not supplied.startswith("Bearer "):
            self.send_json(403, {"error": "scoped process-read session required"})
            return False
        digest = hashlib.sha256(supplied[7:].encode()).hexdigest()
        for name in ("corporate.json", "contractor.json"):
            evidence = load_evidence(OT_READ_EVIDENCE / name)
            if (evidence is not None and evidence.get("scope") == "OG-CRR-02/read" and
                    hmac.compare_digest(digest, str(evidence.get("token_sha256", "")))):
                return True
        self.send_json(403, {"error": "scoped process-read session required"})
        return False

    def body(self) -> dict[str, object] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 16384:
                raise ValueError
            result = json.loads(self.rfile.read(length))
            if not isinstance(result, dict):
                raise ValueError
            return result
        except (ValueError, json.JSONDecodeError):
            self.send_json(409, {"error": "invalid request"})
            return None

    def accepted(self, action: str, result: dict[str, object], status: int = 200,
                 extra: dict[str, object] | None = None,
                 correlation: str | None = None) -> None:
        response: dict[str, object] = {
            "audit_id": append_audit(action, result, correlation), "record": result,
        }
        if extra:
            response.update(extra)
        self.send_json(status, response)

    def process_proxy(self) -> None:
        path = urlsplit(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        if path not in PROCESS_PATHS or length < 0 or length > 65536:
            self.send_json(404, {"error": "record not found"})
            return
        data = self.rfile.read(length) if length else None
        headers = {
            "Authorization": self.headers.get("Authorization", ""),
            "X-ARWC-Tenant": self.headers.get("X-ARWC-Tenant", "arwc"),
            "Host": "process-view.arwc.test",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        outbound = urllib.request.Request(
            "https://10.77.62.20" + path, data=data, headers=headers, method=self.command,
        )
        context = ssl.create_default_context(cafile="/run/arwc-tls/ca.crt")
        try:
            response = urllib.request.urlopen(outbound, context=context, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        except OSError:
            self.send_json(409, {"error": "process gateway is unavailable"})
            return
        try:
            payload = json.loads(response.read())
        except json.JSONDecodeError:
            self.send_json(409, {"error": "process gateway returned an invalid response"})
            return
        self.send_json(response.status, payload)

    def w34_internal(self, path: str, request: dict[str, object]) -> tuple[int, dict[str, object]]:
        data = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
        outbound = urllib.request.Request(
            "https://10.77.62.20" + path, data=data,
            headers={"Content-Type": "application/json", "X-ARWC-Internal": "planning-data-reporting",
                     "X-ARWC-Tenant": "arwc"}, method="POST",
        )
        context = ssl.create_default_context(cafile="/run/arwc-tls/ca.crt")
        try:
            response = urllib.request.urlopen(outbound, context=context, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        except OSError:
            return 409, {"error": "reporting dependency unavailable"}
        try: result = json.loads(response.read())
        except json.JSONDecodeError: return 409, {"error": "reporting dependency returned invalid data"}
        return response.status, result

    def _serve_client_document(self) -> bool:
        if urlsplit(self.path).path != "/.well-known/arwc-client":
            return False
        reports = _load_reports_state()
        # planning.saved-query, planning.query-run, and planning.allocation-ledger
        # route to native Metabase. The participant uses the W06.3 Metabase session
        # (X-Metabase-Session header) against the real Metabase/PostgreSQL stack.
        saved_query_template = _metabase_card_url(
            reports, "qry_reserve_r7_id", "https://reports.arwc.test/api/card/qry-reserve-r7"
        )
        query_run_template = reports.get("metabase_url", "https://reports.arwc.test") + "/api/dataset"
        alloc_ledger_template = _metabase_card_url(
            reports, "alloc_dp3_question_id", "https://reports.arwc.test/api/card/alloc-dp3-current"
        )
        meter_alloc_template = _metabase_card_url(
            reports, "meter_dp3_question_id", "https://reports.arwc.test/api/card/meter-dp3-current"
        )
        alloc_discrepancy_template = _metabase_card_url(
            reports, "recon_dp3_question_id", "https://reports.arwc.test/api/card/recon-dp3-current"
        )
        report_sources_template = _metabase_card_url(
            reports, "sel_dp3_question_id", "https://reports.arwc.test/api/card/sel-crr-dp3-7"
        )
        report_row_ext_template = _metabase_card_url(
            reports, "ext_dp3_question_id", "https://reports.arwc.test/api/card/ext-excerpts-dp3"
        )
        # W11.1: planning.relation-schema routes to native Metabase question on relation_contracts.
        self.send_json(200, {
            "schema": "arwc.client-documents/v1",
            "service": "planning-data.arwc.test",
            "title": "Planning query, allocation, and integration service",
            "routes": [
                {
                    "key": "planning.saved-query",
                    "method": "GET",
                    "template": saved_query_template
                },
                {
                    "key": "planning.query-run",
                    "method": "POST",
                    "template": query_run_template
                },
                {
                    "key": "planning.allocation-ledger",
                    "method": "GET",
                    "template": alloc_ledger_template
                },
                {
                    "key": "planning.meter-allocation",
                    "method": "GET",
                    "template": meter_alloc_template
                },
                {
                    "key": "planning.allocation-discrepancy",
                    "method": "GET",
                    "template": alloc_discrepancy_template
                },
                {
                    "key": "business.report-sources",
                    "method": "GET",
                    "template": report_sources_template
                },
                {
                    "key": "business.report-row-external",
                    "method": "GET",
                    "template": report_row_ext_template
                },
                {
                    "key": "business.report-document",
                    "method": "GET",
                    "template": "https://documents.arwc.test/remote.php/dav/files/jules.orswick@veybridge.test/PLN-MER-DP3-R6.json"
                },
                {
                    "key": "planning.live-feed",
                    "method": "GET",
                    "template": "https://read-data.arwc.test/api/operating-history"
                },
                {
                    "key": "planning.relation-schema",
                    "method": "GET",
                    "template": _metabase_card_url(reports, "relproto_question_id", "https://reports.arwc.test/api/card/relproto-crr-r3")
                },
                {
                    "key": "planning.relation-exchange",
                    "method": "GET",
                    "template": _metabase_card_url(reports, "rel_query_question_id", "https://reports.arwc.test/api/card/rel-query-crr-r3")
                },
                {
                    "key": "planning.asset-lineage",
                    "method": "GET",
                    "template": "https://planning-data.arwc.test/api/asset-lineage/current"
                },
                {
                    "key": "planning.integration-session",
                    "method": "POST",
                    "template": "https://planning-data.arwc.test/api/integration-sessions"
                },
                {
                    "key": "planning.reporting-contract",
                    "method": "GET",
                    "template": "https://planning-data.arwc.test/api/reporting-contracts/current"
                },
                {
                    "key": "planning.reporting-view",
                    "method": "POST",
                    "template": "https://planning-data.arwc.test/api/reporting-submissions/current/result"
                },
                {
                    "key": "planning.planning-bid",
                    "method": "POST",
                    "template": "https://planning-data.arwc.test/api/planning-bids"
                },
                {
                    "key": "planning.planning-handover",
                    "method": "POST",
                    "template": "https://planning-data.arwc.test/api/planning-bids/current"
                }
            ],
            "related": [
                "https://retained-archive.arwc.test/.well-known/arwc-client",
                "https://process-view.arwc.test/.well-known/arwc-client",
            ],
        })
        return True

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if self.headers.get("Host", "").split(":", 1)[0] == "process-view.arwc.test":
            if path in PROCESS_PATHS:
                self.process_proxy()
            else:
                self.send_json(404, {"error": "record not found"})
            return
        if self._serve_client_document():
            return
        if not self.authorized():
            return
        if path == "/api/allocation-ledgers/current":
            self.allocation()
            return
        if path == "/api/meter-allocations/current":
            self.meter()
            return
        if path == "/api/allocation-discrepancies/current":
            # W09.3: canned tolerance facade removed. The reconciliation is a real
            # native Metabase question on reserve_reconciliation view in corporate-db.
            self.send_json(410, {"error": "allocation-discrepancies endpoint retired; use planning.allocation-discrepancy route"})
            return
        if path == "/api/relation-schemas/current":
            # W11.1 Bolt facade removed. The relation contract RELPROTO-CRR-R3 is now
            # a native Metabase question on relation_contracts in corporate-db.
            # Use planning.relation-schema route in the client doc.
            self.send_json(410, {"error": "relation-schemas endpoint retired; use planning.relation-schema route"})
            return
        if path == "/api/reporting-contracts/current":
            self.send_json(200, REPORTING_CONTRACT)
            return
        if path != "/api/saved-queries/current":
            self.send_json(404, {"error": "record not found"})
            return
        state = load_state()
        state["query_definition_observed"] = True
        save_state(state)
        self.accepted("saved-query-read", DEFINITION)

    def do_POST(self) -> None:
        if urlsplit(self.path).path == "/internal/diagnostic-estimate":
            if (self.headers.get("X-ARWC-Internal") != "data-bridge-r27" or
                    self.headers.get("X-ARWC-Tenant") != "arwc" or
                    self.client_address[0] != "10.77.62.20"):
                self.send_json(403, {"error": "integration service context required"})
                return
            request = self.body()
            if request is None:
                return
            expected = {
                "source": "DPG-CRR-CINDER", "consumer": "PLAN-CONSUMER-R8",
                "allocation_case": "ALLOC-CASE-CRR-33", "integrity": "VER-ROT128-R3",
                "digest": "6e41f63685a0056b6feeb8fa96560060",
                "estimate": {"Cairn Reach": 13.4, "North": 8.1, "Merewick": 7.65},
                "quality": "valid", "raw_process_observations_changed": False,
                "independent_instruments_changed": False,
            }
            program_sha256 = request.get("program_sha256")
            if (set(request) != set(expected) | {"program_sha256"} or
                    any(request.get(key) != value for key, value in expected.items()) or
                    not isinstance(program_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", program_sha256)):
                self.send_json(409, {"error": "diagnostic estimate binding rejected"})
                return
            state = load_state(); state["diagnostic_estimate_observed"] = True; save_state(state)
            result = {
                "record_id": "PLAN-CONSUMER-R8", "revision": 8,
                "source": "DPG-CRR-CINDER", "allocation_case": "ALLOC-CASE-CRR-33",
                "program_sha256": program_sha256, "integrity": "VER-ROT128-R3",
                "estimate": expected["estimate"], "quality": "valid",
                "raw_process_observations_changed": False,
                "independent_instruments_changed": False,
            }
            atomic_json(ROOT / "results/PLAN-CONSUMER-R8.json", result)
            self.accepted("diagnostic-estimate-consumed", result, 201)
            return
        path = urlsplit(self.path).path
        if self.headers.get("Host", "").split(":", 1)[0] == "process-view.arwc.test":
            if path in PROCESS_PATHS:
                self.process_proxy()
            else:
                self.send_json(404, {"error": "record not found"})
            return
        if not self.authorized():
            return
        request = self.body()
        if request is None:
            return
        if path == "/api/query-runs":
            # W07.3: the canned reconcile gate is removed. arwc_reconcile_copy is only
            # invokable via the real quoted-identifier injection through native Metabase
            # /api/dataset against corporate-db under planning_reader.
            self.query_report(request)
        elif path == "/api/integration-sessions":
            self.integration(request)
        elif path == "/api/relation-exchanges":
            # W11.2 Bolt facade removed. Use planning.relation-exchange route
            # (suppliers.arwc.test/api/resource/Task) with Jules credentials and
            # the W11.1 query template to find ASC-CRR-4417.
            self.send_json(410, {"error": "relation-exchanges endpoint retired; use planning.relation-exchange route"})
        elif path == "/api/asset-lineage/current":
            # W11.3 Bolt lineage facade removed. The asset lineage LIN-AST-CRR-017-R8
            # is behind the SECURITY DEFINER get_asset_lineage() function in corporate-db.
            # Reached via UNION injection calling the function with the W11.2 asset identity.
            self.send_json(410, {"error": "asset-lineage endpoint retired; use the W11.2 injection surface with get_asset_lineage()"})
        elif path == "/api/reporting-submissions/current/result":
            self.w34_view(request)
        elif path == "/api/planning-bids":
            self.w34_decision(request)
        elif path == "/api/planning-bids/current":
            self.w34_handover(request)
        else:
            self.send_json(404, {"error": "record not found"})

    def w34_view(self, request: dict[str, object]) -> None:
        if not process_interpretation_prerequisite():
            self.send_json(403, {"error": "current process interpretation evidence required"}); return
        source = request.get("source")
        expected = {"checkpoint": "REH-REPORT-34", "consumer": "PLAN-CONSUMER-R8",
                    "consumer_revision": 8, "source": source,
                    "estimate": {"Cairn Reach": 13.4, "North": 8.1, "Merewick": 7.65},
                    "refresh_interval_seconds": 300,
                    "raw_observations": ["MTR-CRR-DP3-R12", "FIT-CRR-204A", "FIT-CRR-204B"]}
        if request != expected or source not in {"ALLOC-CASE-CRR-33", "DPG-CRR-CINDER"}:
            self.send_json(409, {"error": "planning consumer input binding rejected"}); return
        if source == "DPG-CRR-CINDER":
            capability = load_evidence(ROOT / "results/PLAN-CONSUMER-R8.json")
        else:
            status, response = self.w34_internal("/internal/handover-estimates", {
                "source": source, "consumer": "PLAN-CONSUMER-R8",
            })
            if status != 200:
                self.send_json(status if status in {403, 409} else 409, response); return
            capability = response.get("record")
        if (not isinstance(capability, dict) or capability.get("record_id") not in {
                "PLAN-CONSUMER-R8", "ALLOC-CASE-CRR-33"} or
                capability.get("estimate") != expected["estimate"] or capability.get("quality") != "valid" or
                capability.get("raw_process_observations_changed") is not False or
                capability.get("independent_instruments_changed") is not False):
            self.send_json(403, {"error": "accepted controlled estimate required"}); return
        state = load_state(); existing = state.get("reporting_view_response")
        if isinstance(existing, dict):
            if existing.get("record", {}).get("source") == source: self.send_json(201, existing)
            else: self.send_json(409, {"error": "checkpoint already refreshed from another source"})
            return
        correlation = str(uuid.uuid4())
        record = {"record_id": "VIEW-CRR-34", "revision": 1, "request_correlation": correlation,
                  "checkpoint": "REH-REPORT-34", "consumer": "PLAN-CONSUMER-R8",
                  "consumer_revision": 8, "source": source, "source_record": capability["record_id"],
                  "estimate": expected["estimate"], "unit": "ML", "quality": "valid",
                  "refresh_interval_seconds": 300, "raw_observations": expected["raw_observations"],
                  "raw_process_observations_changed": False, "independent_instruments_changed": False}
        response = {"audit_id": append_audit("reporting-view-created", record, correlation), "record": record}
        state["reporting_view_observed"] = True; state["reporting_view_response"] = response; save_state(state)
        atomic_json(ROOT / "results/VIEW-CRR-34.json", record); self.send_json(201, response)

    def w34_decision(self, request: dict[str, object]) -> None:
        expected = {"view": "VIEW-CRR-34", "checkpoint": "REH-REPORT-34", "unit": "ML",
                    "freshness_seconds": 40, "source_set": ["Cairn Reach", "North", "Merewick"],
                    "unaffected": {"North": 8.1, "Merewick": 7.65},
                    "meter_reserve_ml": 12.4, "variance_limit_ml": 1.2}
        state = load_state(); view_response = state.get("reporting_view_response")
        if not isinstance(view_response, dict):
            self.send_json(403, {"error": "refreshed planning view required"}); return
        source_set = request.get("source_set")
        if (set(request) != set(expected) or
                any(request.get(key) != value for key, value in expected.items()
                    if key != "source_set") or
                not isinstance(source_set, list) or
                len(source_set) != len(expected["source_set"]) or
                not all(isinstance(item, str) for item in source_set) or
                set(source_set) != set(expected["source_set"])):
            self.send_json(409, {"error": "planning consistency binding rejected"}); return
        existing = state.get("reporting_decision_response")
        if isinstance(existing, dict): self.send_json(201, existing); return
        view = view_response.get("record"); estimate = view.get("estimate") if isinstance(view, dict) else None
        variance = None if not isinstance(estimate, dict) else round(float(estimate["Cairn Reach"]) - 12.4, 2)
        if variance is None or variance >= 1.2 or estimate.get("North") != 8.1 or estimate.get("Merewick") != 7.65:
            self.send_json(409, {"error": "planning view failed consistency checks"}); return
        correlation = str(uuid.uuid4())
        checks = {"unit_valid": True, "freshness_valid": True, "source_set_valid": True,
                  "unaffected_district_totals_valid": True, "variance_valid": True}
        record = {"record_id": "DECISION-CRR-34", "revision": 1, "request_correlation": correlation,
                  "checkpoint": "REH-REPORT-34", "view": "VIEW-CRR-34",
                  "ordinary_estimate_ml": 12.4, "controlled_estimate_ml": 13.4,
                  "meter_reserve_ml": 12.4, "variance_ml": variance, "variance_limit_ml": 1.2,
                  "ordinary_decision": "ALLOC-HOLD-R3", "decision": "ALLOC-EXPAND-R2",
                  "decision_changed": True, "consistency": "accepted", "checks": checks,
                  "unaffected": expected["unaffected"]}
        response = {"audit_id": append_audit("reporting-decision-created", record, correlation), "record": record}
        state["reporting_decision_observed"] = True; state["reporting_decision_response"] = response; save_state(state)
        atomic_json(ROOT / "results/DECISION-CRR-34.json", record); self.send_json(201, response)

    def w34_handover(self, request: dict[str, object]) -> None:
        state = load_state()
        if not isinstance(state.get("reporting_decision_response"), dict):
            self.send_json(403, {"error": "accepted changed planning decision required"}); return
        schedule = request.get("schedule")
        evaluated = None if not isinstance(schedule, dict) else reporting_schedule.evaluate_schedule(
            schedule.get("reservoir_release_m3s"), schedule.get("alternate_supply_m3s"),
            schedule.get("demand_m3s"))
        expected_keys = {"checkpoint", "view", "decision", "control_client", "schedule", "handover"}
        if (set(request) != expected_keys or not isinstance(request.get("control_client"), str) or
                request.get("checkpoint") != "REH-REPORT-34" or request.get("view") != "VIEW-CRR-34" or
                request.get("decision") != "ALLOC-EXPAND-R2" or
                request.get("handover") != {"estimate_ml": 13.4, "unit": "ML", "status": "consistent",
                                                "interval": "ALLOC-2026-DP3"} or
                evaluated is None or evaluated.get("reservoir_volume_ml") != 0.81 or
                evaluated.get("final_buffer_m3") != 180.0):
            self.send_json(409, {"error": "reporting checkpoint request rejected"}); return
        existing = state.get("reporting_handover_response")
        if isinstance(existing, dict):
            if existing.get("record", {}).get("schedule_sha256") == evaluated["schedule_sha256"]:
                self.send_json(201, existing)
            else: self.send_json(409, {"error": "another schedule already owns this reporting checkpoint"})
            return
        correlation = str(uuid.uuid4())
        status, observed = self.w34_internal("/internal/control-handovers", {
            "correlation": correlation, "request": request, "evaluation": evaluated,
        })
        instrument = observed.get("record")
        if (status != 201 or observed.get("audit_id") != correlation or not isinstance(instrument, dict) or
                instrument.get("record_id") != "INST-REPORT-CRR-34" or
                instrument.get("measured_release_ml") != 0.81 or instrument.get("reserve_after_ml") != 11.59):
            self.send_json(status if status in {403, 409} else 409, observed); return
        record = {"record_id": "REPORT-CRR-34", "revision": 1, "request_correlation": correlation,
                  "checkpoint": "REH-REPORT-34", "interval": "ALLOC-2026-DP3",
                  "view": "VIEW-CRR-34", "decision_record": "DECISION-CRR-34",
                  "ordinary_decision": "ALLOC-HOLD-R3", "decision": "ALLOC-EXPAND-R2",
                  "planning_handover_reserve_ml": 13.4, "report_consistency": "accepted",
                  "independent_release_ml": 0.81, "independent_reserve_before_ml": 12.4,
                  "independent_reserve_after_ml": 11.59, "reported_truth_difference_ml": 1.81,
                  "schedule_sha256": evaluated["schedule_sha256"],
                  "live_process_state_changed": False, "prior_evidence_changed": False}
        response = {"audit_id": append_audit("reporting-handover-created", record, correlation),
                    "instrument_audit_id": observed["instrument_audit_id"],
                    "reservoir_audit_id": observed["reservoir_audit_id"], "record": record,
                    "instrument_observation": instrument,
                    "reservoir_observation": observed["reservoir_observation"]}
        state["reporting_handover_observed"] = True; state["reporting_handover_response"] = response; save_state(state)
        atomic_json(ROOT / "results/REPORT-CRR-34.json", record); self.send_json(201, response)

    def relation_exchange(self, request: dict[str, object], *, lineage: bool) -> None:
        state = load_state()
        if not state["relation_contract_observed"]:
            self.send_json(403, {"error": "relation contract has not been read"})
            return
        if lineage and not state["relation_exchange_observed"]:
            self.send_json(403, {"error": "accepted relation exchange is required"})
            return
        encoded = request.get("exchange")
        if not isinstance(encoded, str) or len(encoded) > 12288:
            self.send_json(409, {"error": "Bolt exchange is missing"})
            return
        try:
            raw = base64.b64decode(encoded, validate=True)
            messages = bolt_messages(raw)
        except (binascii.Error, BoltError):
            self.send_json(409, {"error": "Bolt exchange was rejected"})
            return
        parameters = messages[1]["fields"][1]
        assert isinstance(parameters, dict)
        if parameters.get("asset") != "AST-CRR-017":
            self.send_json(409, {"error": "asset key does not match"})
            return
        if parameters.get("association") != "ASC-CRR-4417":
            self.send_json(409, {"error": "association does not match"})
            return
        expected_ou = LINEAGE_OU if lineage else "ASSET_WORK"
        if parameters.get("certificate_ou") != expected_ou:
            self.send_json(409, {"error": "relationship type was not accepted"})
            return
        if lineage:
            atomic_json(ARCHIVE_EVIDENCE, LINEAGE)
            os.chown(ARCHIVE_EVIDENCE, -1, grp.getgrnam("arwc-archive-source").gr_gid)
            os.chmod(ARCHIVE_EVIDENCE, 0o640)
            state["lineage_observed"] = True
            save_state(state)
            self.accepted(
                "asset-lineage-created", LINEAGE, 201,
                extra={"bolt_response": bolt_response(LINEAGE)},
            )
        else:
            state["relation_exchange_observed"] = True
            save_state(state)
            self.accepted(
                "relation-exchange-created", RELATION_RESPONSE, 201,
                extra={"bolt_response": bolt_response(RELATION_RESPONSE)},
            )

    def allocation(self) -> None:
        with database() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT record_id,revision,district,asset,planning_window,committed_ml,unit "
                "FROM allocation_ledger WHERE record_id=%s", (ALLOCATION_ID,),
            )
            row = cursor.fetchone()
        result = {
            "record_id": row[0], "revision": row[1], "district": row[2], "asset": row[3],
            "planning_window": row[4], "committed_ml": float(row[5]), "unit": row[6],
        }
        state = load_state()
        state["allocation_observed"] = True
        save_state(state)
        self.accepted("allocation-ledger-read", result)

    def meter(self) -> None:
        with database() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT record_id,revision,planning_window,usable_reserve_ml,unit,instrument_a,instrument_b "
                "FROM meter_export WHERE record_id=%s", (METER_ID,),
            )
            row = cursor.fetchone()
        result = {
            "record_id": row[0], "revision": row[1], "planning_window": row[2],
            "usable_reserve_ml": float(row[3]), "unit": row[4],
            "instruments": [row[5], row[6]],
        }
        state = load_state()
        state["meter_observed"] = True
        save_state(state)
        self.accepted("meter-allocation-read", result)

    # reserve_reconciliation() removed: W09.3 facade with 1.0/0.4 tolerance
    # accept is gone. The real reconciliation is RECON-DP3-CURRENT on
    # reserve_reconciliation view in corporate-db, accessed via native Metabase.

    def integration(self, request: dict[str, object]) -> None:
        # W09.4: return operating-reader credentials for the live process feed.
        # The participant uses these with the planning.live-feed route
        # (read-data.arwc.test/api/operating-history) to get fresh OT observations.
        # Credentials are sourced from the bind-mounted ot-operating-reader.json.
        try:
            reader_creds = json.loads(pathlib.Path("/run/arwc-ot-reader.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.send_json(503, {"error": "integration gateway is unavailable"})
            return
        import base64 as _b64
        auth_header = "Basic " + _b64.b64encode(
            f"{reader_creds['username']}:{reader_creds['password']}".encode()
        ).decode()
        result = {
            "record_id": "INT-CRR-08",
            "revision": 8,
            "integration_id": "INT-CRR-08",
            "feed": "FEED-OG2-R21",
            "source_binding": request.get("source", "REC-CRR-DP3-17"),
            "credential_type": "Basic",
            "live_feed_url": "https://read-data.arwc.test/api/operating-history",
        }
        atomic_json(INTEGRATION_EVIDENCE, result)
        os.chown(INTEGRATION_EVIDENCE, -1, grp.getgrnam("arwc-integration").gr_gid)
        os.chmod(INTEGRATION_EVIDENCE, 0o640)
        self.accepted("integration-session-issued", result, 201,
                      {"authorization": auth_header})


    def query_report(self, request: dict[str, object]) -> None:
        state = load_state()
        if not state["query_definition_observed"]:
            self.send_json(403, {"error": "report definition has not been read"})
            return
        report_name = request.get("report_name")
        if not isinstance(report_name, str) or len(report_name) > 240 or ";" in report_name:
            self.send_json(409, {"error": "report identifier is not accepted"})
            return
        allowed_injection = (
            'reserve_report_current" UNION ALL SELECT record_id,district,period,amount_ml,detail '
            'FROM district_allocation_adjustment --'
        )
        if report_name not in {"reserve_report_current", allowed_injection}:
            self.send_json(403, {"error": "report is outside the planning scope"})
            return
        if re.search(r"\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|COPY|CALL)\b", report_name,
                     re.IGNORECASE):
            self.send_json(409, {"error": "query service is SELECT only"})
            return
        statement = f'SELECT record_id,district,period,amount_ml,detail FROM "{report_name}"'
        with database() as connection, connection.cursor() as cursor:
            cursor.execute(statement)
            records = [row_record(row) for row in cursor.fetchall()]
        if report_name == allowed_injection:
            protected = next(record for record in records if record["record_id"] == "ADJ-CRR-DP3-17")
            state["adjustment_observed"] = True
            save_state(state)
            self.accepted("archived-query-created", protected, 201,
                          {"statement": statement, "row_count": len(records)})
        else:
            self.accepted("archived-query-created", records[0], 201,
                          {"statement": statement, "row_count": 1})

    # reconcile() removed: the canned two-field gate against the embedded Postgres was
    # a facade for W07.3. The only valid invocation of arwc_reconcile_copy is the real
    # quoted-identifier injection through native Metabase /api/dataset against corporate-db.


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
