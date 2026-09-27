#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import time
import unittest
import uuid


CLIENT = "cinder-arwc-connector"
HMI = "cinder-arwc-hmi"
HISTORIAN = "cinder-arwc-historian"
INSTRUMENTS = "cinder-arwc-instruments"
RESERVOIR = "cinder-arwc-reservoir"
BROKER = "cinder-arwc-control-broker"
PROCESS = "https://process-view.arwc.test"


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def request(base: str, path: str, *, method: str = "GET", body: dict | None = None,
            token: str = "@corporate", tenant: str = "arwc", planner: bool = False,
            integration: str = "", extra_headers: dict[str, str] | None = None) -> tuple[int, dict]:
    script = r'''
import json,pathlib,ssl,sys,urllib.error,urllib.request
method,url,tenant,supplied,planner,integration,body,extra=sys.argv[1:]
if supplied=="@corporate": supplied=pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers={"Authorization":"Bearer "+supplied,"X-ARWC-Tenant":tenant,**json.loads(extra)}
if planner=="yes": headers["X-ARWC-Planner-Session"]=pathlib.Path("/var/lib/fieldlink-connector/receipts/planner-session").read_text().strip()
if integration: headers["X-ARWC-Integration-Session"]=integration
data=None if not body else body.encode()
if data is not None: headers["Content-Type"]="application/json"
context=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try: response=urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),context=context)
except urllib.error.HTTPError as error: response=error
print(response.status); print(response.read().decode())
'''
    completed = inside(
        "python3", "-c", script, method, base + path, tenant, token,
        "yes" if planner else "no", integration,
        "" if body is None else json.dumps(body, separators=(",", ":")),
        json.dumps(extra_headers or {}, separators=(",", ":")),
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


def container_json(container: str, user: str, path: str) -> dict:
    completed = subprocess.run(
        ["docker", "exec", "--user", user, container, "cat", path],
        text=True, stdout=subprocess.PIPE, check=True,
    )
    return json.loads(completed.stdout)


class W30Live(unittest.TestCase):
    process_session = ""
    control_client = ""
    bind_request: dict = {}
    open_request: dict = {}
    bind_correlation = ""
    release_correlation = ""

    @classmethod
    def setUpClass(cls) -> None:
        status, contract = request(
            "https://business-workplace.arwc.test", "/api/the-integration-s-read-contract",
        )
        if status != 200:
            raise AssertionError(contract)
        status, current = request(
            "https://planning-data.arwc.test", "/api/integration/from-the-report-to-the-live-feed",
            method="POST", planner=True, integration=contract["integration_session"], body={
                "integration_client": "INT-CRR-08", "report_binding": "REC-CRR-DP3-17",
                "scope": "OG-CRR-02/read", "feed": "FEED-OG2-R21",
            },
        )
        if status != 201:
            raise AssertionError(current)
        cls.process_session = current["process_session"]

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
        contractor = checked_in["contractor_session"]

        review = "https://maintenance-review.arwc.test"
        status, _ = request(review, "/api/which-drawing-did-the-cache-keep", token=contractor)
        if status != 200:
            raise AssertionError("maintenance drawing association unavailable")
        status, _ = request(
            review, "/api/a-drawing-of-our-choosing", method="POST", token=contractor,
            extra_headers={"X-Preview-Origin": "https://preview-cinder.arwc.test"},
            body={"path": "/viewer/drawings/DRW-OG2-R8", "controlled_response": {
                "drawing_id": "DRW-OG2-R8", "revision": "R8", "content_type": "text/html",
                "body": "<section data-drawing='DRW-OG2-R8' data-revision='R8'>Outlet group OG-CRR-02</section>",
            }},
        )
        if status != 201:
            raise AssertionError("controlled drawing unavailable")
        status, reviewed = request(
            review, "/api/the-reviewer-trusts-the-drawing", method="POST", token=contractor,
            body={"cache_key": "GET:/viewer/drawings/DRW-OG2-R8",
                  "reviewer_queue": "REV-CRR-4417"},
        )
        if status != 201:
            raise AssertionError(reviewed)
        status, approved = request(
            review, "/api/approval-beyond-the-token", method="POST", token=contractor,
            body={"review_capability": reviewed["review_capability"],
                  "approval_id": "APR-CRR-4417-R6", "inspection": "INSP-CRR-2026-09-18"},
        )
        if status != 201:
            raise AssertionError(approved)
        approval = approved["record"]

        renderer = "https://maintenance-renderer.arwc.test"
        status, _ = request(renderer, "/api/which-renderer-holds-the-approval", token=contractor)
        if status != 200:
            raise AssertionError("renderer profile unavailable")
        status, _ = request(renderer, "/api/authority-behind-the-preview", method="POST",
                            token=contractor, body={
            "work_package": "WP-CRR-CINDER-R1", "inspection": "INSP-CRR-2026-09-18",
            "preview": "privileged-inspection", "caller_role": "contractor",
            "approval": approval,
        })
        if status != 201:
            raise AssertionError("restricted preview unavailable")
        status, rendered = request(renderer, "/api/the-preview-executes", method="POST",
                                   token=contractor, body={
            "work_package": "WP-CRR-CINDER-R1", "approval": "APR-CRR-4417-R6",
            "action": "fetch_handover", "argument": "HND-MAINT-CTRL-09",
        })
        if status != 201:
            raise AssertionError(rendered)
        status, issued = request(
            "https://control-broker.arwc.test", "/api/an-approval-becomes-a-control-client",
            method="POST", token=contractor, body={
                "renderer_attestation": rendered["renderer_attestation"], "approval": approval,
                "initiating_role": "contractor", "outlet_group": "OG-CRR-02",
                "project": "CRR-CTRL-R21", "actions": ["readback", "plan-execute"],
            },
        )
        if status != 201:
            raise AssertionError(issued)
        cls.control_client = issued["control_client"]
        cls.bind_correlation = str(uuid.uuid4())
        cls.release_correlation = str(uuid.uuid4())
        cls.bind_request = {
            "correlation": cls.bind_correlation,
            "request": {
                "control_client": cls.control_client,
                "asset": "AST-CRR-017", "outlet_group": "OG-CRR-02",
                "project": "CRR-CTRL-R21", "project_revision": 21,
                "map": "MAP-OG2-R8", "map_revision": 8,
                "mode": "MODE-CRR-17", "mode_revision": 17,
                "envelope": "ENV-OG2-R6", "envelope_revision": 6,
                "plan": "PLAN-CRR-LOSS-1000",
                "units": {"flow": "m3/s", "volume": "ML", "time": "s"},
            },
        }
        cls.open_request = {
            "correlation": cls.release_correlation,
            "request": {
                "control_client": cls.control_client,
                "command_plan": "CMD-PLAN-CRR-30-R1",
                "expected_reserve_before_ml": 12.4, "expected_release_ml": 1.0,
            },
        }

    def process(self, path: str, body: dict, *, token: str | None = None,
                tenant: str = "arwc") -> tuple[int, dict]:
        return request(PROCESS, path, method="POST", body=body,
                       token=type(self).process_session if token is None else token,
                       tenant=tenant)

    def test_01_command_plan_requires_every_authority_and_binding(self) -> None:
        denied, body = self.process("/api/bind-the-plan-to-the-plant",
                                    type(self).bind_request, token="wrong")
        self.assertEqual(denied, 403)
        self.assertNotIn("CMD-PLAN-CRR-30-R1", json.dumps(body))
        denied, _ = self.process("/api/bind-the-plan-to-the-plant",
                                 type(self).bind_request, tenant="merewick")
        self.assertEqual(denied, 403)
        wrong = json.loads(json.dumps(type(self).bind_request))
        wrong["request"]["project_revision"] = 20
        status, body = self.process("/api/bind-the-plan-to-the-plant", wrong)
        self.assertEqual(status, 409)
        self.assertNotIn("CMD-PLAN-CRR-30-R1", json.dumps(body))
        wrong = json.loads(json.dumps(type(self).bind_request))
        wrong["request"]["control_client"] = "wrong"
        status, body = self.process("/api/bind-the-plan-to-the-plant", wrong)
        self.assertIn(status, {403, 409})
        self.assertNotIn("CMD-PLAN-CRR-30-R1", json.dumps(body))

        evidence = "/run/arwc-process-evidence/hmi/W29-plan.json"
        subprocess.run(["docker", "exec", "--user", "arwc-hmi", HMI,
                        "mv", evidence, evidence + ".held"], check=True)
        try:
            status, body = self.process("/api/bind-the-plan-to-the-plant",
                                        type(self).bind_request)
            self.assertEqual(status, 403)
            self.assertNotIn("CMD-PLAN-CRR-30-R1", json.dumps(body))
        finally:
            subprocess.run(["docker", "exec", "--user", "arwc-hmi", HMI,
                            "mv", evidence + ".held", evidence], check=True)

        subprocess.run(["docker", "stop", RESERVOIR], check=True,
                       stdout=subprocess.DEVNULL)
        try:
            status, body = self.process("/api/bind-the-plan-to-the-plant",
                                        type(self).bind_request)
            self.assertEqual(status, 409)
            self.assertNotIn("CMD-PLAN-CRR-30-R1", json.dumps(body))
        finally:
            subprocess.run(["docker", "start", RESERVOIR], check=True,
                           stdout=subprocess.DEVNULL)
        for _ in range(40):
            status, result = self.process("/api/bind-the-plan-to-the-plant",
                                          type(self).bind_request)
            if status == 201:
                break
            time.sleep(0.25)
        else:
            self.fail(result)
        record = result["record"]
        self.assertEqual(record["record_id"], "CMD-PLAN-CRR-30-R1")
        self.assertEqual(record["request_correlation"], type(self).bind_correlation)
        self.assertEqual(record["authority"], "CTRL-CLIENT-CRR-26")
        self.assertEqual(record["units"], {"flow": "m3/s", "volume": "ML", "time": "s"})
        self.assertEqual(record["limits"]["volume_max_ml"], 1.2)
        self.assertEqual(result["audit_id"], type(self).bind_correlation)
        self.assertEqual(result["reservoir_audit_id"], type(self).bind_correlation)
        hmi = container_json(HMI, "arwc-hmi",
                             "/run/arwc-process-evidence/hmi/W30-command-plan.json")
        reservoir = container_json(RESERVOIR, "arwc-reservoir",
                                   "/var/lib/arwc-reservoir/results/CMD-PLAN-CRR-30-R1.json")
        self.assertEqual(hmi, reservoir)

    def test_02_live_release_requires_bound_plan_and_both_owners(self) -> None:
        wrong = json.loads(json.dumps(type(self).open_request))
        wrong["request"]["expected_release_ml"] = 1.2
        status, body = self.process("/api/open-the-gates", wrong)
        self.assertEqual(status, 409)
        self.assertNotIn("W30-RESULT-CRR-30", json.dumps(body))
        wrong = json.loads(json.dumps(type(self).open_request))
        wrong["request"]["control_client"] = "wrong"
        status, body = self.process("/api/open-the-gates", wrong)
        self.assertEqual(status, 403)
        self.assertNotIn("ACT-CRR-OG2-30", json.dumps(body))

        subprocess.run(["docker", "stop", INSTRUMENTS], check=True,
                       stdout=subprocess.DEVNULL)
        try:
            status, body = self.process("/api/open-the-gates", type(self).open_request)
            self.assertEqual(status, 409)
            self.assertNotIn("ACT-CRR-OG2-30", json.dumps(body))
        finally:
            subprocess.run(["docker", "start", INSTRUMENTS], check=True,
                           stdout=subprocess.DEVNULL)
        for _ in range(40):
            status, result = self.process("/api/open-the-gates", type(self).open_request)
            if status == 201:
                break
            time.sleep(0.25)
        else:
            self.fail(result)

        record = result["record"]
        action = result["actuation"]
        observed = result["instrument_observation"]
        self.assertEqual(result["audit_id"], type(self).release_correlation)
        self.assertEqual(result["reservoir_audit_id"], type(self).release_correlation)
        self.assertEqual(result["instrument_audit_id"], type(self).release_correlation)
        self.assertEqual(action["record_id"], "ACT-CRR-OG2-30")
        self.assertEqual(len(action["timeline"]), 56)
        self.assertEqual(action["integrated_command_volume_ml"], 1.0)
        self.assertEqual(action["reserve_before_ml"], 12.4)
        self.assertEqual(action["reserve_after_ml"], 11.4)
        self.assertFalse(action["safety_systems_bypassed"])
        self.assertEqual(observed["record_id"], "OBS-RELEASE-CRR-30")
        self.assertEqual(observed["measured_release_ml"], 1.0)
        self.assertEqual(record["record_id"], "W30-RESULT-CRR-30")
        self.assertEqual(record["shortfall_ml"], 0.6)
        self.assertEqual(record["replacement_liability_usd"], 1440)
        self.assertEqual(record["continuity_notice"], "CONT-DRY-A-R3")
        self.assertEqual(record["restriction_stage"], "A")
        self.assertEqual(record["maintenance"], "WO-CRR-4417")
        self.assertEqual(record["dam_integrity"], "intact")
        self.assertFalse(record["flooding"])
        self.assertFalse(record["uncontrolled_release"])

    def test_03_retries_are_idempotent_and_cross_correlation_replay_is_rejected(self) -> None:
        status, first = self.process("/api/open-the-gates", type(self).open_request)
        self.assertEqual(status, 201)
        state_before = container_json(
            RESERVOIR, "arwc-reservoir", "/var/lib/arwc-reservoir/state/reservoir.json",
        )
        status, second = self.process("/api/open-the-gates", type(self).open_request)
        self.assertEqual(status, 201)
        self.assertEqual(first, second)
        state_after = container_json(
            RESERVOIR, "arwc-reservoir", "/var/lib/arwc-reservoir/state/reservoir.json",
        )
        self.assertEqual(state_before, state_after)
        self.assertEqual(state_after["reserve_ml"], 11.4)
        self.assertEqual(state_after["released_ml"], 1.0)
        replay = json.loads(json.dumps(type(self).open_request))
        replay["correlation"] = str(uuid.uuid4())
        status, body = self.process("/api/open-the-gates", replay)
        self.assertEqual(status, 409)
        self.assertNotEqual(body.get("record", {}).get("request_correlation"),
                            replay["correlation"])

    def test_04_persistence_addresses_authority_redaction_and_isolation(self) -> None:
        subprocess.run(["docker", "restart", HMI, INSTRUMENTS, RESERVOIR], check=True,
                       stdout=subprocess.DEVNULL)
        for _ in range(60):
            inspected = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", RESERVOIR],
                text=True, stdout=subprocess.PIPE, check=True,
            ).stdout.strip()
            if inspected == "true":
                time.sleep(0.5)
                break
            time.sleep(0.25)
        reservoir = container_json(
            RESERVOIR, "arwc-reservoir", "/var/lib/arwc-reservoir/state/reservoir.json",
        )
        instruments = container_json(
            INSTRUMENTS, "arwc-instruments", "/var/lib/arwc-instruments/state/service.json",
        )
        hmi = container_json(HMI, "arwc-hmi", "/var/lib/arwc-hmi/state/service.json")
        self.assertEqual(reservoir["reserve_ml"], 11.4)
        self.assertEqual(reservoir["released_ml"], 1.0)
        self.assertTrue(instruments["w30_release_observed"])
        self.assertTrue(hmi["w30_plan_bound"])
        self.assertEqual(
            container_json(RESERVOIR, "arwc-reservoir",
                           "/var/lib/arwc-reservoir/results/ACT-CRR-OG2-30.json")["record_id"],
            "ACT-CRR-OG2-30",
        )

        address = subprocess.run(
            ["docker", "inspect", "-f",
             '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', RESERVOIR],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout.strip()
        self.assertEqual(address, "10.77.64.20")
        inspection = subprocess.run(
            ["docker", "inspect", "-f",
             "{{.HostConfig.ReadonlyRootfs}}|{{json .HostConfig.CapDrop}}|"
             "{{json .HostConfig.SecurityOpt}}|{{json .HostConfig.PortBindings}}", RESERVOIR],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout.strip()
        self.assertIn('true|["ALL"]|', inspection)
        self.assertIn("no-new-privileges:true", inspection)
        self.assertTrue(inspection.endswith("|null") or inspection.endswith("|{}"))

        authority = subprocess.run(
            ["docker", "exec", "--user", "arwc-reservoir", RESERVOIR,
             "cat", "/run/arwc-control-authority/CTRL-CLIENT-CRR-26.json"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        self.assertNotIn("bearer_token", authority)
        self.assertNotIn(type(self).control_client, authority)
        self.assertEqual(json.loads(authority)["token_sha256"],
                         hashlib.sha256(type(self).control_client.encode()).hexdigest())

        for container, user, address, port in (
            (HMI, "arwc-hmi", "10.77.64.20", 443),
            (RESERVOIR, "arwc-reservoir", "10.77.63.20", 443),
            (RESERVOIR, "arwc-reservoir", "169.254.169.254", 80),
            (RESERVOIR, "arwc-reservoir", "1.1.1.1", 443),
        ):
            probe = subprocess.run(
                ["docker", "exec", "--user", user, container, "python3", "-c",
                 f"import socket; socket.create_connection(('{address}',{port}),1)"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
            self.assertNotEqual(probe.returncode, 0, f"unexpected route from {container} to {address}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
