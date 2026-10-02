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
    response = urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), context=context)
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


class W02W03Live(unittest.TestCase):
    def test_01_protected_association_requires_source_table(self) -> None:
        status, body = request(
            "/api/the-record-behind-the-wrong-association", method="POST",
            body={"association_id": "ASC-CRR-4417-ALT", "expected_revision": 6},
        )
        self.assertEqual(status, 403)
        self.assertNotIn("MR-CRR-4417-R6", json.dumps(body))

    def test_02_asset_contractor_bundle_is_one_record(self) -> None:
        status, response = request("/api/the-asset-and-the-contractor")
        self.assertEqual(status, 200)
        self.assertEqual(response["record"], {
            "record_id": "BND-CRR-OUTLET-17",
            "asset": "AST-CRR-017",
            "outlet_group": "OG-CRR-02",
            "contractor_assignment": "CTR-VEY-204",
            "inspection": "INSP-CRR-2026-09-18",
        })

    def test_03_association_authorization_uses_supplied_row(self) -> None:
        status, table = request("/api/three-names-for-one-job")
        self.assertEqual(status, 200)
        sources = table["record"]["sources"]
        self.assertEqual(sources["work_order"]["id"], "WO-CRR-4417")
        self.assertEqual(sources["contractor_job"]["id"], "VYB-204-77")
        self.assertEqual(sources["asset"]["id"], "AST-CRR-017")
        self.assertEqual(sources["inspection"]["id"], "INSP-CRR-2026-09-18")

        wrong, _ = request(
            "/api/the-record-behind-the-wrong-association", method="POST",
            body={"association_id": "ASC-MER-1000", "expected_revision": 6},
        )
        self.assertEqual(wrong, 409)
        status, result = request(
            "/api/the-record-behind-the-wrong-association", method="POST",
            body={"association_id": "ASC-CRR-4417-ALT", "expected_revision": 6},
        )
        self.assertEqual(status, 201)
        self.assertEqual(result["record"]["record_id"], "MR-CRR-4417-R6")
        self.assertEqual(result["record"]["revision"], 6)

    def test_04_annex_names_the_real_handover_and_importer(self) -> None:
        status, response = request("/api/an-annex-left-with-the-order")
        self.assertEqual(status, 200)
        record = response["record"]
        self.assertEqual(record["record_id"], "ANN-4417-R2")
        self.assertEqual(record["work_order"], "WO-CRR-4417")
        self.assertEqual(record["process_data_handover"], "PDH-CRR-READ-08")
        self.assertEqual(record["importer"], "annex-import/2")

    def test_05_read_contract_requires_restricted_handover(self) -> None:
        status, body = request("/api/the-integration-s-read-contract")
        self.assertEqual(status, 403)
        self.assertNotIn("INT-CRR-08", json.dumps(body))

    def test_06_validate_before_decode_reaches_restricted_handover(self) -> None:
        plain, _ = request(
            "/api/a-reference-outside-the-order", method="POST",
            body={"reference": "restricted/PDH-CRR-READ-08"},
        )
        self.assertEqual(plain, 409)
        status, imported = request(
            "/api/a-reference-outside-the-order", method="POST",
            body={"reference": "attachments/%2e%2e%2frestricted%2fPDH-CRR-READ-08"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(imported["record"]["record_id"], "PDH-CRR-READ-08")
        self.assertEqual(imported["record"]["work_order"], "WO-CRR-4417")
        self.assertEqual(imported["record"]["service_identity"], "svc-annex")

        status, contract = request("/api/the-integration-s-read-contract")
        self.assertEqual(status, 200)
        self.assertEqual(contract["record"], {
            "record_id": "PDH-CRR-READ-08",
            "integration_client": "INT-CRR-08",
            "endpoint": "process-read.arwc.test",
            "protocol": "process-read/v2",
            "scope": "OG-CRR-02/read",
            "retained_bundle": "BND-COLLECT-CRR-12",
        })

    def test_07_wrong_session_and_tenant_disclose_nothing(self) -> None:
        status, body = request("/api/three-names-for-one-job", token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("WO-CRR-4417", json.dumps(body))
        status, body = request("/api/an-annex-left-with-the-order", tenant="merewick")
        self.assertEqual(status, 403)
        self.assertNotIn("PDH-CRR-READ-08", json.dumps(body))

    def test_08_evidence_and_discoveries_persist_across_restart(self) -> None:
        subprocess.run(["docker", "restart", SERVICE], check=True, stdout=subprocess.DEVNULL)
        for _ in range(30):
            try:
                status, contract = request("/api/the-integration-s-read-contract")
                if status == 200:
                    break
            except AssertionError:
                pass
        else:
            self.fail("business workplace did not return after restart")
        self.assertEqual(contract["record"]["integration_client"], "INT-CRR-08")
        hidden = inside("sh", "-c", "test ! -r /var/lib/arwc-business/audit/events.jsonl")
        self.assertEqual(hidden.returncode, 0)
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-business", SERVICE,
             "cat", "/var/lib/arwc-business/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        )
        self.assertIn('"action":"the-record-behind-the-wrong-association"', audit.stdout)
        self.assertIn('"action":"a-reference-outside-the-order"', audit.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
