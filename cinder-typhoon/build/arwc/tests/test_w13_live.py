#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import unittest


CLIENT = "cinder-arwc-connector"
SERVICE = "cinder-arwc-contractors"
BASE = "https://contractor-portal.arwc.test"


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
headers={"Authorization":"Bearer "+supplied,"X-ARWC-Tenant":tenant}
data=None if not body else body.encode()
if data is not None: headers["Content-Type"]="application/json"
context=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try: response=urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),context=context)
except urllib.error.HTTPError as error: response=error
print(response.status); print(response.read().decode())
'''
    completed = inside("python3", "-c", script, method, BASE + path, tenant,
                       "@session" if token is None else token,
                       "" if body is None else json.dumps(body, separators=(",", ":")))
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


class W13Live(unittest.TestCase):
    session = ""

    def test_01_records_are_authorized_and_independently_exact(self) -> None:
        for path, identifier in (("/api/window-on-thursday", "APT-CRR-2026-09-18"),
                                 ("/api/who-is-expected-at-the-gate", "ROSTER-CRR-SEP18-R2")):
            status, body = request(path, token="wrong")
            self.assertEqual(status, 403)
            self.assertNotIn(identifier, json.dumps(body))
        status, appointment = request("/api/window-on-thursday")
        self.assertEqual(status, 200)
        self.assertEqual(appointment["record"], {
            "record_id": "APT-CRR-2026-09-18", "revision": 1,
            "inspection": "INSP-CRR-2026-09-18", "asset": "AST-CRR-017",
            "window": {"day": "Thursday", "starts": "09:00", "ends": "11:00"},
            "owner_organization": "Northbank Civil Inspections",
            "attendee": "northbank.inspector.117",
        })
        status, roster = request("/api/who-is-expected-at-the-gate")
        self.assertEqual(status, 200)
        self.assertEqual(roster["record"]["identity"], "veybridge.tech.204")
        self.assertEqual(roster["record"]["assignment"], "CTR-VEY-204")
        self.assertEqual(roster["record"]["revision"], 2)

    def test_02_attendee_update_enforces_org_and_immutable_bindings(self) -> None:
        baseline = {
            "appointment_id": "APT-CRR-2026-09-18", "expected_revision": 1,
            "attendee": "veybridge.tech.204",
            "caller_organization": "Veybridge Technical Services",
            "inspection": "INSP-CRR-2026-09-18", "asset": "AST-CRR-017",
            "window": {"day": "Thursday", "starts": "09:00", "ends": "11:00"},
        }
        for changed, expected in (
            (dict(baseline, attendee="veybridge.tech.999"), 403),
            (dict(baseline, caller_organization="Northbank Civil Inspections"), 403),
            (dict(baseline, asset="AST-MER-004"), 409),
            (dict(baseline, inspection="INSP-MER-2026-09-18"), 409),
            (dict(baseline, window={"day": "Friday", "starts": "09:00", "ends": "11:00"}), 409),
        ):
            status, body = request("/api/an-appointment-we-do-not-own", method="POST", body=changed)
            self.assertEqual(status, expected)
            self.assertNotIn('"revision":2', json.dumps(body))
        status, response = request("/api/an-appointment-we-do-not-own", method="POST", body=baseline)
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["attendee"], "veybridge.tech.204")
        self.assertEqual(response["record"]["revision"], 2)
        self.assertEqual(response["record"]["owner_organization"], "Northbank Civil Inspections")

    def test_03_checkin_uses_current_attendee_and_separate_roster(self) -> None:
        baseline = {
            "appointment_id": "APT-CRR-2026-09-18",
            "roster_id": "ROSTER-CRR-SEP18-R2",
            "identity": "veybridge.tech.204",
        }
        status, body = request("/api/checked-in-as-the-contractor", method="POST",
                               body=dict(baseline, roster_id="ROSTER-CRR-SEP18-R1"))
        self.assertEqual(status, 403)
        self.assertNotIn("SCOPE-INSP-CRR-4417", json.dumps(body))
        status, response = request("/api/checked-in-as-the-contractor", method="POST", body=baseline)
        self.assertEqual(status, 201)
        self.assertEqual(response["record"], {
            "record_id": "SCOPE-INSP-CRR-4417", "inspection": "INSP-CRR-2026-09-18",
            "asset": "AST-CRR-017", "identity": "veybridge.tech.204",
            "assignment": "CTR-VEY-204", "scope": ["field-work:read"],
        })
        type(self).session = response["contractor_session"]
        self.assertGreater(len(type(self).session), 32)

    def test_04_scope_and_state_persist_across_restart(self) -> None:
        subprocess.run(["docker", "restart", SERVICE], check=True, stdout=subprocess.DEVNULL)
        for _ in range(30):
            try:
                status, response = request("/api/the-field-bag", token=type(self).session)
                if status == 200:
                    break
            except AssertionError:
                pass
        else:
            self.fail("contractor portal did not return after restart")
        self.assertEqual(response["record"]["record_id"], "FIELD-BAG-CRR-4417-R3")
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-contractors", SERVICE,
             "cat", "/var/lib/arwc-contractors/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        for action in ("window-on-thursday", "who-is-expected-at-the-gate",
                       "an-appointment-we-do-not-own", "checked-in-as-the-contractor"):
            self.assertIn(f'"action":"{action}"', audit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
