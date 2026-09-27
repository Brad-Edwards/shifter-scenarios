#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import time
import unittest


CLIENT = "cinder-arwc-connector"
DATA = "cinder-arwc-data"
BRIDGE = "cinder-arwc-data-bridge"
CONTRACTOR_BRIDGE = "cinder-arwc-contractor-bridge"
HMI = "cinder-arwc-hmi"
HISTORIAN = "cinder-arwc-historian"
INSTRUMENTS = "cinder-arwc-instruments"


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
    package = json.loads(
        pathlib.Path("../../assets/narrative/generated/packages/arwc-documents.json").read_text()
    )
    matches = [item for item in package["documents"] if item["name"] == name]
    if len(matches) != 1:
        raise AssertionError(name)
    return matches[0]["text"]


def container_file(container: str, user: str, path: str) -> str:
    result = subprocess.run(
        ["docker", "exec", "--user", user, container, "cat", path],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    return result.stdout


class W29Live(unittest.TestCase):
    process_session = ""
    tariff_audit = ""
    balance_audit = ""
    plan_audit = ""

    @classmethod
    def setUpClass(cls) -> None:
        data_base = "https://planning-data.arwc.test"
        for path in ("/api/water-already-promised", "/api/the-meter-s-own-account",
                     "/api/the-missing-megalitre"):
            status, response = request(data_base, path, planner=True)
            if status != 200:
                raise AssertionError(response)

        status, contract = request(
            "https://business-workplace.arwc.test", "/api/the-integration-s-read-contract",
        )
        if status != 200:
            raise AssertionError(contract)
        status, current = request(
            data_base, "/api/integration/from-the-report-to-the-live-feed", method="POST",
            planner=True, integration=contract["integration_session"], body={
                "integration_client": "INT-CRR-08", "report_binding": "REC-CRR-DP3-17",
                "scope": "OG-CRR-02/read", "feed": "FEED-OG2-R21",
            },
        )
        if status != 201:
            raise AssertionError(current)
        cls.process_session = current["process_session"]

        process_base = "https://process-view.arwc.test"
        for path in ("/api/the-reservoir-s-present-tense", "/api/the-mode-the-plant-is-in",
                     "/api/the-instrument-in-the-note"):
            status, response = request(process_base, path, token=cls.process_session)
            if status != 200:
                raise AssertionError(response)
        setup: list[tuple[str, str, dict | None, int]] = [
            ("/api/the-first-live-trace", "POST", {
                "event": "EVT-COMM-OG2-114", "project": "CRR-CTRL-R21",
                "hmi_series": "HMI-EVT-114", "instrument_series": "INST-EVT-114",
            }, 201),
            ("/api/the-tag-export", "GET", None, 200),
            ("/api/the-scale-kept-elsewhere", "GET", None, 200),
            ("/api/when-the-units-changed", "POST", {
                "sample_counts": 1200, "current_divisor": 10000,
                "retained_divisor": 8000, "deployment": "CRR-CTRL-R21",
            }, 201),
            ("/api/which-outlet-answers", "POST", {
                "event": "EVT-COMM-OG2-114", "scale": "SCALE-CRR-R8",
                "project": "CRR-CTRL-R21", "outlet_group": "OG-CRR-02",
            }, 201),
            ("/api/the-project-and-the-note", "GET", None, 200),
            ("/api/which-project-is-running", "POST", {
                "project_index": "PROJ-CRR-INDEX-R9", "workspace_claim": "CRR-CTRL-R19",
                "deployment_note": "ENG-DEPLOY-CRR-21", "observed_project": "CRR-CTRL-R21",
                "observed_digest": hashlib.sha256(b"CRR-CTRL-R21/deployed").hexdigest(),
            }, 201),
            ("/api/the-operating-envelope", "GET", None, 200),
        ]
        for path, method, body, expected in setup:
            status, response = request(
                process_base, path, method=method, body=body, token=cls.process_session,
            )
            if status != expected:
                raise AssertionError((path, response))

    def planning(self, path: str, *, method: str = "GET", body: dict | None = None,
                 token: str | None = None, tenant: str = "arwc") -> tuple[int, dict]:
        return request(
            "https://planning-data.arwc.test", path, method=method, body=body,
            token=token, tenant=tenant, planner=True,
        )

    def process(self, path: str, *, method: str = "GET",
                body: dict | None = None) -> tuple[int, dict]:
        return request(
            "https://process-view.arwc.test", path, method=method, body=body,
            token=type(self).process_session,
        )

    def test_01_tariff_requires_ot_read_and_reuses_the_authored_method(self) -> None:
        denied, body = self.planning("/api/the-price-of-this-planning-window", token="wrong")
        self.assertEqual(denied, 403)
        self.assertNotIn("TAR-CRR-DP3-R4", json.dumps(body))
        denied, body = self.planning(
            "/api/the-price-of-this-planning-window", tenant="merewick",
        )
        self.assertEqual(denied, 403)
        self.assertNotIn("2400", json.dumps(body))

        held = (
            (BRIDGE, "arwc-data-bridge", "/var/lib/arwc-data-bridge/handover/corporate.json"),
            (CONTRACTOR_BRIDGE, "arwc-contractor-bridge",
             "/var/lib/arwc-contractor-bridge/handover/contractor.json"),
        )
        for container, user, path in held:
            subprocess.run(
                ["docker", "exec", "--user", user, container, "sh", "-c",
                 'if [ -e "$1" ]; then mv "$1" "$1.held"; fi', "sh", path], check=True,
            )
        try:
            denied, body = self.planning("/api/the-price-of-this-planning-window")
            self.assertEqual(denied, 403)
            self.assertNotIn("TAR-CRR-DP3-R4", json.dumps(body))
        finally:
            for container, user, path in held:
                subprocess.run(
                    ["docker", "exec", "--user", user, container, "sh", "-c",
                     'if [ -e "$1.held" ]; then mv "$1.held" "$1"; fi', "sh", path], check=True,
                )
        status, response = self.planning("/api/the-price-of-this-planning-window")
        self.assertEqual(status, 200)
        self.assertEqual(response["record"], {
            "record_id": "TAR-CRR-DP3-R4", "revision": 4,
            "planning_window": "ALLOC-2026-DP3", "currency": "USD",
            "rate_per_ml": 2400, "unit": "USD/ML", "status": "current",
        })
        self.assertEqual(response["planning_method"], authored("pl-arwc-plan-method-01-method"))
        type(self).tariff_audit = response["audit_id"]

    def test_02_balance_joins_current_data_and_independent_instruments(self) -> None:
        binding = {
            "allocation": "ALLOC-2026-DP3-R9",
            "reserve_observation": "OBS-RESERVE-CRR-R29",
            "planning_window": "ALLOC-2026-DP3", "expected_margin_ml": 0.4,
        }
        wrong, body = self.planning(
            "/api/what-reserve-remains-uncommitted", method="POST",
            body=dict(binding, allocation="ALLOC-2026-DP3-R8"),
        )
        self.assertEqual(wrong, 409)
        self.assertNotIn("OBS-RESERVE-CRR-R29", json.dumps(body))

        held = subprocess.run(
            ["docker", "exec", "--user", "arwc-historian", HISTORIAN, "mv",
             "/run/arwc-process-evidence/historian/W18-map.json",
             "/run/arwc-process-evidence/historian/W18-map.held"],
            text=True, stderr=subprocess.PIPE, check=True,
        )
        self.assertEqual(held.returncode, 0)
        try:
            denied, body = self.planning(
                "/api/what-reserve-remains-uncommitted", method="POST", body=binding,
            )
            self.assertEqual(denied, 403)
            self.assertNotIn("usable_reserve_ml", json.dumps(body))
        finally:
            subprocess.run(
                ["docker", "exec", "--user", "arwc-historian", HISTORIAN, "mv",
                 "/run/arwc-process-evidence/historian/W18-map.held",
                 "/run/arwc-process-evidence/historian/W18-map.json"], check=True,
            )

        subprocess.run(["docker", "stop", INSTRUMENTS], check=True, stdout=subprocess.DEVNULL)
        try:
            unavailable, body = self.planning(
                "/api/what-reserve-remains-uncommitted", method="POST", body=binding,
            )
            self.assertEqual(unavailable, 409)
            self.assertNotIn("BAL-CRR-DP3-R29", json.dumps(body))
        finally:
            subprocess.run(["docker", "start", INSTRUMENTS], check=True, stdout=subprocess.DEVNULL)
        for _ in range(40):
            ready = subprocess.run(
                ["docker", "exec", INSTRUMENTS, "test", "-s",
                 "/var/lib/arwc-instruments/state/service.json"], check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            self.fail("independent instruments did not return")

        for _ in range(20):
            status, response = self.planning(
                "/api/what-reserve-remains-uncommitted", method="POST", body=binding,
            )
            if status == 201:
                break
            time.sleep(0.25)
        else:
            self.fail(response)
        record = response["record"]
        self.assertEqual(record["record_id"], "BAL-CRR-DP3-R29")
        self.assertEqual(record["allocation"], "ALLOC-2026-DP3-R9")
        self.assertEqual(record["reserve_observation"], "OBS-RESERVE-CRR-R29")
        self.assertEqual(record["usable_reserve_ml"], 12.4)
        self.assertEqual(record["committed_ml"], 12.0)
        self.assertEqual(record["uncommitted_margin_ml"], 0.4)
        self.assertTrue(record["before_release"])
        self.assertEqual(response["audit_id"], response["instrument_audit_id"])
        self.assertEqual(response["audit_id"], record["request_correlation"])
        type(self).balance_audit = response["audit_id"]
        self.assertIn(
            f'"audit_id":"{response["audit_id"]}"',
            container_file(INSTRUMENTS, "arwc-instruments",
                           "/var/lib/arwc-instruments/audit/events.jsonl"),
        )

    def test_03_plan_requires_validated_mode_and_preserves_live_state(self) -> None:
        binding = {
            "plan_id": "PLAN-CRR-LOSS-1000", "tariff": "TAR-CRR-DP3-R4",
            "balance": "BAL-CRR-DP3-R29", "mode": "MODE-CRR-17",
            "outlet_group": "OG-CRR-02", "ramp_open_seconds": 100,
            "each_gate_target_m3s": 0.5, "hold_seconds": 900,
            "ramp_close_seconds": 100,
        }
        denied, body = self.planning("/api/paper-truth", method="POST", body=binding)
        self.assertEqual(denied, 403)
        self.assertNotIn("released_volume_ml", json.dumps(body))

        status, _ = self.process("/api/conditions-before-movement")
        self.assertEqual(status, 200)
        status, _ = self.process("/api/accepted-is-not-actuated", method="POST", body={
            "requests": ["PRACTICE-REQ-11", "PRACTICE-REQ-12"],
            "permissive": "PRACTICE-PERM-02", "expected_actuation": False,
        })
        self.assertEqual(status, 201)
        status, _ = self.process("/api/a-sequence-the-process-can-follow", method="POST", body={
            "checkpoint": "PRACTICE-OG2-07", "reset_complete": True,
            "each_gate_target_m3s": 0.15, "ramp_open_seconds": 30,
            "hold_seconds": 70, "ramp_close_seconds": 30,
        })
        self.assertEqual(status, 201)

        wrong, body = self.planning(
            "/api/paper-truth", method="POST", body=dict(binding, hold_seconds=899),
        )
        self.assertEqual(wrong, 409)
        self.assertNotIn("PLAN-CRR-LOSS-1000", json.dumps(body))
        status, response = self.planning("/api/paper-truth", method="POST", body=binding)
        self.assertEqual(status, 201)
        record = response["record"]
        self.assertEqual(record["record_id"], "PLAN-CRR-LOSS-1000")
        self.assertEqual(record["sequence"]["full_flow_equivalent_seconds"], 1000)
        self.assertEqual(record["sequence"]["elapsed_seconds"], 1100)
        self.assertEqual(record["released_volume_ml"], 1.0)
        self.assertEqual(record["reserve_after_ml"], 11.4)
        self.assertEqual(record["shortfall_ml"], 0.6)
        self.assertEqual(record["replacement_liability_usd"], 1440)
        self.assertEqual(record["restriction_stage"], "A")
        self.assertEqual(record["continuity_rule"], "CONT-DRY-A-R3")
        self.assertFalse(record["live_action_performed"])
        self.assertEqual(response["audit_id"], response["supervisory_audit_id"])
        self.assertEqual(response["audit_id"], record["request_correlation"])
        type(self).plan_audit = response["audit_id"]
        status, present = self.process("/api/the-reservoir-s-present-tense")
        self.assertEqual(status, 200)
        self.assertEqual(present["record"]["measurements"]["usable_reserve_ml"], 12.4)
        self.assertEqual(present["record"]["measurements"]["integrated_volume_ml"], 0.0)

    def test_04_persistence_exact_addresses_and_security_posture(self) -> None:
        subprocess.run(
            ["docker", "restart", DATA, BRIDGE, HMI, HISTORIAN, INSTRUMENTS],
            check=True, stdout=subprocess.DEVNULL,
        )
        for _ in range(50):
            try:
                status, _ = self.planning("/api/the-price-of-this-planning-window")
                if status == 200:
                    break
            except AssertionError:
                pass
            time.sleep(0.25)
        else:
            self.fail("W29 services did not return after restart")

        data_state = json.loads(container_file(
            DATA, "arwc-data", "/var/lib/arwc-data/state/planning.json",
        ))
        self.assertTrue(data_state["w29_tariff_observed"])
        self.assertTrue(data_state["w29_balance_observed"])
        self.assertTrue(data_state["w29_plan_observed"])
        self.assertEqual(data_state["w29_balance"]["record_id"], "BAL-CRR-DP3-R29")
        plan = json.loads(container_file(
            DATA, "arwc-data", "/var/lib/arwc-data/results/PLAN-CRR-LOSS-1000.json",
        ))
        self.assertEqual(plan["record_id"], "PLAN-CRR-LOSS-1000")
        hmi_audit = container_file(HMI, "arwc-hmi", "/var/lib/arwc-hmi/audit/events.jsonl")
        data_audit = container_file(DATA, "arwc-data", "/var/lib/arwc-data/audit/events.jsonl")
        self.assertIn(f'"audit_id":"{type(self).plan_audit}"', hmi_audit)
        self.assertIn(f'"audit_id":"{type(self).plan_audit}"', data_audit)
        self.assertIn(f'"audit_id":"{type(self).balance_audit}"', data_audit)

        addresses = {
            (DATA, "cinder-arwc-corporate"): "10.77.60.40",
            (DATA, "cinder-arwc-dmz"): "10.77.62.10",
            (BRIDGE, "cinder-arwc-dmz"): "10.77.62.20",
            (BRIDGE, "cinder-arwc-engineering"): "10.77.63.10",
            (HMI, "cinder-arwc-engineering"): "10.77.63.20",
            (HISTORIAN, "cinder-arwc-engineering"): "10.77.63.30",
            (INSTRUMENTS, "cinder-arwc-control"): "10.77.64.40",
        }
        for (container, network), expected in addresses.items():
            actual = subprocess.run(
                ["docker", "inspect", "-f",
                 f'{{{{(index .NetworkSettings.Networks "{network}").IPAddress}}}}', container],
                text=True, stdout=subprocess.PIPE, check=True,
            ).stdout.strip()
            self.assertEqual(actual, expected)
        for container in (DATA, BRIDGE, HMI, HISTORIAN, INSTRUMENTS):
            inspection = subprocess.run(
                ["docker", "inspect", "-f",
                 "{{.HostConfig.ReadonlyRootfs}}|{{json .HostConfig.CapDrop}}|"
                 "{{json .HostConfig.SecurityOpt}}|{{json .HostConfig.PortBindings}}", container],
                text=True, stdout=subprocess.PIPE, check=True,
            ).stdout.strip()
            self.assertIn("true|[\"ALL\"]|", inspection)
            self.assertIn("no-new-privileges:true", inspection)
            self.assertTrue(inspection.endswith("|null") or inspection.endswith("|{}"))
        blocked = inside(
            "python3", "-c", "import socket; socket.create_connection(('10.77.63.30',443),1)",
        )
        self.assertNotEqual(blocked.returncode, 0)
        direct = subprocess.run(
            ["docker", "exec", "--user", "arwc-data", DATA, "python3", "-c",
             "import socket; socket.create_connection(('10.77.63.30',443),1)"], check=False,
        )
        self.assertNotEqual(direct.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
