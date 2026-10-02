#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import unittest


CONTAINER = "cinder-arwc-connector"
BASE = "https://customer-handover.arwc.test:8443"


def inside(*arguments: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "--user",
            "fieldlink",
            "--workdir",
            "/var/lib/fieldlink-connector",
            CONTAINER,
            *arguments,
        ],
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
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


class W01Live(unittest.TestCase):
    def test_01_customer_copy_is_bound_to_active_delivery(self) -> None:
        status, response = request("/api/the-customer-s-copy")
        self.assertEqual(status, 200)
        self.assertEqual(
            response["record"],
            {
                "record_id": "HND-ARWC-047",
                "tenant": "TEN-ARWC-047",
                "active_connector": "FLK-7.4.2",
                "maintenance_case": "MTN-CRR-204",
                "customer_receipt": "RCP-742-047",
                "status": "retained",
            },
        )
        self.assertRegex(response["audit_id"], r"^[0-9a-f-]{36}$")

    def test_02_planner_handover_is_a_separate_record(self) -> None:
        status, response = request("/api/the-planner-s-unfinished-handover")
        self.assertEqual(status, 200)
        record = response["record"]
        self.assertEqual(record["record_id"], "PLN-HO-CRR-17")
        self.assertEqual(record["inspection"], "INSP-CRR-2026-09-18")
        self.assertEqual(record["assignee"], "nadia.corvane")
        self.assertNotIn("customer_receipt", record)

    def test_03_exact_authored_planning_context_is_reused(self) -> None:
        status, response = request("/api/how-the-company-buys-time")
        self.assertEqual(status, 200)
        record = response["record"]
        self.assertEqual(record["record_id"], "CONT-DRY-A-R3")
        self.assertEqual(record["planning_reference"], "ARWC-PLAN-METHOD-01")
        source = json.loads(
            pathlib.Path(
                "../../assets/narrative/generated/packages/arwc-documents.json"
            ).read_text(encoding="utf-8")
        )
        authored = next(
            item["text"] for item in source["documents"]
            if item["name"] == "pl-arwc-plan-method-01-method"
        )
        self.assertEqual(record["planning_context"], authored)
        self.assertEqual(
            record["measures"],
            ["replacement water purchasing", "Stage A restrictions"],
        )

    def test_04_attachment_change_preserves_immutable_bindings(self) -> None:
        before_status, before = request("/api/the-planner-s-unfinished-handover")
        self.assertEqual(before_status, 200)
        original = before["record"]
        content = "# Cinder inspection summary\n\nOutlet inspection remains scheduled for 18 September.\n"
        body = {
            "record_id": "PLN-HO-CRR-17",
            "expected_revision": original["revision"],
            "inspection": original["inspection"],
            "assignee": original["assignee"],
            "attachment": {"filename": "cinder-inspection-summary.md", "content": content},
        }
        status, changed = request("/api/change-the-corporate-record", method="POST", body=body)
        self.assertEqual(status, 201)
        self.assertEqual(changed["inspection"], original["inspection"])
        self.assertEqual(changed["assignee"], original["assignee"])
        self.assertEqual(changed["attachment_sha256"], hashlib.sha256(content.encode()).hexdigest())
        after_status, after = request("/api/the-planner-s-unfinished-handover")
        self.assertEqual(after_status, 200)
        self.assertEqual(after["record"]["revision"], original["revision"] + 1)
        self.assertEqual(after["record"]["attachment"]["owner"], "nadia.corvane")

        stale_status, _ = request("/api/change-the-corporate-record", method="POST", body=body)
        self.assertEqual(stale_status, 409)

    def test_05_wrong_authority_tenant_and_binding_are_denied(self) -> None:
        status, body = request("/api/the-customer-s-copy", token="not-a-session")
        self.assertEqual(status, 403)
        self.assertNotIn("HND-ARWC-047", json.dumps(body))
        status, body = request("/api/the-customer-s-copy", tenant="merewick")
        self.assertEqual(status, 403)
        self.assertNotIn("HND-ARWC-047", json.dumps(body))

        current_status, current = request("/api/the-planner-s-unfinished-handover")
        self.assertEqual(current_status, 200)
        status, _ = request(
            "/api/change-the-corporate-record",
            method="POST",
            body={
                "record_id": "PLN-HO-CRR-17",
                "expected_revision": current["record"]["revision"],
                "inspection": "INSP-MER-2026-09-18",
                "assignee": "nadia.corvane",
                "attachment": {"filename": "other.md", "content": "wrong district"},
            },
        )
        self.assertEqual(status, 409)

    def test_06_state_and_protected_audit_persist(self) -> None:
        _, before = request("/api/the-planner-s-unfinished-handover")
        subprocess.run(["docker", "restart", CONTAINER], check=True, stdout=subprocess.DEVNULL)
        for _ in range(30):
            completed = inside("sh", "-c", "test -r /tmp/arwc-ca.crt")
            if completed.returncode == 0:
                try:
                    status, after = request("/api/the-planner-s-unfinished-handover")
                    if status == 200:
                        break
                except AssertionError:
                    pass
        else:
            self.fail("customer handover did not return after restart")
        self.assertEqual(after["record"], before["record"])
        audit_check = inside("sh", "-c", "test ! -r /var/lib/arwc-connector/audit/events.jsonl")
        self.assertEqual(audit_check.returncode, 0)
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-connector", CONTAINER,
             "cat", "/var/lib/arwc-connector/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        )
        self.assertIn('"action":"change-the-corporate-record"', audit.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
