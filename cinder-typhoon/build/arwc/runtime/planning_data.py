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


ROOT = pathlib.Path("/var/lib/arwc-data")
STATE = ROOT / "state" / "planning.json"
AUDIT = ROOT / "audit" / "events.jsonl"
TOKEN_HASH = ROOT / "auth" / "corporate-session.sha256"
PLANNER_EVIDENCE = pathlib.Path("/run/arwc-planning-evidence/planner-session.json")
INTEGRATION_EVIDENCE = ROOT / "integration" / "W09-data.json"
ARCHIVE_EVIDENCE = ROOT / "archive" / "W11-lineage.json"
BUSINESS_RELATION_EVIDENCE = pathlib.Path("/run/arwc-business-relation/W02-association.json")
PROCESS_PATHS = {
    "/api/the-reservoir-s-present-tense", "/api/the-mode-the-plant-is-in",
    "/api/the-instrument-in-the-note", "/api/the-first-live-trace",
    "/api/the-tag-export", "/api/the-scale-kept-elsewhere",
    "/api/when-the-units-changed", "/api/which-outlet-answers",
    "/api/the-project-and-the-note", "/api/which-project-is-running",
    "/api/the-operating-envelope", "/api/conditions-before-movement",
    "/api/accepted-is-not-actuated", "/api/a-sequence-the-process-can-follow",
    "/api/the-diagnostic-nobody-retired", "/api/a-second-interpretation",
    "/api/the-hidden-check", "/api/a-map-from-the-old-diagnostic",
    "/api/the-viewer-in-the-delivery", "/api/the-machine-inside-the-viewer",
    "/api/the-decision-inside-the-sealed-project", "/api/the-reviewer-who-was-never-listed",
    "/api/a-measurement-with-side-effects", "/api/control-beyond-the-measurement",
    "/api/a-measurement-that-never-existed",
    "/api/two-kinds-of-answer", "/api/which-answer-comes-next",
    "/api/the-diagnostic-evidence-bundle", "/api/signed-by-someone-who-never-approved-it",
    "/api/what-the-image-kept", "/api/a-valid-maintenance-record",
    "/api/change-one-record-keep-the-rest",
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
        })
    else:
        state = load_state()
        changed = False
        for key in (
            "allocation_observed", "meter_observed", "reserve_reconciled",
            "relation_contract_observed", "relation_exchange_observed", "lineage_observed",
        ):
            if key not in state:
                state[key] = False
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


def append_audit(action: str, result: dict[str, object]) -> str:
    correlation = str(uuid.uuid4())
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
                 extra: dict[str, object] | None = None) -> None:
        response: dict[str, object] = {"audit_id": append_audit(action, result), "record": result}
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

    def do_GET(self) -> None:
        if (self.headers.get("Host", "").split(":", 1)[0] == "process-view.arwc.test" and
                urlsplit(self.path).path in PROCESS_PATHS):
            self.process_proxy()
            return
        if not self.authorized():
            return
        path = urlsplit(self.path).path
        if path == "/api/water-already-promised":
            self.allocation()
            return
        if path == "/api/the-meter-s-own-account":
            self.meter()
            return
        if path == "/api/the-missing-megalitre":
            self.reserve_reconciliation()
            return
        if path == "/api/the-relation-service-s-language":
            if not relation_prerequisite():
                self.send_json(403, {"error": "asset association or reconciled allocation is required"})
                return
            state = load_state()
            state["relation_contract_observed"] = True
            save_state(state)
            self.accepted("the-relation-service-s-language", RELATION_CONTRACT)
            return
        if path != "/api/the-query-the-planner-keeps":
            self.send_json(404, {"error": "record not found"})
            return
        state = load_state()
        state["query_definition_observed"] = True
        save_state(state)
        self.accepted("the-query-the-planner-keeps", DEFINITION)

    def do_POST(self) -> None:
        if (self.headers.get("Host", "").split(":", 1)[0] == "process-view.arwc.test" and
                urlsplit(self.path).path in PROCESS_PATHS):
            self.process_proxy()
            return
        if not self.authorized():
            return
        request = self.body()
        if request is None:
            return
        path = urlsplit(self.path).path
        if path == "/api/read-beyond-the-allowed-statement":
            self.query_report(request)
        elif path == "/api/the-database-does-more-than-read":
            self.reconcile(request)
        elif path == "/api/integration/from-the-report-to-the-live-feed":
            self.integration(request)
        elif path == "/api/an-exchange-the-backend-accepts":
            self.relation_exchange(request, lineage=False)
        elif path == "/api/the-asset-s-true-lineage":
            self.relation_exchange(request, lineage=True)
        else:
            self.send_json(404, {"error": "record not found"})

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
                "the-asset-s-true-lineage", LINEAGE, 201,
                extra={"bolt_response": bolt_response(LINEAGE)},
            )
        else:
            state["relation_exchange_observed"] = True
            save_state(state)
            self.accepted(
                "an-exchange-the-backend-accepts", RELATION_RESPONSE, 201,
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
        self.accepted("water-already-promised", result)

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
        self.accepted("the-meter-s-own-account", result)

    def reserve_reconciliation(self) -> None:
        state = load_state()
        if not state["allocation_observed"] or not state["meter_observed"]:
            self.send_json(403, {"error": "allocation ledger and meter export are required"})
            return
        with database() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT a.record_id,a.planning_window,a.committed_ml,a.unit,m.record_id,m.usable_reserve_ml,"
                "r.record_id,r.reported_ml,r.duplicate_transfer "
                "FROM allocation_ledger a JOIN meter_export m USING (planning_window) "
                "JOIN business_reserve_report r USING (planning_window) "
                "WHERE a.record_id=%s AND m.record_id=%s AND r.record_id=%s",
                (ALLOCATION_ID, METER_ID, REPORT_ID),
            )
            row = cursor.fetchone()
        committed, reserve, reported = Decimal(row[2]), Decimal(row[5]), Decimal(row[7])
        result = {
            "record_id": "REC-CRR-DP3-17",
            "revision": 17,
            "planning_window": row[1],
            "unit": row[3],
            "allocation_ledger": row[0],
            "meter_export": row[4],
            "business_report": row[6],
            "reported_ml": float(reported),
            "usable_reserve_ml": float(reserve),
            "committed_ml": float(committed),
            "overstatement_ml": float(reported - reserve),
            "uncommitted_margin_ml": float(reserve - committed),
            "duplicate_transfer": row[8],
            "asset": "AST-CRR-017",
            "outlet_group": "OG-CRR-02",
        }
        if result["overstatement_ml"] != 1.0 or result["uncommitted_margin_ml"] != 0.4:
            self.send_json(409, {"error": "reserve records do not reconcile"})
            return
        atomic_json(INTEGRATION_EVIDENCE, result)
        os.chown(INTEGRATION_EVIDENCE, -1, grp.getgrnam("arwc-integration").gr_gid)
        os.chmod(INTEGRATION_EVIDENCE, 0o640)
        state["reserve_reconciled"] = True
        save_state(state)
        self.accepted("the-missing-megalitre", result)

    def integration(self, request: dict[str, object]) -> None:
        state = load_state()
        if not state["reserve_reconciled"]:
            self.send_json(403, {"error": "reserve reconciliation is required"})
            return
        supplied = self.headers.get("X-ARWC-Integration-Session", "")
        if not supplied:
            self.send_json(403, {"error": "integration read session required"})
            return
        data = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
        outbound = urllib.request.Request(
            "https://10.77.62.20/api/from-the-report-to-the-live-feed",
            data=data,
            headers={
                "Authorization": "Bearer " + supplied,
                "X-ARWC-Tenant": self.headers.get("X-ARWC-Tenant", "arwc"),
                "Content-Type": "application/json",
            },
            method="POST",
        )
        context = ssl.create_default_context(cafile="/run/arwc-tls/ca.crt")
        try:
            response = urllib.request.urlopen(outbound, context=context, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        except OSError:
            self.send_json(409, {"error": "integration gateway is unavailable"})
            return
        try:
            payload = json.loads(response.read())
        except json.JSONDecodeError:
            self.send_json(409, {"error": "integration gateway returned an invalid response"})
            return
        self.send_json(response.status, payload)

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
            self.accepted("read-beyond-the-allowed-statement", protected, 201,
                          {"statement": statement, "row_count": len(records)})
        else:
            self.accepted("read-beyond-the-allowed-statement", records[0], 201,
                          {"statement": statement, "row_count": 1})

    def reconcile(self, request: dict[str, object]) -> None:
        state = load_state()
        if not state["adjustment_observed"]:
            self.send_json(403, {"error": "allocation adjustment has not been observed"})
            return
        if request.get("function") != "arwc_reconcile_copy" or request.get("record_id") != "REC-CRR-DP3-17":
            self.send_json(409, {"error": "reconciliation invocation is not accepted"})
            return
        try:
            with database() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT * FROM arwc_reconcile_copy(%s)", (request["record_id"],))
                row = cursor.fetchone()
        except psycopg2.Error:
            self.send_json(409, {"error": "reconciliation function rejected the request"})
            return
        result = {
            "record_id": row[0],
            "revision": row[1],
            "source_record": row[2],
            "database_identity": row[3],
            "execution_context": "SECURITY DEFINER",
        }
        atomic_json(ROOT / "results" / "REC-CRR-DP3-17-COPY.json", result)
        state["reconciliation_copy_created"] = True
        save_state(state)
        self.accepted("the-database-does-more-than-read", result, 201)


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
