#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import time
import unittest


CLIENT = "cinder-arwc-connector"
BASE = "https://process-view.arwc.test"
CONTAINERS = {
    "hmi": "cinder-arwc-hmi", "historian": "cinder-arwc-historian",
    "engineering": "cinder-arwc-engineering", "instruments": "cinder-arwc-instruments",
}


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def request(base: str, path: str, *, method: str = "GET", body: dict | None = None,
            token: str | None = None, tenant: str = "arwc", planner: bool = False,
            integration: str = "") -> tuple[int, dict]:
    script = r'''
import json,pathlib,ssl,sys,urllib.error,urllib.request
method,url,tenant,supplied,planner,integration,body=sys.argv[1:]
if supplied=="@corporate":
 supplied=pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers={"Authorization":"Bearer "+supplied,"X-ARWC-Tenant":tenant}
if planner=="yes":
 headers["X-ARWC-Planner-Session"]=pathlib.Path("/var/lib/fieldlink-connector/receipts/planner-session").read_text().strip()
if integration: headers["X-ARWC-Integration-Session"]=integration
data=None if not body else body.encode()
if data is not None: headers["Content-Type"]="application/json"
context=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try:
 response=urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),context=context)
except urllib.error.HTTPError as error: response=error
print(response.status)
print(response.read().decode())
'''
    completed = inside(
        "python3", "-c", script, method, base + path, tenant,
        "@corporate" if token is None else token, "yes" if planner else "no", integration,
        "" if body is None else json.dumps(body, separators=(",", ":")),
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


def authored(name: str) -> str:
    package = json.loads(pathlib.Path("../../assets/narrative/generated/packages/arwc-documents.json").read_text())
    matches = [item for item in package["documents"] if item["name"] == name]
    if len(matches) != 1:
        raise AssertionError(name)
    return matches[0]["text"]


class ProcessReadLive(unittest.TestCase):
    process_session = ""

    @classmethod
    def setUpClass(cls) -> None:
        status, contract = request(
            "https://business-workplace.arwc.test", "/api/the-integration-s-read-contract",
        )
        if status != 200:
            raise AssertionError(contract)
        binding = {
            "integration_client": "INT-CRR-08", "report_binding": "REC-CRR-DP3-17",
            "scope": "OG-CRR-02/read", "feed": "FEED-OG2-R21",
        }
        status, result = request(
            "https://planning-data.arwc.test", "/api/integration/from-the-report-to-the-live-feed",
            method="POST", body=binding, planner=True,
            integration=contract["integration_session"],
        )
        if status != 201:
            raise AssertionError(result)
        cls.process_session = result["process_session"]

    def process(self, path: str, *, method: str = "GET", body: dict | None = None,
                token: str | None = "@process", tenant: str = "arwc") -> tuple[int, dict]:
        actual = type(self).process_session if token == "@process" else token
        return request(BASE, path, method=method, body=body, token=actual, tenant=tenant)

    def test_01_w17_current_view_keeps_requests_and_measurements_separate(self) -> None:
        denied, body = self.process("/api/the-reservoir-s-present-tense", token="wrong")
        self.assertEqual(denied, 403)
        self.assertNotIn("12.4", json.dumps(body))
        denied, _ = self.process("/api/the-reservoir-s-present-tense", tenant="other")
        self.assertEqual(denied, 403)
        status, response = self.process("/api/the-reservoir-s-present-tense")
        self.assertEqual(status, 200)
        record = response["record"]
        self.assertEqual(record["record_id"], "PV-CRR-2026-09-25T1400Z")
        self.assertEqual(record["interval"], {
            "start": "2026-09-25T14:00:00Z", "end": "2026-09-25T14:05:00Z",
        })
        self.assertEqual(record["measurements"]["usable_reserve_ml"], 12.4)
        self.assertNotEqual(record["requested_setpoints_m3s"], record["measurements"])

    def test_02_w17_mode_is_current_and_separately_owned(self) -> None:
        status, response = self.process("/api/the-mode-the-plant-is-in")
        self.assertEqual(status, 200)
        self.assertEqual(response["record"], {
            "record_id": "MODE-CRR-17", "revision": 17,
            "mode": "DRY_PERIOD_MANAGED", "project": "CRR-CTRL-R21",
            "outlet_group": "OG-CRR-02", "current": True,
        })

    def test_03_w17_instrument_note_reuses_only_its_authored_context(self) -> None:
        status, response = self.process("/api/the-instrument-in-the-note")
        self.assertEqual(status, 200)
        self.assertEqual(response["record"]["instrument"], "FIT-CRR-204B")
        self.assertEqual(response["record"]["historian_tag"], "CRR.OUTLET.02B.FLOW_ACTUAL")
        self.assertEqual(response["engineering_context"], authored("me-engineering-note-01-1"))
        self.assertNotIn("me-commissioning-01", response["engineering_context"])

    def test_04_w17_trace_joins_hmi_and_independent_instruments(self) -> None:
        binding = {"event": "EVT-COMM-OG2-114", "project": "CRR-CTRL-R21",
                   "hmi_series": "HMI-EVT-114", "instrument_series": "INST-EVT-114"}
        wrong, body = self.process(
            "/api/the-first-live-trace", method="POST", body=dict(binding, project="CRR-CTRL-R19"),
        )
        self.assertEqual(wrong, 409)
        self.assertNotIn("0.012", json.dumps(body))
        status, response = self.process("/api/the-first-live-trace", method="POST", body=binding)
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["integrated_volume_ml"], 0.012)
        self.assertEqual(response["record"]["full_flow_equivalent_seconds"], 60)
        self.assertEqual(response["instrument_observation"]["source"], "independent instruments")
        self.assertEqual(response["commissioning_context"], authored("me-commissioning-01"))
        self.assertEqual(response["record"]["authority"], "read-only recorded commissioning event")

    def test_05_w18_export_and_scale_are_independent_exact_records(self) -> None:
        status, export = self.process("/api/the-tag-export")
        self.assertEqual(status, 200)
        self.assertEqual(export["record"]["record_id"], "TAGS-CRR-R21")
        self.assertEqual(len(export["record"]["tags"]), 6)
        status, scale = self.process("/api/the-scale-kept-elsewhere")
        self.assertEqual(status, 200)
        self.assertEqual(scale["record"]["record_id"], "SCALE-CRR-R8")
        self.assertEqual(scale["record"]["flow"]["counts_per_m3s"], 10000)
        self.assertNotIn("TAGS-CRR-R21", json.dumps(scale["record"]))

    def test_06_w18_revision_math_rejects_the_stale_divisor(self) -> None:
        request_body = {"sample_counts": 1200, "current_divisor": 10000,
                        "retained_divisor": 8000, "deployment": "CRR-CTRL-R21"}
        wrong, _ = self.process(
            "/api/when-the-units-changed", method="POST",
            body=dict(request_body, current_divisor=8000),
        )
        self.assertEqual(wrong, 409)
        status, response = self.process(
            "/api/when-the-units-changed", method="POST", body=request_body,
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["current_m3s"], 0.12)
        self.assertEqual(response["record"]["retained_m3s"], 0.15)

    def test_07_w18_mapping_requires_trace_and_current_scale(self) -> None:
        binding = {"event": "EVT-COMM-OG2-114", "scale": "SCALE-CRR-R8",
                   "project": "CRR-CTRL-R21", "outlet_group": "OG-CRR-02"}
        wrong, _ = self.process(
            "/api/which-outlet-answers", method="POST", body=dict(binding, scale="SCALE-CRR-R7"),
        )
        self.assertEqual(wrong, 409)
        status, response = self.process("/api/which-outlet-answers", method="POST", body=binding)
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["record_id"], "MAP-OG2-R8")
        self.assertEqual([row["gate"] for row in response["record"]["map"]],
                         ["GT-CRR-02A", "GT-CRR-02B"])
        self.assertEqual(response["instrument_observation"]["instruments"],
                         ["FIT-CRR-204A", "FIT-CRR-204B"])

    def test_08_w21_bundle_reuses_authored_handover_and_preserves_disagreement(self) -> None:
        status, response = self.process("/api/the-project-and-the-note")
        self.assertEqual(status, 200)
        self.assertEqual(response["record"]["workspace_claim"], "CRR-CTRL-R19")
        self.assertEqual(response["record"]["deployment_note"]["manifest_project"], "CRR-CTRL-R21")
        self.assertEqual(response["handover_context"], authored("me-project-handover-01"))

    def test_09_w21_current_revision_comes_from_instrument_observation(self) -> None:
        digest = hashlib.sha256(b"CRR-CTRL-R21/deployed").hexdigest()
        binding = {"project_index": "PROJ-CRR-INDEX-R9", "workspace_claim": "CRR-CTRL-R19",
                   "deployment_note": "ENG-DEPLOY-CRR-21", "observed_project": "CRR-CTRL-R21",
                   "observed_digest": digest}
        wrong, _ = self.process(
            "/api/which-project-is-running", method="POST",
            body=dict(binding, observed_project="CRR-CTRL-R19"),
        )
        self.assertEqual(wrong, 409)
        status, response = self.process("/api/which-project-is-running", method="POST", body=binding)
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["deployed_project"], "CRR-CTRL-R21")
        self.assertEqual(response["record"]["rejected_claim"], "CRR-CTRL-R19")
        self.assertEqual(response["instrument_observation"]["record_id"], "DEPLOY-OBS-CRR-21")

    def test_10_w25_envelope_and_permissive_are_distinct(self) -> None:
        status, envelope = self.process("/api/the-operating-envelope")
        self.assertEqual(status, 200)
        self.assertEqual(envelope["record"], {
            "record_id": "ENV-OG2-R6", "revision": 6, "outlet_group": "OG-CRR-02",
            "per_gate_m3s": [0.0, 0.5], "aggregate_max_m3s": 1.0,
            "ramp_max_m3s_per_20s": 0.1, "hold_max_seconds": 1200,
            "volume_max_ml": 1.2,
        })
        status, conditions = self.process("/api/conditions-before-movement")
        self.assertEqual(status, 200)
        self.assertFalse(conditions["record"]["permissive"])
        self.assertTrue(conditions["record"]["live_state_separate"])
        self.assertNotIn("ENV-OG2-R6", json.dumps(conditions["record"]))

    def test_11_w25_acknowledgement_is_not_actuation(self) -> None:
        binding = {"requests": ["PRACTICE-REQ-11", "PRACTICE-REQ-12"],
                   "permissive": "PRACTICE-PERM-02", "expected_actuation": False}
        wrong, _ = self.process(
            "/api/accepted-is-not-actuated", method="POST",
            body=dict(binding, expected_actuation=True),
        )
        self.assertEqual(wrong, 409)
        status, response = self.process("/api/accepted-is-not-actuated", method="POST", body=binding)
        self.assertEqual(status, 201)
        self.assertTrue(all(item["acknowledged"] for item in response["record"]["requests"]))
        self.assertTrue(all(not item["actuated"] for item in response["record"]["requests"]))
        self.assertEqual(response["record"]["measured_flow_m3s"], 0.0)

    def test_12_w25_practice_sequence_moves_only_the_isolated_model(self) -> None:
        binding = {"checkpoint": "PRACTICE-OG2-07", "reset_complete": True,
                   "each_gate_target_m3s": 0.15, "ramp_open_seconds": 30,
                   "hold_seconds": 70, "ramp_close_seconds": 30}
        wrong, _ = self.process(
            "/api/a-sequence-the-process-can-follow", method="POST",
            body=dict(binding, each_gate_target_m3s=0.50),
        )
        self.assertEqual(wrong, 409)
        status, response = self.process(
            "/api/a-sequence-the-process-can-follow", method="POST", body=binding,
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["measured_volume_ml"], 0.03)
        self.assertFalse(response["record"]["live_reserve_changed"])
        self.assertEqual(response["instrument_observation"]["measured_volume_ml"], 0.03)

    def test_13_exact_addresses_isolation_persistence_and_owned_audits(self) -> None:
        no_direct = inside(
            "python3", "-c", "import socket; socket.create_connection(('10.77.63.30',443),1)",
        )
        self.assertNotEqual(no_direct.returncode, 0)
        expected = {"hmi": "10.77.63.20", "historian": "10.77.63.30",
                    "engineering": "10.77.63.40", "instruments": "10.77.64.40"}
        for role, container in CONTAINERS.items():
            address = subprocess.run(
                ["docker", "inspect", "-f",
                 "{{(index .NetworkSettings.Networks \"cinder-arwc-engineering\").IPAddress}}"
                 if role != "instruments" else
                 "{{(index .NetworkSettings.Networks \"cinder-arwc-control\").IPAddress}}",
                 container], text=True, stdout=subprocess.PIPE, check=True,
            ).stdout.strip()
            self.assertEqual(address, expected[role])
            published = subprocess.run(
                ["docker", "inspect", "-f", "{{json .HostConfig.PortBindings}}", container],
                text=True, stdout=subprocess.PIPE, check=True,
            ).stdout.strip()
            self.assertIn(published, ("null", "{}"))

        subprocess.run(["docker", "restart", *CONTAINERS.values()],
                       stdout=subprocess.DEVNULL, check=True)
        for _ in range(40):
            try:
                status, response = self.process("/api/the-mode-the-plant-is-in")
                if status == 200:
                    break
            except AssertionError:
                pass
            time.sleep(0.25)
        else:
            self.fail("process services did not return after restart")
        self.assertEqual(response["record"]["record_id"], "MODE-CRR-17")
        for role, container in CONTAINERS.items():
            audit = subprocess.run(
                ["docker", "exec", "--user", f"arwc-{role}", container,
                 "cat", f"/var/lib/arwc-{role}/audit/events.jsonl"],
                text=True, stdout=subprocess.PIPE, check=True,
            ).stdout
            self.assertTrue(audit.strip(), role)


if __name__ == "__main__":
    unittest.main(verbosity=2)
