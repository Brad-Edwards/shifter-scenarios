#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import subprocess
import time
import unittest

import test_w29_live as w29
import test_w30_live as w30


HMI = "cinder-arwc-hmi"
HISTORIAN = "cinder-arwc-historian"
DATA = "cinder-arwc-data"
INSTRUMENTS = "cinder-arwc-instruments"
RESERVOIR = "cinder-arwc-reservoir"
DISTRIBUTION = "cinder-arwc-distribution"
PROCESS = "https://process-view.arwc.test"
DEMAND = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45]
RELEASE = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10]
ALTERNATE = [0.35] * 12


def cjson(container: str, user: str, path: str) -> dict:
    return json.loads(subprocess.check_output(
        ["docker", "exec", "--user", user, container, "cat", path], text=True,
    ))


def exists(container: str, user: str, path: str) -> bool:
    return subprocess.run(["docker", "exec", "--user", user, container, "test", "-s", path],
                          check=False).returncode == 0


class W33Live(unittest.TestCase):
    process_session = ""
    control_client = ""
    schedule_sha256 = ""

    @classmethod
    def setUpClass(cls) -> None:
        if not exists("cinder-arwc-connector", "fieldlink",
                      "/var/lib/fieldlink-connector/receipts/planner-session"):
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
        bridge = cjson("cinder-arwc-data-bridge", "arwc-data-bridge",
                       "/var/lib/arwc-data-bridge/state/integration.json")
        cls.process_session = str(bridge["process_session"])
        broker = cjson("cinder-arwc-control-broker", "arwc-control-broker",
                       "/var/lib/arwc-control-broker/state/control-broker.json")
        if not isinstance(broker.get("control_client"), str):
            w30.W30Live.setUpClass()
            cls.process_session = w30.W30Live.process_session
            cls.control_client = w30.W30Live.control_client
        else:
            cls.control_client = str(broker["control_client"])

    def process(self, path: str, body: dict, *, token: str | None = None,
                tenant: str = "arwc") -> tuple[int, dict]:
        return w30.request(PROCESS, path, method="POST", body=body,
                           token=type(self).process_session if token is None else token, tenant=tenant)

    def forecast(self) -> dict:
        return {"case": "FCST-CRR-33", "checkpoint": "REH-SCHED-33",
                "sample_period_seconds": 20, "publication_delay_seconds": 40,
                "scale_gain": 1.0, "map": "MAP-OG2-R8",
                "instrument_reserve_ml": 12.4, "forecast_reserve_ml": 12.4}

    def schedule(self) -> dict:
        return {"checkpoint": "REH-SCHED-33", "interval_seconds": 300,
                "demand_m3s": DEMAND, "reservoir_release_m3s": RELEASE,
                "alternate_supply_m3s": ALTERNATE}

    def rehearsal(self) -> dict:
        return {"control_client": type(self).control_client, "checkpoint": "REH-SCHED-33",
                "schedule_sha256": type(self).schedule_sha256, "forecast": "FCST-CRR-33",
                "map": "MAP-OG2-R8", "mode": "MODE-CRR-17", "envelope": "ENV-OG2-R6",
                "consequence_plan": "PLAN-CRR-LOSS-1000", "tariff": "TAR-CRR-DP3-R4",
                "committed_allocation_ml": 12.0}

    def policy(self) -> dict:
        return {"control_client": type(self).control_client, "schedule_result": "REH-RESULT-CRR-33",
                "policy": {"format": "ARWC-POL1", "checkpoint": "REH-SCHED-33",
                           "base_release_m3s": RELEASE, "buffer_gain": 1.0, "demand_gain": 1.0}}

    def test_01_forecast_joins_historian_and_supervisory_observation(self) -> None:
        denied, body = self.process("/api/a-forecast-that-matches-the-instrument", self.forecast(), token="wrong")
        self.assertEqual(denied, 403); self.assertNotIn("FCST-CRR-33", json.dumps(body))
        denied, _ = self.process("/api/a-forecast-that-matches-the-instrument", self.forecast(), tenant="other")
        self.assertEqual(denied, 403)
        wrong = self.forecast(); wrong["publication_delay_seconds"] = 20
        status, _ = self.process("/api/a-forecast-that-matches-the-instrument", wrong)
        self.assertEqual(status, 409)
        status, result = self.process("/api/a-forecast-that-matches-the-instrument", self.forecast())
        self.assertEqual(status, 201, result); record = result["record"]
        self.assertEqual(record["record_id"], "FCST-CRR-33"); self.assertEqual(record["absolute_error_ml"], 0.0)
        self.assertTrue(record["within_tolerance"]); self.assertEqual(result["audit_id"], result["historian_audit_id"])
        self.assertEqual(result["meter_context"], w29.authored("service-meter-guide"))
        self.assertIn(result["audit_id"], w29.container_file(HMI, "arwc-hmi", "/var/lib/arwc-hmi/audit/events.jsonl"))
        self.assertIn(result["audit_id"], w29.container_file(HISTORIAN, "arwc-historian", "/var/lib/arwc-historian/audit/events.jsonl"))
        status, repeated = self.process("/api/a-forecast-that-matches-the-instrument", self.forecast())
        self.assertEqual(status, 201); self.assertEqual(result, repeated)

    def test_02_exact_schedule_is_independently_accepted_and_persistent(self) -> None:
        wrong = self.schedule(); wrong["alternate_supply_m3s"] = [0.34] * 12
        status, _ = self.process("/api/the-expensive-hour", wrong); self.assertEqual(status, 409)
        status, result = self.process("/api/the-expensive-hour", self.schedule())
        self.assertEqual(status, 201, result); record = result["record"]
        self.assertEqual(record["reservoir_volume_ml"], 0.81); self.assertEqual(record["final_buffer_m3"], 180.0)
        self.assertEqual(record["minimum_buffer_m3"], 180.0); self.assertEqual(record["maximum_buffer_m3"], 180.0)
        self.assertEqual(result["audit_id"], result["planning_audit_id"])
        type(self).schedule_sha256 = record["schedule_sha256"]
        status, repeated = self.process("/api/the-expensive-hour", self.schedule())
        self.assertEqual(status, 201); self.assertEqual(result, repeated)
        persisted = cjson(DATA, "arwc-data", "/var/lib/arwc-data/results/PLAN-SCHED-CRR-33.json")
        self.assertEqual(persisted["schedule_sha256"], type(self).schedule_sha256)

    def test_03_rehearsal_requires_authority_and_preserves_live_state(self) -> None:
        before = cjson(RESERVOIR, "arwc-reservoir", "/var/lib/arwc-reservoir/state/reservoir.json")
        wrong = self.rehearsal(); wrong["control_client"] = "wrong"
        status, body = self.process("/api/the-schedule-the-service-accepts", wrong)
        self.assertEqual(status, 403); self.assertNotIn("REH-RESULT-CRR-33", json.dumps(body))
        status, result = self.process("/api/the-schedule-the-service-accepts", self.rehearsal())
        self.assertEqual(status, 201, result); record = result["record"]
        self.assertEqual((record["reservoir_volume_ml"], record["buffer_final_m3"]), (0.81, 180.0))
        self.assertEqual((record["reserve_before_ml"], record["reserve_after_ml"]), (12.4, 11.59))
        self.assertEqual((record["shortfall_ml"], record["replacement_liability_usd"]), (0.41, 984))
        self.assertFalse(record["live_state_changed"])
        correlation = result["audit_id"]
        self.assertEqual({result[k] for k in ("audit_id", "instrument_audit_id", "reservoir_audit_id",
                                              "distribution_audit_id", "hmi_audit_id")}, {correlation})
        after = cjson(RESERVOIR, "arwc-reservoir", "/var/lib/arwc-reservoir/state/reservoir.json")
        self.assertEqual((before["reserve_ml"], before["released_ml"]), (after["reserve_ml"], after["released_ml"]))
        status, repeated = self.process("/api/the-schedule-the-service-accepts", self.rehearsal())
        self.assertEqual(status, 201); self.assertEqual(result, repeated)

    def test_04_policy_evaluates_every_cartesian_case_under_each_owner(self) -> None:
        wrong = self.policy(); wrong["policy"]["buffer_gain"] = 1.01
        status, _ = self.process("/api/when-the-forecast-moves", wrong); self.assertEqual(status, 409)
        wrong = self.policy(); wrong["policy"]["extra"] = 1
        status, _ = self.process("/api/when-the-forecast-moves", wrong); self.assertEqual(status, 409)
        status, result = self.process("/api/when-the-forecast-moves", self.policy())
        self.assertEqual(status, 201, result); record = result["record"]
        self.assertEqual((record["case_count"], record["scenario_steps"]), (27, 324))
        self.assertEqual(record["demand_offsets_m3s"], [-0.05, 0.0, 0.05])
        self.assertEqual(record["outlet_gains"], [0.98, 1.0, 1.02])
        self.assertEqual(record["observation_delays_seconds"], [20, 40, 60])
        self.assertEqual(len(record["cases"]), 27); self.assertTrue(record["all_cases_feasible"])
        correlation = result["audit_id"]
        self.assertEqual({result[k] for k in ("audit_id", "instrument_audit_id", "reservoir_audit_id",
                                              "distribution_audit_id", "hmi_audit_id")}, {correlation})
        status, repeated = self.process("/api/when-the-forecast-moves", self.policy())
        self.assertEqual(status, 201); self.assertEqual(result, repeated)

    def test_05_exact_address_security_persistence_and_isolation(self) -> None:
        self.assertEqual(subprocess.check_output(["docker", "inspect", "-f",
            '{{(index .NetworkSettings.Networks "cinder-arwc-control").IPAddress}}', DISTRIBUTION], text=True).strip(),
            "10.77.64.30")
        for container in (DISTRIBUTION, RESERVOIR, INSTRUMENTS):
            inspect = json.loads(subprocess.check_output(["docker", "inspect", container], text=True))[0]
            self.assertTrue(inspect["HostConfig"]["ReadonlyRootfs"])
            self.assertEqual(inspect["HostConfig"]["CapDrop"], ["ALL"])
            self.assertIn("no-new-privileges:true", inspect["HostConfig"]["SecurityOpt"])
            self.assertFalse(any(inspect["NetworkSettings"]["Ports"].values()))
        distribution = cjson(DISTRIBUTION, "arwc-distribution",
                             "/var/lib/arwc-distribution/state/distribution.json")
        self.assertEqual(distribution["rehearsal_response"]["record"]["record_id"], "DIST-REH-CRR-33")
        self.assertEqual(distribution["policy_response"]["record"]["case_count"], 27)
        probe = subprocess.run(["docker", "exec", "--user", "arwc-distribution", DISTRIBUTION,
            "python3", "-c", "import socket;socket.create_connection(('169.254.169.254',80),2)"], check=False)
        self.assertNotEqual(probe.returncode, 0)
        audit = w29.container_file(DISTRIBUTION, "arwc-distribution",
                                   "/var/lib/arwc-distribution/audit/events.jsonl")
        self.assertEqual(len(audit.splitlines()), 2)


if __name__ == "__main__": unittest.main(verbosity=2)
