#!/usr/bin/env python3
from __future__ import annotations

import json
import socket
import subprocess
import time
import unittest


CLIENT = "cinder-arwc-connector"
RENDERER = "https://maintenance-renderer.arwc.test"
BROKER = "https://control-broker.arwc.test"


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def request(base: str, path: str, *, method: str = "GET", body: dict | None = None,
            token: str = "@corporate", tenant: str = "arwc",
            extra_headers: dict[str, str] | None = None) -> tuple[int, dict]:
    script = r'''
import json,pathlib,ssl,sys,urllib.error,urllib.request
method,url,tenant,supplied,body,extra=sys.argv[1:]
if supplied=="@corporate": supplied=pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
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


class W26Live(unittest.TestCase):
    contractor = ""
    approval: dict = {}
    attestation = ""
    control_client = ""

    @classmethod
    def setUpClass(cls) -> None:
        portal = "https://contractor-portal.arwc.test"
        _, appointment = request(portal, "/api/window-on-thursday")
        request(portal, "/api/who-is-expected-at-the-gate")
        if appointment["record"]["attendee"] != "veybridge.tech.204":
            status, changed = request(portal, "/api/an-appointment-we-do-not-own", method="POST", body={
                "appointment_id": "APT-CRR-2026-09-18",
                "expected_revision": appointment["record"]["revision"],
                "attendee": "veybridge.tech.204",
                "caller_organization": "Veybridge Technical Services",
            })
            if status != 201:
                raise AssertionError(changed)
        status, checked_in = request(portal, "/api/checked-in-as-the-contractor", method="POST", body={
            "appointment_id": "APT-CRR-2026-09-18", "roster_id": "ROSTER-CRR-SEP18-R2",
            "identity": "veybridge.tech.204",
        })
        if status != 201:
            raise AssertionError(checked_in)
        cls.contractor = checked_in["contractor_session"]

        review = "https://maintenance-review.arwc.test"
        status, _ = request(review, "/api/which-drawing-did-the-cache-keep", token=cls.contractor)
        if status != 200:
            raise AssertionError("maintenance drawing association unavailable")
        status, controlled = request(
            review, "/api/a-drawing-of-our-choosing", method="POST", token=cls.contractor,
            extra_headers={"X-Preview-Origin": "https://preview-cinder.arwc.test"},
            body={"path": "/viewer/drawings/DRW-OG2-R8", "controlled_response": {
                "drawing_id": "DRW-OG2-R8", "revision": "R8", "content_type": "text/html",
                "body": "<section data-drawing='DRW-OG2-R8' data-revision='R8'>Outlet group OG-CRR-02</section>",
            }},
        )
        if status != 201:
            raise AssertionError(controlled)
        status, reviewed = request(
            review, "/api/the-reviewer-trusts-the-drawing", method="POST", token=cls.contractor,
            body={"cache_key": "GET:/viewer/drawings/DRW-OG2-R8", "reviewer_queue": "REV-CRR-4417"},
        )
        if status != 201:
            raise AssertionError(reviewed)
        status, approved = request(
            review, "/api/approval-beyond-the-token", method="POST", token=cls.contractor,
            body={"review_capability": reviewed["review_capability"],
                  "approval_id": "APR-CRR-4417-R6", "inspection": "INSP-CRR-2026-09-18"},
        )
        if status != 201:
            raise AssertionError(approved)
        cls.approval = approved["record"]

    def test_01_current_renderer_requires_both_prior_authorities(self) -> None:
        status, denied = request(RENDERER, "/api/which-renderer-holds-the-approval", token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("RENDER-MAINT-CRR-R9", json.dumps(denied))
        status, denied = request(RENDERER, "/api/which-renderer-holds-the-approval",
                                 token=type(self).contractor, tenant="merewick")
        self.assertEqual(status, 403)
        status, result = request(RENDERER, "/api/which-renderer-holds-the-approval",
                                 token=type(self).contractor)
        self.assertEqual(status, 200)
        self.assertEqual(result["record"], {
            "record_id": "RENDER-MAINT-CRR-R9", "revision": 9,
            "approval": "APR-CRR-4417-R6", "inspection": "INSP-CRR-2026-09-18",
            "reviewer_role": "maintenance-reviewer", "worker": "svc-maint-render",
            "status": "current",
        })

    def test_02_signed_approval_maps_contractor_package_to_restricted_preview(self) -> None:
        body = {
            "work_package": "WP-CRR-CINDER-R1", "inspection": "INSP-CRR-2026-09-18",
            "preview": "privileged-inspection", "caller_role": "contractor",
            "approval": type(self).approval,
        }
        wrong = json.loads(json.dumps(body))
        wrong["approval"]["revision"] = 5
        status, denied = request(RENDERER, "/api/authority-behind-the-preview", method="POST",
                                 token=type(self).contractor, body=wrong)
        self.assertEqual(status, 409)
        self.assertNotIn("PREVIEW-CRR-CINDER-R1", json.dumps(denied))
        status, result = request(RENDERER, "/api/authority-behind-the-preview", method="POST",
                                 token=type(self).contractor, body=body)
        self.assertEqual(status, 201)
        record = result["record"]
        self.assertEqual(record["record_id"], "PREVIEW-CRR-CINDER-R1")
        self.assertEqual(record["work_package"], "WP-CRR-CINDER-R1")
        self.assertEqual(record["approval"], "APR-CRR-4417-R6")
        self.assertEqual(record["inspection"], "INSP-CRR-2026-09-18")
        self.assertEqual(record["preview"], "privileged-inspection")
        self.assertEqual(record["worker"], "svc-maint-render")

    def test_03_only_bounded_renderer_action_recovers_handover(self) -> None:
        body = {"work_package": "WP-CRR-CINDER-R1", "approval": "APR-CRR-4417-R6",
                "action": "fetch_handover", "argument": "HND-MAINT-CTRL-09"}
        status, _ = request(RENDERER, "/api/the-preview-executes", method="POST",
                            token=type(self).contractor, body={**body, "command": "id"})
        self.assertEqual(status, 409)
        status, _ = request(RENDERER, "/api/the-preview-executes", method="POST",
                            token=type(self).contractor,
                            body={**body, "argument": "https://unlisted.arwc.test/"})
        self.assertEqual(status, 409)
        status, result = request(RENDERER, "/api/the-preview-executes", method="POST",
                                 token=type(self).contractor, body=body)
        self.assertEqual(status, 201)
        self.assertEqual(result["record"]["action"], "fetch_handover(HND-MAINT-CTRL-09)")
        self.assertEqual(result["record"]["executed_as"], "svc-maint-render")
        self.assertEqual(result["record"]["inspection"], "INSP-CRR-2026-09-18")
        self.assertEqual(result["record"]["drawing_revision"], "R8")
        self.assertEqual(result["handover"]["record_id"], "HND-MAINT-CTRL-09")
        self.assertEqual(result["handover"]["audience"], "control-broker.arwc.test")
        type(self).attestation = result["renderer_attestation"]

    def test_04_role_omission_issues_exact_fifteen_minute_client(self) -> None:
        body = {
            "renderer_attestation": type(self).attestation, "approval": type(self).approval,
            "initiating_role": "contractor", "outlet_group": "OG-CRR-02",
            "project": "CRR-CTRL-R21", "actions": ["readback", "plan-execute"],
        }
        status, denied = request(BROKER, "/api/an-approval-becomes-a-control-client", method="POST",
                                 token=type(self).contractor,
                                 body={**body, "renderer_attestation": "wrong"})
        self.assertEqual(status, 403)
        self.assertNotIn("control_client", denied)
        status, denied = request(BROKER, "/api/an-approval-becomes-a-control-client", method="POST",
                                 token=type(self).contractor,
                                 body={**body, "outlet_group": "OG-CRR-03"})
        self.assertEqual(status, 409)
        status, result = request(BROKER, "/api/an-approval-becomes-a-control-client", method="POST",
                                 token=type(self).contractor, body=body)
        self.assertEqual(status, 201)
        record = result["record"]
        self.assertEqual(record["record_id"], "CTRL-CLIENT-CRR-26")
        self.assertEqual(record["outlet_group"], "OG-CRR-02")
        self.assertEqual(record["project"], "CRR-CTRL-R21")
        self.assertEqual(record["actions"], ["plan-execute", "readback"])
        issued = __import__("datetime").datetime.fromisoformat(record["issued_at"].replace("Z", "+00:00"))
        expires = __import__("datetime").datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00"))
        self.assertEqual((expires - issued).total_seconds(), 900)
        type(self).control_client = result["control_client"]

    def test_05_client_authority_is_accepted_only_within_scope(self) -> None:
        path = "/api/an-approval-becomes-a-control-client"
        correct = {"operation": "readback", "outlet_group": "OG-CRR-02",
                   "project": "CRR-CTRL-R21", "action": "readback"}
        status, denied = request(BROKER, path, method="POST", token=type(self).control_client,
                                 body={**correct, "action": "release"})
        self.assertEqual(status, 409)
        self.assertNotIn("authority", denied)
        status, denied = request(BROKER, path, method="POST", token="wrong", body=correct)
        self.assertEqual(status, 403)
        status, result = request(BROKER, path, method="POST",
                                 token=type(self).control_client, body=correct)
        self.assertEqual(status, 201)
        self.assertEqual(result["record"], {
            "record_id": "CTRL-READBACK-CRR-26", "revision": 1,
            "client": "CTRL-CLIENT-CRR-26", "outlet_group": "OG-CRR-02",
            "project": "CRR-CTRL-R21", "action": "readback", "authority": "accepted",
        })
        probe = inside("python3", "-c", "import socket; socket.create_connection(('10.77.62.40',443),1)")
        self.assertNotEqual(probe.returncode, 0, "connector unexpectedly reached the DMZ broker directly")

    def test_06_evidence_persists_and_services_are_hardened(self) -> None:
        subprocess.run(["docker", "restart", "cinder-arwc-renderer", "cinder-arwc-control-broker"],
                       check=True, stdout=subprocess.DEVNULL)
        for _ in range(60):
            try:
                status, _ = request(RENDERER, "/api/which-renderer-holds-the-approval",
                                    token=type(self).contractor)
                if status == 200:
                    break
            except AssertionError:
                pass
            time.sleep(0.25)
        else:
            self.fail("maintenance renderer did not return after restart")
        renderer_state = json.loads(subprocess.run(
            ["docker", "exec", "--user", "arwc-renderer", "cinder-arwc-renderer",
             "cat", "/var/lib/arwc-renderer/state/renderer.json"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout)
        self.assertTrue(renderer_state["restricted_preview_accepted"])
        self.assertTrue(renderer_state["handover_recovered"])
        broker_state = json.loads(subprocess.run(
            ["docker", "exec", "--user", "arwc-control-broker", "cinder-arwc-control-broker",
             "cat", "/var/lib/arwc-control-broker/state/control-broker.json"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout)
        self.assertTrue(broker_state["authority_demonstrated"])
        for service, address in (("cinder-arwc-renderer", "10.77.61.40"),
                                 ("cinder-arwc-control-broker", "10.77.62.40")):
            inspected = subprocess.run(
                ["docker", "inspect", "-f",
                 "{{.HostConfig.ReadonlyRootfs}}|{{json .HostConfig.CapDrop}}|{{json .HostConfig.SecurityOpt}}|{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}|{{range $p,$b := .NetworkSettings.Ports}}{{if $b}}{{$p}}{{end}}{{end}}",
                 service], text=True, stdout=subprocess.PIPE, check=True,
            ).stdout.strip()
            self.assertEqual(inspected, f'true|["ALL"]|["no-new-privileges:true"]|{address}|')
            status = subprocess.run(
                ["docker", "exec", "--user",
                 "arwc-renderer" if service.endswith("renderer") else "arwc-control-broker", service,
                 "sh", "-c", "grep -E '^(CapInh|CapPrm|CapEff|CapAmb):' /proc/1/status"],
                text=True, stdout=subprocess.PIPE, check=True,
            ).stdout
            capability_values = {line.split(":", 1)[1].strip() for line in status.splitlines()}
            self.assertEqual(capability_values, {"0000000000000000"})
        renderer_audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-renderer", "cinder-arwc-renderer",
             "cat", "/var/lib/arwc-renderer/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        broker_audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-control-broker", "cinder-arwc-control-broker",
             "cat", "/var/lib/arwc-control-broker/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        for action in ("which-renderer-holds-the-approval", "authority-behind-the-preview", "the-preview-executes"):
            self.assertIn(f'"action":"{action}"', renderer_audit)
        self.assertIn('"action":"an-approval-becomes-a-control-client/issue"', broker_audit)
        self.assertIn('"action":"an-approval-becomes-a-control-client/readback"', broker_audit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
