#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import subprocess
import unittest


CLIENT = "cinder-arwc-connector"
DATA = "cinder-arwc-data"
BUSINESS = "cinder-arwc-business"
BASE = "https://planning-data.arwc.test"
MAGIC = bytes.fromhex("6060b017")
VERSION = bytes.fromhex("00000405")
QUERY = (
    "MATCH (a:Asset {record_id: $asset})-[r:RELATION]->(w:Work) "
    "RETURN r.record_id,w.record_id"
)
LINEAGE_OU = (
    "ASSET_WORK]->(w) WITH a MATCH p=(legacy:Legacy)-[:SUPERSEDES]->"
    "(group:OutletGroup)-[:CURRENT_ASSET]->(a)<-[:ARCHIVED_ASSET]-"
    "(archive:Archive) RETURN p //"
)


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def request(path: str, *, method: str = "GET", body: dict | None = None,
            token: str | None = None, tenant: str = "arwc",
            planner: str | None = "@planner") -> tuple[int, dict]:
    script = r'''
import json, pathlib, ssl, sys, urllib.error, urllib.request
method, url, tenant, supplied, planner, body = sys.argv[1:]
if supplied == "@session":
    supplied = pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
if planner == "@planner":
    planner = pathlib.Path("/var/lib/fieldlink-connector/receipts/planner-session").read_text().strip()
headers = {"Authorization": "Bearer " + supplied, "X-ARWC-Tenant": tenant}
if planner:
    headers["X-ARWC-Planner-Session"] = planner
data = None if not body else body.encode()
if data is not None:
    headers["Content-Type"] = "application/json"
context = ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try:
    response = urllib.request.urlopen(
        urllib.request.Request(url, data=data, headers=headers, method=method), context=context
    )
except urllib.error.HTTPError as error:
    response = error
print(response.status)
print(response.read().decode())
'''
    completed = inside(
        "python3", "-c", script, method, BASE + path, tenant,
        "@session" if token is None else token,
        "" if planner is None else planner,
        "" if body is None else json.dumps(body, separators=(",", ":")),
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


def pack(value: object) -> bytes:
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
    if isinstance(value, dict):
        return bytes([0xA0 + len(value)]) + b"".join(
            pack(str(key)) + pack(item) for key, item in value.items()
        )
    raise ValueError(value)


def structure(signature: int, *fields: object) -> bytes:
    return bytes([0xB0 + len(fields), signature]) + b"".join(pack(field) for field in fields)


def chunk(payload: bytes) -> bytes:
    return len(payload).to_bytes(2, "big") + payload + b"\x00\x00"


def exchange(*, asset: str = "AST-CRR-017", association: str = "ASC-CRR-4417",
             ou: str = "ASSET_WORK", query: str = QUERY,
             magic: bytes = MAGIC, version: bytes = VERSION) -> str:
    value = magic + version + bytes(12)
    value += chunk(structure(0x01, {"user_agent": "arwc-reltool/3"}))
    value += chunk(structure(0x10, query, {
        "asset": asset, "association": association, "certificate_ou": ou,
    }, {}))
    value += chunk(structure(0x3F, {"n": -1}))
    return base64.b64encode(value).decode()


def response_signatures(encoded: str) -> list[int]:
    value = base64.b64decode(encoded, validate=True)
    if value[:4] != VERSION:
        raise AssertionError("wrong negotiated version")
    result: list[int] = []
    offset = 4
    while offset < len(value):
        length = int.from_bytes(value[offset:offset + 2], "big")
        offset += 2
        payload = value[offset:offset + length]
        offset += length
        if value[offset:offset + 2] != b"\x00\x00":
            raise AssertionError("missing chunk terminator")
        offset += 2
        result.append(payload[1])
    return result


class W11Live(unittest.TestCase):
    def test_01_each_declared_prerequisite_independently_exposes_contract(self) -> None:
        evidence = "/var/lib/arwc-business/relation/W02-association.json"
        original = subprocess.run(
            ["docker", "exec", "--user", "arwc-data", DATA,
             "cat", "/var/lib/arwc-data/state/planning.json"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        state = json.loads(original)

        def set_reserve(value: bool) -> None:
            changed = dict(state, reserve_reconciled=value)
            subprocess.run(
                ["docker", "exec", "-i", "--user", "arwc-data", DATA,
                 "python3", "-c",
                 "import json,sys; open('/var/lib/arwc-data/state/planning.json','w').write(json.dumps(json.load(sys.stdin),sort_keys=True,separators=(',',':'))+'\\n')"],
                input=json.dumps(changed), text=True, check=True,
            )

        subprocess.run(["docker", "exec", BUSINESS, "mv", evidence, evidence + ".hold"], check=True)
        set_reserve(False)
        status, body = request("/api/the-relation-service-s-language")
        self.assertEqual(status, 403)
        self.assertNotIn("RELPROTO-CRR-R3", json.dumps(body))

        subprocess.run(["docker", "exec", BUSINESS, "mv", evidence + ".hold", evidence], check=True)
        status, business_branch = request("/api/the-relation-service-s-language")
        self.assertEqual(status, 200)

        subprocess.run(["docker", "exec", BUSINESS, "mv", evidence, evidence + ".hold"], check=True)
        set_reserve(True)
        status, data_branch = request("/api/the-relation-service-s-language")
        self.assertEqual(status, 200)
        self.assertEqual(data_branch["record"], business_branch["record"])

        subprocess.run(["docker", "exec", BUSINESS, "mv", evidence + ".hold", evidence], check=True)
        restored = dict(state, relation_contract_observed=True)
        subprocess.run(
            ["docker", "exec", "-i", "--user", "arwc-data", DATA,
             "python3", "-c",
             "import json,sys; open('/var/lib/arwc-data/state/planning.json','w').write(json.dumps(json.load(sys.stdin),sort_keys=True,separators=(',',':'))+'\\n')"],
            input=json.dumps(restored), text=True, check=True,
        )
        contract = data_branch["record"]
        self.assertEqual(contract["record_id"], "RELPROTO-CRR-R3")
        self.assertEqual(contract["protocol"], "Neo4j Bolt 5.4")
        self.assertEqual(contract["magic"], "60 60 b0 17")
        self.assertEqual(contract["relation"], "ASSET_WORK")
        self.assertEqual(contract["association"], "ASC-CRR-4417")
        self.assertEqual(contract["packstream"]["RUN"]["signature"], "10")

    def test_02_only_a_complete_bolt_54_exchange_is_accepted(self) -> None:
        invalid = (
            exchange(magic=bytes.fromhex("6060b016")),
            exchange(version=bytes.fromhex("00000305")),
            exchange(query="CREATE (n) RETURN n"),
            base64.b64encode(MAGIC + VERSION + bytes(12) + b"\x00\x08\xb1").decode(),
        )
        for candidate in invalid:
            status, body = request(
                "/api/an-exchange-the-backend-accepts", method="POST",
                body={"exchange": candidate},
            )
            self.assertEqual(status, 409)
            self.assertNotIn("REL-ASC-CRR-4417-R3", json.dumps(body))
        status, response = request(
            "/api/an-exchange-the-backend-accepts", method="POST",
            body={"exchange": exchange()},
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"], {
            "record_id": "REL-ASC-CRR-4417-R3", "revision": 3,
            "association": "ASC-CRR-4417", "relation": "ASSET_WORK",
            "asset": "AST-CRR-017", "work_order": "WO-CRR-4417",
        })
        self.assertEqual(response_signatures(response["bolt_response"]), [0x70, 0x70, 0x71, 0x70])

    def test_03_initial_exchange_does_not_contain_lineage(self) -> None:
        status, response = request(
            "/api/an-exchange-the-backend-accepts", method="POST",
            body={"exchange": exchange()},
        )
        self.assertEqual(status, 201)
        self.assertNotIn("LIN-AST-CRR-017-R8", json.dumps(response))
        self.assertNotIn("ARC-COLD-CRR-2019", json.dumps(response))

    def test_04_relationship_construction_reaches_only_bound_lineage(self) -> None:
        for candidate in (
            exchange(asset="AST-MER-001", ou=LINEAGE_OU),
            exchange(association="ASC-MER-001", ou=LINEAGE_OU),
            exchange(ou="ASSET_WORK"),
            exchange(ou=LINEAGE_OU + " DELETE a"),
        ):
            status, body = request(
                "/api/the-asset-s-true-lineage", method="POST",
                body={"exchange": candidate},
            )
            self.assertEqual(status, 409)
            self.assertNotIn("LIN-AST-CRR-017-R8", json.dumps(body))
        status, response = request(
            "/api/the-asset-s-true-lineage", method="POST",
            body={"exchange": exchange(ou=LINEAGE_OU)},
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"], {
            "record_id": "LIN-AST-CRR-017-R8", "revision": 8,
            "legacy": "CRR-OG-LEGACY-2", "outlet_group": "OG-CRR-02",
            "current_asset": "AST-CRR-017", "archive": "ARC-COLD-CRR-2019",
        })
        self.assertEqual(response_signatures(response["bolt_response"]), [0x70, 0x70, 0x71, 0x70])

    def test_05_authorization_and_tenant_are_enforced(self) -> None:
        status, body = request("/api/the-relation-service-s-language", token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("RELPROTO-CRR-R3", json.dumps(body))
        status, body = request("/api/the-relation-service-s-language", tenant="merewick")
        self.assertEqual(status, 403)
        self.assertNotIn("ASSET_WORK", json.dumps(body))
        status, body = request("/api/the-relation-service-s-language", planner=None)
        self.assertEqual(status, 403)
        self.assertNotIn("ASC-CRR-4417", json.dumps(body))

    def test_06_results_and_audits_persist_across_restart(self) -> None:
        subprocess.run(["docker", "restart", DATA], check=True, stdout=subprocess.DEVNULL)
        for _ in range(30):
            try:
                status, response = request(
                    "/api/the-asset-s-true-lineage", method="POST",
                    body={"exchange": exchange(ou=LINEAGE_OU)},
                )
                if status == 201:
                    break
            except AssertionError:
                pass
        else:
            self.fail("planning data did not return after restart")
        self.assertEqual(response["record"]["record_id"], "LIN-AST-CRR-017-R8")
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-data", DATA,
             "cat", "/var/lib/arwc-data/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        for action in (
            "the-relation-service-s-language", "an-exchange-the-backend-accepts",
            "the-asset-s-true-lineage",
        ):
            self.assertIn(f'"action":"{action}"', audit)
        hidden = inside("sh", "-c", "test ! -r /var/lib/arwc-data/state/planning.json")
        self.assertEqual(hidden.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
