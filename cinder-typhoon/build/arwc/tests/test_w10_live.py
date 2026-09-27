#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import unittest


CLIENT = "cinder-arwc-connector"
SERVICE = "cinder-arwc-business"
BASE = "https://business-workplace.arwc.test"


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def request(path: str, *, method: str = "GET", body: dict | None = None,
            token: str | None = None, tenant: str = "arwc") -> tuple[int, dict]:
    script = r'''
import json, pathlib, ssl, sys, urllib.error, urllib.request
method, url, tenant, supplied, body = sys.argv[1:]
if supplied == "@session":
    supplied = pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers = {"Authorization": "Bearer " + supplied, "X-ARWC-Tenant": tenant}
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
        "" if body is None else json.dumps(body, separators=(",", ":")),
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


class W10Live(unittest.TestCase):
    def test_01_dependent_reads_require_fresh_owned_evidence(self) -> None:
        status, body = request(
            "/api/another-district-in-the-results", method="POST",
            body={"source_set": "SEL-CRR-DP3-7", "expected_revision": 7,
                  "role": "planning-reader", "district": "Cairn Reach"},
        )
        self.assertEqual(status, 403)
        self.assertNotIn("EXC-MER-DP3-4", json.dumps(body))
        status, body = request(
            "/api/the-document-behind-the-answer", method="POST",
            body={"excerpt_id": "EXC-MER-DP3-4", "expected_revision": 4},
        )
        self.assertEqual(status, 403)
        self.assertNotIn("PLN-MER-DP3-R6", json.dumps(body))

    def test_02_source_selection_is_the_exact_current_record(self) -> None:
        status, response = request("/api/the-report-s-source-list")
        self.assertEqual(status, 200)
        record = response["record"]
        self.assertEqual(record["record_id"], "SEL-CRR-DP3-7")
        self.assertEqual(record["revision"], 7)
        self.assertEqual(record["district"], "Cairn Reach")
        self.assertEqual(record["report"], "RPT-CRR-DP3-R7")
        self.assertEqual(record["sources"], [
            {"record_id": "ALLOC-2026-DP3-R9", "revision": 9, "status": "current"},
            {"record_id": "MTR-CRR-DP3-R12", "revision": 12, "status": "current"},
            {"record_id": "FEED-OG2-R21", "revision": 21, "status": "current"},
        ])

    def test_03_role_is_checked_but_session_district_is_not(self) -> None:
        baseline = {"source_set": "SEL-CRR-DP3-7", "expected_revision": 7,
                    "role": "planning-reader", "district": "Cairn Reach"}
        for changed in (
            dict(baseline, source_set="SEL-MER-DP3-1"),
            dict(baseline, expected_revision=6),
        ):
            status, body = request("/api/another-district-in-the-results", method="POST", body=changed)
            self.assertEqual(status, 409)
            self.assertNotIn("EXC-MER-DP3-4", json.dumps(body))
        denied, body = request(
            "/api/another-district-in-the-results", method="POST",
            body=dict(baseline, role="customer-service"),
        )
        self.assertEqual(denied, 403)
        self.assertNotIn("EXC-MER-DP3-4", json.dumps(body))
        status, response = request(
            "/api/another-district-in-the-results", method="POST", body=baseline,
        )
        self.assertEqual(status, 201)
        record = response["record"]
        self.assertEqual(record["record_id"], "EXC-MER-DP3-4")
        self.assertEqual(record["revision"], 4)
        self.assertEqual(record["district"], "Merewick")
        self.assertEqual(record["linked_document"], "PLN-MER-DP3-R6")
        self.assertNotIn("supply_condition", record)

    def test_04_linked_document_uses_possession_not_district(self) -> None:
        for body in (
            {"excerpt_id": "EXC-CRR-DP3-4", "expected_revision": 4},
            {"excerpt_id": "EXC-MER-DP3-4", "expected_revision": 3},
        ):
            status, response = request("/api/the-document-behind-the-answer", method="POST", body=body)
            self.assertEqual(status, 409)
            self.assertNotIn("PLN-MER-DP3-R6", json.dumps(response))
        status, response = request(
            "/api/the-document-behind-the-answer", method="POST",
            body={"excerpt_id": "EXC-MER-DP3-4", "expected_revision": 4,
                  "district": "Cairn Reach"},
        )
        self.assertEqual(status, 201)
        record = response["record"]
        self.assertEqual(record["record_id"], "PLN-MER-DP3-R6")
        self.assertEqual(record["revision"], 6)
        self.assertEqual(record["district"], "Merewick")
        self.assertEqual(record["linked_excerpt"], "EXC-MER-DP3-4")

    def test_05_wrong_authority_and_tenant_disclose_nothing(self) -> None:
        status, body = request("/api/the-report-s-source-list", token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("SEL-CRR-DP3-7", json.dumps(body))
        status, body = request("/api/the-report-s-source-list", tenant="merewick")
        self.assertEqual(status, 403)
        self.assertNotIn("RPT-CRR-DP3-R7", json.dumps(body))

    def test_06_evidence_and_audits_persist_across_restart(self) -> None:
        subprocess.run(["docker", "restart", SERVICE], check=True, stdout=subprocess.DEVNULL)
        for _ in range(30):
            try:
                status, response = request(
                    "/api/the-document-behind-the-answer", method="POST",
                    body={"excerpt_id": "EXC-MER-DP3-4", "expected_revision": 4},
                )
                if status == 201:
                    break
            except AssertionError:
                pass
        else:
            self.fail("business workplace did not return after restart")
        self.assertEqual(response["record"]["record_id"], "PLN-MER-DP3-R6")
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-business", SERVICE,
             "cat", "/var/lib/arwc-business/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        for action in (
            "the-report-s-source-list", "another-district-in-the-results",
            "the-document-behind-the-answer",
        ):
            self.assertIn(f'"action":"{action}"', audit)
        hidden = inside("sh", "-c", "test ! -r /var/lib/arwc-business/state/discoveries.json")
        self.assertEqual(hidden.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
