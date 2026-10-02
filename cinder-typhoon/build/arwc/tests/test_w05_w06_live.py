#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
import unittest


CLIENT = "cinder-arwc-connector"
SERVICE = "cinder-arwc-identity"
BASE = "https://corporate-identity.arwc.test"


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def request(path: str, *, method: str = "GET", body: dict | None = None,
            token: str | None = None, tenant: str = "arwc",
            planning_access: str = "") -> tuple[int, dict]:
    script = r'''
import json, pathlib, ssl, sys, urllib.error, urllib.request
method, url, tenant, supplied, planning, body = sys.argv[1:]
if supplied == "@session":
    supplied = pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers = {"Authorization": "Bearer " + supplied, "X-ARWC-Tenant": tenant}
if planning:
    headers["X-ARWC-Planning-Access"] = planning
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
        "@session" if token is None else token, planning_access,
        "" if body is None else json.dumps(body, separators=(",", ":")),
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


class W05W06Live(unittest.TestCase):
    handover = ""
    limited = ""
    oauth_state = ""
    planner = ""

    def test_01_archive_handover_is_an_independent_planning_path(self) -> None:
        handover = inside("cat", "/var/lib/fieldlink-connector/receipts/planner-handover")
        self.assertEqual(handover.returncode, 0, handover.stderr)
        type(self).handover = handover.stdout.strip()
        status, response = request(
            "/api/the-planner-s-login-trail", planning_access=type(self).handover,
        )
        self.assertEqual(status, 200)
        self.assertEqual(response["record"]["record_id"], "RENDER-CRR-882")
        self.assertEqual(response["record"]["drawing"], "DRW-OG2-R8")

    def test_02_onboarding_records_are_distinct_and_exact(self) -> None:
        status, starter = request("/api/a-starter-pack-left-open")
        self.assertEqual(status, 200)
        self.assertEqual(starter["record"], {
            "record_id": "START-MIRA-2026",
            "revision": 1,
            "employee_name": "Mira Vale",
            "employee_number": "TMP-4821",
            "assignment": "PLAN-RELIEF-7",
            "portal_identity": "mira.vale.temp",
            "activation_secret": None,
        })
        status, roster = request("/api/the-activation-roster")
        self.assertEqual(status, 200)
        self.assertEqual(roster["record"]["record_id"], "ACT-SEP26-R3")
        self.assertEqual(roster["record"]["activation_code"], "731944")
        self.assertEqual(roster["record"]["approved_assignment"], "PLAN-RELIEF-3")
        self.assertNotIn("731944", json.dumps(starter))

    def test_03_activation_omits_only_the_assignment_binding(self) -> None:
        wrong, _ = request(
            "/api/temporary-with-the-wrong-rights", method="POST",
            body={
                "employee_number": "TMP-4821", "activation_code": "000000",
                "requested_assignment": "PLAN-RELIEF-7",
            },
        )
        self.assertEqual(wrong, 409)
        unavailable, _ = request(
            "/api/temporary-with-the-wrong-rights", method="POST",
            body={
                "employee_number": "TMP-4821", "activation_code": "731944",
                "requested_assignment": "PLAN-ADMIN-1",
            },
        )
        self.assertEqual(unavailable, 409)
        status, response = request(
            "/api/temporary-with-the-wrong-rights", method="POST",
            body={
                "employee_number": "TMP-4821", "activation_code": "731944",
                "requested_assignment": "PLAN-RELIEF-7",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["assignment"], "PLAN-RELIEF-7")
        self.assertFalse(response["record"]["administrative"])
        self.assertNotIn("admin", response["record"]["roles"])
        type(self).limited = response["limited_session"]

    def test_04_rendering_record_requires_working_planning_access(self) -> None:
        denied, body = request("/api/the-planner-s-login-trail", planning_access="wrong")
        self.assertEqual(denied, 403)
        self.assertNotIn("OAUTH-PLN-882", json.dumps(body))
        status, response = request(
            "/api/the-planner-s-login-trail", planning_access=type(self).limited,
        )
        self.assertEqual(status, 200)
        record = response["record"]
        self.assertEqual(record["planner"], "nadia.corvane")
        self.assertEqual(record["review"], "REV-CRR-4417")
        self.assertEqual(record["oauth_transaction"], "OAUTH-PLN-882")
        self.assertEqual(record["browser_profile"], "planner-review-3")
        type(self).oauth_state = record["oauth_state"]

    def test_05_state_is_checked_before_preview_origin_is_replaced(self) -> None:
        wrong_state, _ = request(
            "/api/a-drawing-in-the-wrong-context", method="POST",
            planning_access=type(self).limited,
            body={
                "oauth_state": "wrong", "drawing": "DRW-OG2-R8",
                "review": "REV-CRR-4417", "preview_origin": "https://preview-cinder.arwc.test",
            },
        )
        self.assertEqual(wrong_state, 409)
        wrong_drawing, _ = request(
            "/api/a-drawing-in-the-wrong-context", method="POST",
            planning_access=type(self).limited,
            body={
                "oauth_state": type(self).oauth_state, "drawing": "DRW-MER-1",
                "review": "REV-CRR-4417", "preview_origin": "https://preview-cinder.arwc.test",
            },
        )
        self.assertEqual(wrong_drawing, 409)
        status, response = request(
            "/api/a-drawing-in-the-wrong-context", method="POST",
            planning_access=type(self).limited,
            body={
                "oauth_state": type(self).oauth_state, "drawing": "DRW-OG2-R8",
                "review": "REV-CRR-4417", "preview_origin": "https://preview-cinder.arwc.test",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["revision"], 9)
        self.assertEqual(response["record"]["preview_origin"], "https://preview-cinder.arwc.test")

    def test_06_privileged_browser_posts_a_bounded_planner_session(self) -> None:
        wrong, _ = request(
            "/api/a-planner-session-that-works", method="POST",
            planning_access=type(self).limited,
            body={
                "oauth_transaction": "OAUTH-PLN-882",
                "preview_origin": "https://unrelated.arwc.test",
            },
        )
        self.assertEqual(wrong, 409)
        status, response = request(
            "/api/a-planner-session-that-works", method="POST",
            planning_access=type(self).limited,
            body={
                "oauth_transaction": "OAUTH-PLN-882",
                "preview_origin": "https://preview-cinder.arwc.test",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["planner"], "nadia.corvane")
        self.assertEqual(response["record"]["scope"], "planning-records")
        remaining = response["record"]["expires_at_epoch"] - int(time.time())
        self.assertGreaterEqual(remaining, 895)
        self.assertLessEqual(remaining, 900)
        type(self).planner = response["planner_session"]
        saved = inside(
            "sh", "-c",
            "umask 077; printf '%s\\n' \"$1\" > /var/lib/fieldlink-connector/receipts/planner-session",
            "sh", type(self).planner,
        )
        self.assertEqual(saved.returncode, 0, saved.stderr)

    def test_07_wrong_corporate_session_and_tenant_disclose_nothing(self) -> None:
        status, body = request("/api/a-starter-pack-left-open", token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("TMP-4821", json.dumps(body))
        status, body = request("/api/the-activation-roster", tenant="merewick")
        self.assertEqual(status, 403)
        self.assertNotIn("731944", json.dumps(body))

    def test_08_identity_state_and_audit_persist_across_restart(self) -> None:
        subprocess.run(["docker", "restart", SERVICE], check=True, stdout=subprocess.DEVNULL)
        for _ in range(30):
            try:
                status, response = request(
                    "/api/the-planner-s-login-trail", planning_access=type(self).limited,
                )
                if status == 200:
                    break
            except AssertionError:
                pass
        else:
            self.fail("corporate identity did not return after restart")
        self.assertEqual(response["record"]["pending_preview_origin"], "https://preview-cinder.arwc.test")
        hidden = inside("sh", "-c", "test ! -r /var/lib/arwc-identity/state/identity.json")
        self.assertEqual(hidden.returncode, 0)
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-identity", SERVICE,
             "cat", "/var/lib/arwc-identity/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        )
        self.assertIn('"action":"temporary-with-the-wrong-rights"', audit.stdout)
        self.assertIn('"action":"a-drawing-in-the-wrong-context"', audit.stdout)
        self.assertIn('"action":"a-planner-session-that-works"', audit.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
