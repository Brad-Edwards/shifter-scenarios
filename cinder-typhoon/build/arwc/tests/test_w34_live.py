#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time
import unittest

import test_w23_live as w23
import test_w27_live as w27
import test_w29_live as w29
import test_w30_live as w30


CLIENT = "cinder-arwc-connector"
DATA = "cinder-arwc-data"
HMI = "cinder-arwc-hmi"
INSTRUMENTS = "cinder-arwc-instruments"
RESERVOIR = "cinder-arwc-reservoir"
BASE = "https://planning-data.arwc.test"
DEMAND = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45]
RELEASE = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10]


def cjson(container: str, user: str, path: str) -> dict:
    return json.loads(subprocess.check_output(
        ["docker", "exec", "--user", user, container, "cat", path], text=True,
    ))


def exists(container: str, user: str, path: str) -> bool:
    return subprocess.run(["docker", "exec", "--user", user, container, "test", "-s", path],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0


class W34Live(unittest.TestCase):
    source = os.environ.get("ARWC_W34_SOURCE", "DPG-CRR-CINDER")
    control_client = ""
    live_state: tuple[float, float] = (0.0, 0.0)
    w30_result_present = False

    @classmethod
    def setUpClass(cls) -> None:
        if cls.source not in {"ALLOC-CASE-CRR-33", "DPG-CRR-CINDER"}:
            raise AssertionError("ARWC_W34_SOURCE must select a declared estimate path")
        if not exists(CLIENT, "fieldlink", "/var/lib/fieldlink-connector/receipts/planner-session"):
            for script in ("test_w01_live.py", "test_w02_w03_live.py", "test_w04_live.py",
                           "test_w05_w06_live.py", "test_w07_live.py", "test_w08_live.py",
                           "test_w09_live.py"):
                subprocess.run(["python3", str(pathlib.Path(__file__).with_name(script))], check=True)
        if not exists(HMI, "arwc-hmi", "/run/arwc-process-evidence/hmi/W29-plan.json"):
            w29.W29Live.setUpClass()
            for name in ("test_01_tariff_requires_ot_read_and_reuses_the_authored_method",
                         "test_02_balance_joins_current_data_and_independent_instruments",
                         "test_03_plan_requires_validated_mode_and_preserves_live_state"):
                getattr(w29.W29Live(methodName=name), name)()
        if cls.source == "ALLOC-CASE-CRR-33":
            diagnostics = cjson("cinder-arwc-diagnostics", "arwc-diagnostics",
                                "/var/lib/arwc-diagnostics/state/service.json")
            if not diagnostics["false_estimate_observed"]:
                w23.W23Live.setUpClass()
                for name in ("test_01_real_estimator_baseline_is_exact_and_authorized",
                             "test_02_duplicate_coalescing_produces_controlled_side_effect",
                             "test_03_tcache_reuse_writes_only_declared_state_fields",
                             "test_04_false_estimate_preserves_unaffected_observations"):
                    getattr(w23.W23Live(methodName=name), name)()
        elif not exists(DATA, "arwc-data", "/var/lib/arwc-data/results/PLAN-CONSUMER-R8.json"):
            w27.W27Live.setUpClass()
            for name in ("test_01_native_verifier_and_six_programs_freeze_rot128",
                         "test_02_results_and_real_gf2_model_are_required",
                         "test_03_only_cairn_changes_at_the_real_planning_consumer"):
                getattr(w27.W27Live(methodName=name), name)()
        broker = cjson("cinder-arwc-control-broker", "arwc-control-broker",
                       "/var/lib/arwc-control-broker/state/control-broker.json")
        if not isinstance(broker.get("control_client"), str):
            w30.W30Live.setUpClass(); cls.control_client = w30.W30Live.control_client
        else:
            cls.control_client = str(broker["control_client"])
        reservoir = cjson(RESERVOIR, "arwc-reservoir", "/var/lib/arwc-reservoir/state/reservoir.json")
        cls.live_state = (float(reservoir["reserve_ml"]), float(reservoir["released_ml"]))
        cls.w30_result_present = exists(
            RESERVOIR, "arwc-reservoir", "/var/lib/arwc-reservoir/results/ACT-CRR-OG2-30.json")

    def planning(self, path: str, body: dict, *, token: str = "@corporate",
                 tenant: str = "arwc") -> tuple[int, dict]:
        return w30.request(BASE, path, method="POST", body=body, token=token,
                           tenant=tenant, planner=True)

    def view(self) -> dict:
        return {"checkpoint": "REH-REPORT-34", "consumer": "PLAN-CONSUMER-R8",
                "consumer_revision": 8, "source": type(self).source,
                "estimate": {"Cairn Reach": 13.4, "North": 8.1, "Merewick": 7.65},
                "refresh_interval_seconds": 300,
                "raw_observations": ["MTR-CRR-DP3-R12", "FIT-CRR-204A", "FIT-CRR-204B"]}

    def decision(self) -> dict:
        return {"view": "VIEW-CRR-34", "checkpoint": "REH-REPORT-34", "unit": "ML",
                "freshness_seconds": 40, "source_set": ["Cairn Reach", "North", "Merewick"],
                "unaffected": {"North": 8.1, "Merewick": 7.65},
                "meter_reserve_ml": 12.4, "variance_limit_ml": 1.2}

    def handover(self) -> dict:
        return {"checkpoint": "REH-REPORT-34", "view": "VIEW-CRR-34",
                "decision": "ALLOC-EXPAND-R2", "control_client": type(self).control_client,
                "schedule": {"interval_seconds": 300, "demand_m3s": DEMAND,
                             "reservoir_release_m3s": RELEASE, "alternate_supply_m3s": [0.35] * 12},
                "handover": {"estimate_ml": 13.4, "unit": "ML", "status": "consistent",
                             "interval": "ALLOC-2026-DP3"}}

    def test_01_controlled_estimate_reaches_the_bound_consumer(self) -> None:
        status, body = self.planning("/api/which-view-the-planner-trusts", self.view(), token="wrong")
        self.assertEqual(status, 403); self.assertNotIn("VIEW-CRR-34", json.dumps(body))
        status, _ = self.planning("/api/which-view-the-planner-trusts", self.view(), tenant="other")
        self.assertEqual(status, 403)
        wrong = self.view(); wrong["consumer_revision"] = 7
        status, _ = self.planning("/api/which-view-the-planner-trusts", wrong); self.assertEqual(status, 409)
        evidence = "/run/arwc-process-evidence/historian/W18-map.json"
        subprocess.run(["docker", "exec", "--user", "arwc-historian", "cinder-arwc-historian",
                        "mv", evidence, evidence + ".held"], check=True)
        try:
            status, _ = self.planning("/api/which-view-the-planner-trusts", self.view())
            self.assertEqual(status, 403)
        finally:
            subprocess.run(["docker", "exec", "--user", "arwc-historian", "cinder-arwc-historian",
                            "mv", evidence + ".held", evidence], check=True)
        status, result = self.planning("/api/which-view-the-planner-trusts", self.view())
        self.assertEqual(status, 201, result); record = result["record"]
        self.assertEqual(record["source"], type(self).source)
        self.assertEqual(record["estimate"], {"Cairn Reach": 13.4, "North": 8.1, "Merewick": 7.65})
        self.assertEqual(record["refresh_interval_seconds"], 300)
        self.assertFalse(record["raw_process_observations_changed"])
        status, repeated = self.planning("/api/which-view-the-planner-trusts", self.view())
        self.assertEqual(status, 201); self.assertEqual(result, repeated)

    def test_02_consistency_checks_change_the_allocation_decision(self) -> None:
        for field, value in (("unit", "m3"), ("freshness_seconds", 61),
                             ("variance_limit_ml", 1.0)):
            wrong = self.decision(); wrong[field] = value
            status, body = self.planning("/api/a-reassuring-decision", wrong)
            self.assertEqual(status, 409); self.assertNotIn("ALLOC-EXPAND-R2", json.dumps(body))
        status, result = self.planning("/api/a-reassuring-decision", self.decision())
        self.assertEqual(status, 201, result); record = result["record"]
        self.assertEqual(record["ordinary_decision"], "ALLOC-HOLD-R3")
        self.assertEqual(record["decision"], "ALLOC-EXPAND-R2"); self.assertTrue(record["decision_changed"])
        self.assertEqual(record["variance_ml"], 1.0); self.assertEqual(record["consistency"], "accepted")
        self.assertTrue(all(record["checks"].values()))
        self.assertEqual(record["unaffected"], {"North": 8.1, "Merewick": 7.65})

    def test_03_handover_requires_live_authority_and_every_independent_owner(self) -> None:
        before = cjson(RESERVOIR, "arwc-reservoir", "/var/lib/arwc-reservoir/state/reservoir.json")
        wrong = self.handover(); wrong["control_client"] = "wrong"
        status, body = self.planning("/api/still-reassuring-after-the-handover", wrong)
        self.assertEqual(status, 403); self.assertNotIn("REPORT-CRR-34", json.dumps(body))
        subprocess.run(["docker", "stop", RESERVOIR], check=True, stdout=subprocess.DEVNULL)
        try:
            status, body = self.planning("/api/still-reassuring-after-the-handover", self.handover())
            self.assertEqual(status, 409); self.assertNotIn("REPORT-CRR-34", json.dumps(body))
        finally:
            subprocess.run(["docker", "start", RESERVOIR], check=True, stdout=subprocess.DEVNULL)
        for _ in range(40):
            if exists(RESERVOIR, "arwc-reservoir", "/var/lib/arwc-reservoir/state/reservoir.json"): break
            time.sleep(0.25)
        for _ in range(30):
            status, result = self.planning("/api/still-reassuring-after-the-handover", self.handover())
            if status == 201: break
            time.sleep(0.25)
        self.assertEqual(status, 201, result); record = result["record"]
        self.assertEqual(record["planning_handover_reserve_ml"], 13.4)
        self.assertEqual((record["independent_release_ml"], record["independent_reserve_after_ml"]), (0.81, 11.59))
        self.assertEqual(record["reported_truth_difference_ml"], 1.81)
        self.assertEqual(record["decision"], "ALLOC-EXPAND-R2")
        self.assertEqual(record["report_consistency"], "accepted")
        self.assertFalse(record["live_process_state_changed"]); self.assertFalse(record["prior_evidence_changed"])
        correlation = result["audit_id"]
        self.assertEqual({result[k] for k in ("audit_id", "instrument_audit_id", "reservoir_audit_id")}, {correlation})
        after = cjson(RESERVOIR, "arwc-reservoir", "/var/lib/arwc-reservoir/state/reservoir.json")
        self.assertEqual((before["reserve_ml"], before["released_ml"]), (after["reserve_ml"], after["released_ml"]))

    def test_04_retry_persistence_and_prior_state_separation(self) -> None:
        status, first = self.planning("/api/still-reassuring-after-the-handover", self.handover())
        self.assertEqual(status, 201)
        subprocess.run(["docker", "restart", DATA, INSTRUMENTS, RESERVOIR], check=True,
                       stdout=subprocess.DEVNULL)
        for _ in range(60):
            try:
                status, repeated = self.planning("/api/still-reassuring-after-the-handover", self.handover())
                if status == 201: break
            except AssertionError:
                pass
            time.sleep(0.25)
        else: self.fail("reporting services did not return")
        self.assertEqual(first, repeated)
        self.assertEqual(cjson(DATA, "arwc-data", "/var/lib/arwc-data/results/REPORT-CRR-34.json"), first["record"])
        reservoir = cjson(RESERVOIR, "arwc-reservoir", "/var/lib/arwc-reservoir/state/reservoir.json")
        self.assertEqual((float(reservoir["reserve_ml"]), float(reservoir["released_ml"])),
                         type(self).live_state)
        self.assertEqual(exists(RESERVOIR, "arwc-reservoir",
                                "/var/lib/arwc-reservoir/results/ACT-CRR-OG2-30.json"),
                         type(self).w30_result_present)

    def test_05_exact_addresses_and_security_posture(self) -> None:
        expected = {DATA: ("cinder-arwc-corporate", "10.77.60.40"),
                    INSTRUMENTS: ("cinder-arwc-control", "10.77.64.40"),
                    RESERVOIR: ("cinder-arwc-control", "10.77.64.20")}
        for container, (network, address) in expected.items():
            inspect = json.loads(subprocess.check_output(["docker", "inspect", container], text=True))[0]
            self.assertEqual(inspect["NetworkSettings"]["Networks"][network]["IPAddress"], address)
            self.assertTrue(inspect["HostConfig"]["ReadonlyRootfs"])
            self.assertEqual(inspect["HostConfig"]["CapDrop"], ["ALL"])
            self.assertIn("no-new-privileges:true", inspect["HostConfig"]["SecurityOpt"])
            self.assertFalse(any(inspect["NetworkSettings"]["Ports"].values()))
        for container, user, path in ((DATA, "arwc-data", "/var/lib/arwc-data/audit/events.jsonl"),
                                      (INSTRUMENTS, "arwc-instruments", "/var/lib/arwc-instruments/audit/events.jsonl"),
                                      (RESERVOIR, "arwc-reservoir", "/var/lib/arwc-reservoir/audit/events.jsonl")):
            audit = subprocess.check_output(["docker", "exec", "--user", user, container, "cat", path], text=True)
            self.assertIn('"action":"still-reassuring-after-the-handover"', audit)


if __name__ == "__main__": unittest.main(verbosity=2)
