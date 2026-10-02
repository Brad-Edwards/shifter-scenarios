#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import subprocess
import unittest


CLIENT = "cinder-arwc-connector"
SERVICE = "cinder-arwc-approval"
BASE = "https://maintenance-review.arwc.test"


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def request(base: str, path: str, *, method: str = "GET", body: dict | None = None,
            token: str = "@session", tenant: str = "arwc",
            extra_headers: dict[str, str] | None = None) -> tuple[int, dict]:
    script = r'''
import json,pathlib,ssl,sys,urllib.error,urllib.request
method,url,tenant,supplied,body,extra=sys.argv[1:]
if supplied=="@session": supplied=pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers={"Authorization":"Bearer "+supplied,"X-ARWC-Tenant":tenant,**json.loads(extra)}
data=None if not body else body.encode()
if data is not None: headers["Content-Type"]="application/json"
context=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try: response=urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),context=context)
except urllib.error.HTTPError as error: response=error
print(response.status); print(response.read().decode())
'''
    completed = inside("python3", "-c", script, method, base + path, tenant, token,
                       "" if body is None else json.dumps(body, separators=(",", ":")),
                       json.dumps(extra_headers or {}, separators=(",", ":")))
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


def canonical_approval(record: dict) -> bytes:
    payload = {key: value for key, value in record.items()
               if key not in {"signature_algorithm", "signature", "signing_public_key"}}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class W15Live(unittest.TestCase):
    contractor = ""
    review_capability = ""

    @classmethod
    def setUpClass(cls) -> None:
        status, response = request(
            "https://contractor-portal.arwc.test", "/api/checked-in-as-the-contractor",
            method="POST", body={"appointment_id": "APT-CRR-2026-09-18",
                                  "roster_id": "ROSTER-CRR-SEP18-R2",
                                  "identity": "veybridge.tech.204"},
        )
        if status != 201:
            raise AssertionError(response)
        cls.contractor = response["contractor_session"]

    def test_01_both_declared_authority_branches_reach_exact_association(self) -> None:
        status, body = request(BASE, "/api/which-drawing-did-the-cache-keep", token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("CACHE-DRW-OG2-R8", json.dumps(body))
        status, response = request(BASE, "/api/which-drawing-did-the-cache-keep",
                                   token=type(self).contractor)
        self.assertEqual(status, 200)
        self.assertEqual(response["record"], {
            "record_id": "CACHE-DRW-OG2-R8", "revision": 8,
            "drawing": "DRW-OG2-R8", "drawing_revision": "R8",
            "reviewer_queue": "REV-CRR-4417", "upstream_host": "drawings.arwc.test",
            "cache_key_path": "/viewer/drawings/DRW-OG2-R8", "cache_method": "GET",
        })
        status, integration = request(
            "https://business-workplace.arwc.test", "/api/the-integration-s-read-contract",
        )
        self.assertEqual(status, 200)
        status, response = request(BASE, "/api/which-drawing-did-the-cache-keep",
                                   token=integration["integration_session"])
        self.assertEqual(status, 200)
        self.assertEqual(response["record"]["record_id"], "CACHE-DRW-OG2-R8")

    def test_02_cache_omits_revision_and_upstream_identity_but_bounds_content(self) -> None:
        body = {
            "path": "/viewer/drawings/../drawings/DRW-OG2-R8",
            "controlled_response": {
                "drawing_id": "DRW-OG2-R8", "revision": "R8", "content_type": "text/html",
                "body": "<section data-drawing='DRW-OG2-R8' data-revision='R8'>Outlet group OG-CRR-02</section>",
            },
        }
        status, denied = request(
            BASE, "/api/a-drawing-of-our-choosing", method="POST", body=body,
            token=type(self).contractor,
            extra_headers={"X-Preview-Origin": "https://unlisted-preview.arwc.test"},
        )
        self.assertEqual(status, 409)
        self.assertNotIn("CACHE-DRW-OG2-R8-CONTROLLED", json.dumps(denied))
        bad = json.loads(json.dumps(body))
        bad["controlled_response"]["body"] += "\r\nX-Injected: yes"
        status, denied = request(
            BASE, "/api/a-drawing-of-our-choosing", method="POST", body=bad,
            token=type(self).contractor,
            extra_headers={"X-Preview-Origin": "https://preview-cinder.arwc.test"},
        )
        self.assertEqual(status, 409)
        status, response = request(
            BASE, "/api/a-drawing-of-our-choosing", method="POST", body=body,
            token=type(self).contractor,
            extra_headers={"X-Preview-Origin": "https://preview-cinder.arwc.test",
                           "X-Drawing-Revision": "R7"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["cache_key"], "GET:/viewer/drawings/DRW-OG2-R8")
        self.assertEqual(response["record"]["drawing_revision"], "R8")

    def test_03_chromium_executes_source_mismatched_signed_postmessage(self) -> None:
        status, response = request(
            BASE, "/api/the-reviewer-trusts-the-drawing", method="POST",
            token=type(self).contractor,
            body={"cache_key": "GET:/viewer/drawings/DRW-OG2-R8",
                  "reviewer_queue": "REV-CRR-4417"},
        )
        self.assertEqual(status, 201, response)
        self.assertEqual(response["record"]["record_id"], "CAP-REVIEW-CRR-4417")
        self.assertEqual(response["record"]["audience"], "maintenance-approval")
        self.assertEqual(response["record"]["subject"], "DRW-OG2-R8")
        self.assertEqual(response["record"]["scope"], ["review-submit"])
        self.assertEqual(response["record"]["browser"], "Chromium 128")
        self.assertEqual(response["record"]["source_check"], "omitted")
        type(self).review_capability = response["review_capability"]

    def test_04_subject_mismatch_still_discloses_valid_signed_approval(self) -> None:
        status, denied = request(
            BASE, "/api/approval-beyond-the-token", method="POST", token=type(self).contractor,
            body={"review_capability": "wrong", "approval_id": "APR-CRR-4417-R6",
                  "inspection": "INSP-CRR-2026-09-18"},
        )
        self.assertEqual(status, 403)
        self.assertNotIn("signing_public_key", denied)
        status, response = request(
            BASE, "/api/approval-beyond-the-token", method="POST", token=type(self).contractor,
            body={"review_capability": type(self).review_capability,
                  "approval_id": "APR-CRR-4417-R6", "inspection": "INSP-CRR-2026-09-18"},
        )
        self.assertEqual(status, 201)
        record = response["record"]
        self.assertEqual(record["record_id"], "APR-CRR-4417-R6")
        self.assertEqual(record["revision"], 6)
        self.assertEqual(record["maintenance"], "WO-CRR-4417")
        self.assertEqual(record["inspection"], "INSP-CRR-2026-09-18")
        self.assertEqual(record["drawing_revision"], "R8")
        self.assertEqual(record["status"], "signed")
        verify = r'''
import base64,sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
Ed25519PublicKey.from_public_bytes(base64.b64decode(sys.argv[1])).verify(base64.b64decode(sys.argv[2]),sys.stdin.buffer.read())
'''
        completed = subprocess.run(
            ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, "python3", "-c", verify,
             record["signing_public_key"], record["signature"]],
            input=canonical_approval(record), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())

    def test_05_approval_and_audits_persist_across_restart(self) -> None:
        subprocess.run(["docker", "restart", SERVICE], check=True, stdout=subprocess.DEVNULL)
        for _ in range(30):
            try:
                status, _ = request(BASE, "/api/which-drawing-did-the-cache-keep",
                                    token=type(self).contractor)
                if status == 200:
                    break
            except AssertionError:
                pass
        else:
            self.fail("maintenance review service did not return after restart")
        state = subprocess.run(
            ["docker", "exec", "--user", "arwc-approval", SERVICE,
             "cat", "/var/lib/arwc-approval/state/maintenance-review.json"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        self.assertTrue(json.loads(state)["approval_observed"])
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-approval", SERVICE,
             "cat", "/var/lib/arwc-approval/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        for action in ("which-drawing-did-the-cache-keep", "a-drawing-of-our-choosing",
                       "the-reviewer-trusts-the-drawing", "approval-beyond-the-token"):
            self.assertIn(f'"action":"{action}"', audit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
