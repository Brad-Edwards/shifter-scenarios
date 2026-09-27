#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import unittest


CLIENT = "cinder-arwc-connector"
SERVICE = "cinder-arwc-data"
BASE = "https://planning-data.arwc.test"
INJECTION = (
    'reserve_report_current" UNION ALL SELECT record_id,district,period,amount_ml,detail '
    'FROM district_allocation_adjustment --'
)


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def planner_token() -> str:
    completed = inside("cat", "/var/lib/fieldlink-connector/receipts/planner-session")
    if completed.returncode:
        raise AssertionError(completed.stderr)
    return completed.stdout.strip()


def request(path: str, *, method: str = "GET", body: dict | None = None,
            token: str | None = None, tenant: str = "arwc",
            planner: str | None = None) -> tuple[int, dict]:
    script = r'''
import json, pathlib, ssl, sys, urllib.error, urllib.request
method, url, tenant, supplied, planner, body = sys.argv[1:]
if supplied == "@session":
    supplied = pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers = {
    "Authorization": "Bearer " + supplied,
    "X-ARWC-Tenant": tenant,
    "X-ARWC-Planner-Session": planner,
}
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
        planner_token() if planner is None else planner,
        "" if body is None else json.dumps(body, separators=(",", ":")),
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


class W07Live(unittest.TestCase):
    def test_01_planning_data_requires_the_live_planner_session(self) -> None:
        status, body = request("/api/the-query-the-planner-keeps", planner="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("QRY-RESERVE-R7", json.dumps(body))
        status, body = request("/api/the-query-the-planner-keeps", tenant="merewick")
        self.assertEqual(status, 403)
        self.assertNotIn("reserve_report_current", json.dumps(body))

    def test_02_report_definition_freezes_postgresql_and_policy(self) -> None:
        status, response = request("/api/the-query-the-planner-keeps")
        self.assertEqual(status, 200)
        self.assertEqual(response["record"], {
            "record_id": "QRY-RESERVE-R7",
            "revision": 7,
            "database": "PostgreSQL 16.4",
            "view": "reserve_report_current",
            "identifier_quote": '"',
            "policy": "SELECT only",
            "ordinary_request": {"report_name": "reserve_report_current"},
            "ordinary_result": "RPT-CRR-RESERVE-R7",
        })

    def test_03_ordinary_quoted_identifier_returns_only_the_allowed_view(self) -> None:
        status, response = request(
            "/api/read-beyond-the-allowed-statement", method="POST",
            body={"report_name": "reserve_report_current"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["record_id"], "RPT-CRR-RESERVE-R7")
        self.assertEqual(response["record"]["district"], "Cairn Reach")
        self.assertNotIn("ADJ-CRR-DP3-17", json.dumps(response))
        self.assertEqual(response["statement"],
                         'SELECT record_id,district,period,amount_ml,detail FROM "reserve_report_current"')

    def test_04_semicolons_writes_and_unrelated_views_are_denied(self) -> None:
        for supplied in (
            "reserve_report_current; SELECT 1",
            'reserve_report_current" DELETE FROM reserve_report_current --',
            "district_allocation_adjustment",
        ):
            status, body = request(
                "/api/read-beyond-the-allowed-statement", method="POST",
                body={"report_name": supplied},
            )
            self.assertIn(status, {403, 409})
            self.assertNotIn("ADJ-CRR-DP3-17", json.dumps(body))

    def test_05_closing_quote_and_union_reach_the_protected_view(self) -> None:
        status, response = request(
            "/api/read-beyond-the-allowed-statement", method="POST",
            body={"report_name": INJECTION},
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"], {
            "record_id": "ADJ-CRR-DP3-17",
            "district": "Cairn Reach",
            "period": "ALLOC-2026-DP3",
            "amount_ml": -1.0,
            "detail": "duplicate transfer TRN-DP3-118",
        })
        self.assertEqual(response["row_count"], 2)
        self.assertIn('" UNION ALL SELECT', response["statement"])

    def test_06_security_definer_is_bounded_to_the_reconciliation(self) -> None:
        wrong, body = request(
            "/api/the-database-does-more-than-read", method="POST",
            body={"function": "arwc_reconcile_copy", "record_id": "REC-MER-DP3-1"},
        )
        self.assertEqual(wrong, 409)
        self.assertNotIn("REC-CRR-DP3-17-COPY", json.dumps(body))
        status, response = request(
            "/api/the-database-does-more-than-read", method="POST",
            body={"function": "arwc_reconcile_copy", "record_id": "REC-CRR-DP3-17"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"], {
            "record_id": "REC-CRR-DP3-17-COPY",
            "revision": 1,
            "source_record": "REC-CRR-DP3-17",
            "database_identity": "svc-planner-query",
            "execution_context": "SECURITY DEFINER",
        })

    def test_07_postgresql_result_and_service_audit_persist(self) -> None:
        version = subprocess.run(
            ["docker", "exec", SERVICE, "psql", "--version"],
            text=True, stdout=subprocess.PIPE, check=True,
        )
        self.assertIn("16.4", version.stdout)
        subprocess.run(["docker", "restart", SERVICE], check=True, stdout=subprocess.DEVNULL)
        for _ in range(40):
            try:
                status, response = request(
                    "/api/the-database-does-more-than-read", method="POST",
                    body={"function": "arwc_reconcile_copy", "record_id": "REC-CRR-DP3-17"},
                )
                if status == 201:
                    break
            except AssertionError:
                pass
        else:
            self.fail("planning data did not return after restart")
        self.assertEqual(response["record"]["record_id"], "REC-CRR-DP3-17-COPY")
        database_copy = subprocess.run(
            ["docker", "exec", "--user", "postgres", SERVICE, "psql", "-d", "arwc", "-Atc",
             "SELECT record_id FROM reconciliation_copy"],
            text=True, stdout=subprocess.PIPE, check=True,
        )
        self.assertEqual(database_copy.stdout.strip(), "REC-CRR-DP3-17-COPY")
        hidden = inside("sh", "-c", "test ! -r /var/lib/arwc-data/state/planning.json")
        self.assertEqual(hidden.returncode, 0)
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-data", SERVICE,
             "cat", "/var/lib/arwc-data/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        )
        self.assertIn('"action":"read-beyond-the-allowed-statement"', audit.stdout)
        self.assertIn('"action":"the-database-does-more-than-read"', audit.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
