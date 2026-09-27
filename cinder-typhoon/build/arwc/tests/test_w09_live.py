#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import unittest


CLIENT = "cinder-arwc-connector"
DATA = "cinder-arwc-data"
BRIDGE = "cinder-arwc-data-bridge"


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def request(base: str, path: str, *, method: str = "GET", body: dict | None = None,
            token: str | None = None, tenant: str = "arwc",
            planner: str | None = "@planner", integration: str = "") -> tuple[int, dict]:
    script = r'''
import json, pathlib, ssl, sys, urllib.error, urllib.request
method, url, tenant, supplied, planner, integration, body = sys.argv[1:]
if supplied == "@session":
    supplied = pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
if planner == "@planner":
    planner = pathlib.Path("/var/lib/fieldlink-connector/receipts/planner-session").read_text().strip()
headers = {"Authorization": "Bearer " + supplied, "X-ARWC-Tenant": tenant}
if planner:
    headers["X-ARWC-Planner-Session"] = planner
if integration:
    headers["X-ARWC-Integration-Session"] = integration
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
        "python3", "-c", script, method, base + path, tenant,
        "@session" if token is None else token,
        "" if planner is None else planner, integration,
        "" if body is None else json.dumps(body, separators=(",", ":")),
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


class W09Live(unittest.TestCase):
    integration = ""

    def test_01_reconciliation_requires_both_independent_sources(self) -> None:
        status, body = request("https://planning-data.arwc.test", "/api/the-missing-megalitre")
        self.assertEqual(status, 403)
        self.assertNotIn("REC-CRR-DP3-17", json.dumps(body))

    def test_02_allocation_ledger_is_exact_and_database_backed(self) -> None:
        status, response = request("https://planning-data.arwc.test", "/api/water-already-promised")
        self.assertEqual(status, 200)
        self.assertEqual(response["record"], {
            "record_id": "ALLOC-2026-DP3-R9", "revision": 9, "district": "Cairn Reach",
            "asset": "AST-CRR-017", "planning_window": "ALLOC-2026-DP3",
            "committed_ml": 12.0, "unit": "ML",
        })
        database = subprocess.run(
            ["docker", "exec", "--user", "postgres", DATA, "psql", "-d", "arwc", "-Atc",
             "SELECT record_id||':'||committed_ml||':'||unit FROM allocation_ledger"],
            text=True, stdout=subprocess.PIPE, check=True,
        )
        self.assertEqual(database.stdout.strip(), "ALLOC-2026-DP3-R9:12.00:ML")

    def test_03_meter_export_is_a_distinct_record(self) -> None:
        status, response = request("https://planning-data.arwc.test", "/api/the-meter-s-own-account")
        self.assertEqual(status, 200)
        self.assertEqual(response["record"]["record_id"], "MTR-CRR-DP3-R12")
        self.assertEqual(response["record"]["usable_reserve_ml"], 12.4)
        self.assertEqual(response["record"]["unit"], "ML")
        self.assertEqual(response["record"]["instruments"], ["FIT-CRR-204A", "FIT-CRR-204B"])
        self.assertNotIn("ALLOC-2026-DP3-R9", json.dumps(response["record"]))

    def test_04_reconciliation_computes_both_declared_differences(self) -> None:
        status, response = request("https://planning-data.arwc.test", "/api/the-missing-megalitre")
        self.assertEqual(status, 200)
        record = response["record"]
        self.assertEqual(record["record_id"], "REC-CRR-DP3-17")
        self.assertEqual(record["planning_window"], "ALLOC-2026-DP3")
        self.assertEqual(record["reported_ml"], 13.4)
        self.assertEqual(record["usable_reserve_ml"], 12.4)
        self.assertEqual(record["committed_ml"], 12.0)
        self.assertEqual(record["overstatement_ml"], 1.0)
        self.assertEqual(record["uncommitted_margin_ml"], 0.4)
        self.assertEqual(record["duplicate_transfer"], "TRN-DP3-118")
        self.assertEqual(record["asset"], "AST-CRR-017")
        self.assertEqual(record["outlet_group"], "OG-CRR-02")

    def test_05_gateway_requires_both_evidence_and_rejects_stale_feed(self) -> None:
        status, response = request(
            "https://business-workplace.arwc.test", "/api/the-integration-s-read-contract", planner=None,
        )
        self.assertEqual(status, 200)
        self.assertEqual(response["record"]["integration_client"], "INT-CRR-08")
        type(self).integration = response["integration_session"]
        binding = {
            "integration_client": "INT-CRR-08", "report_binding": "REC-CRR-DP3-17",
            "scope": "OG-CRR-02/read", "feed": "FEED-OG2-R21",
        }
        denied, body = request(
            "https://planning-data.arwc.test", "/api/integration/from-the-report-to-the-live-feed",
            method="POST", body=binding,
        )
        self.assertEqual(denied, 403)
        self.assertNotIn("usable_reserve_ml", json.dumps(body))
        wrong = dict(binding, integration_client="INT-MER-01")
        status, body = request(
            "https://planning-data.arwc.test", "/api/integration/from-the-report-to-the-live-feed",
            method="POST", body=wrong, integration=type(self).integration,
        )
        self.assertEqual(status, 409)
        self.assertNotIn("FIT-CRR-204A", json.dumps(body))
        stale = dict(binding, feed="FEED-OG2-R19")
        status, body = request(
            "https://planning-data.arwc.test", "/api/integration/from-the-report-to-the-live-feed",
            method="POST", body=stale, integration=type(self).integration,
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["record"], {"record_id": "FEED-OG2-R19", "revision": 19, "current": False})

    def test_06_current_feed_is_read_through_the_isolated_gateway(self) -> None:
        binding = {
            "integration_client": "INT-CRR-08", "report_binding": "REC-CRR-DP3-17",
            "scope": "OG-CRR-02/read", "feed": "FEED-OG2-R21",
        }
        status, response = request(
            "https://planning-data.arwc.test", "/api/integration/from-the-report-to-the-live-feed",
            method="POST", body=binding, integration=type(self).integration,
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"], {
            "record_id": "FEED-OG2-R21", "revision": 21, "current": True,
            "scope": "OG-CRR-02/read", "outlet_group": "OG-CRR-02", "asset": "AST-CRR-017",
            "planning_window": "ALLOC-2026-DP3", "usable_reserve_ml": 12.4, "unit": "ML",
            "instruments": ["FIT-CRR-204A", "FIT-CRR-204B"],
        })
        no_direct_path = inside(
            "python3", "-c", "import socket; socket.create_connection(('10.77.62.20',443),1)",
        )
        self.assertNotEqual(no_direct_path.returncode, 0)
        data_path = subprocess.run(
            ["docker", "exec", "--user", "arwc-data", DATA, "python3", "-c",
             "import socket; socket.create_connection(('10.77.62.20',443),1).close()"], check=False,
        )
        self.assertEqual(data_path.returncode, 0)

    def test_07_authorization_persistence_and_owned_audits(self) -> None:
        status, body = request(
            "https://planning-data.arwc.test", "/api/water-already-promised", token="wrong",
        )
        self.assertEqual(status, 403)
        self.assertNotIn("ALLOC-2026-DP3-R9", json.dumps(body))
        status, body = request(
            "https://planning-data.arwc.test", "/api/the-meter-s-own-account", tenant="merewick",
        )
        self.assertEqual(status, 403)
        self.assertNotIn("MTR-CRR-DP3-R12", json.dumps(body))
        subprocess.run(["docker", "restart", DATA, BRIDGE], check=True, stdout=subprocess.DEVNULL)
        binding = {
            "integration_client": "INT-CRR-08", "report_binding": "REC-CRR-DP3-17",
            "scope": "OG-CRR-02/read", "feed": "FEED-OG2-R21",
        }
        for _ in range(30):
            try:
                status, response = request(
                    "https://planning-data.arwc.test", "/api/integration/from-the-report-to-the-live-feed",
                    method="POST", body=binding, integration=type(self).integration,
                )
                if status == 201:
                    break
            except AssertionError:
                pass
        else:
            self.fail("planning integration did not return after restart")
        self.assertEqual(response["record"]["record_id"], "FEED-OG2-R21")
        data_audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-data", DATA, "cat", "/var/lib/arwc-data/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        for action in ("water-already-promised", "the-meter-s-own-account", "the-missing-megalitre"):
            self.assertIn(f'"action":"{action}"', data_audit)
        bridge_audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-data-bridge", BRIDGE,
             "cat", "/var/lib/arwc-data-bridge/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        self.assertIn('"action":"from-the-report-to-the-live-feed"', bridge_audit)
        hidden = inside("sh", "-c", "test ! -r /var/lib/arwc-data-bridge/state/integration.json")
        self.assertEqual(hidden.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
