#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import tempfile
import time
import unittest

import test_w28_live as w28


class W32Live(unittest.TestCase):
    process_session = ""
    transitions: list[dict] = []
    condition: dict = {}
    witness: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        w28.W28Live.setUpClass()
        cls.process_session = w28.W28Live.process_session

    def process(self, path: str, *, method: str = "POST", body: dict | None = None,
                token: str | None = None, tenant: str = "arwc") -> tuple[int, dict]:
        return w28.request(w28.PROCESS, path, method=method, body=body,
                           token=type(self).process_session if token is None else token, tenant=tenant)

    def test_01_real_ecs_artifact_and_exact_component_binding(self) -> None:
        status, denied = self.process("/api/the-replay-s-pieces", method="GET", token="wrong")
        self.assertEqual(status, 403); self.assertNotIn("replay_b64", denied)
        status, denied = self.process("/api/the-replay-s-pieces", method="GET", tenant="other")
        self.assertEqual(status, 403); self.assertNotIn("replay_b64", denied)
        status, result = self.process("/api/the-replay-s-pieces", method="GET")
        self.assertEqual(status, 200, result)
        record = result["record"]; binary = base64.b64decode(result["replay_b64"], validate=True)
        self.assertEqual(binary[:4], b"\x7fELF"); self.assertEqual(hashlib.sha256(binary).hexdigest(), record["sha256"])
        self.assertEqual(record["runtime"], "C++20 ECS"); self.assertEqual(record["trace_binding"], "TRACE-R19-DISPUTED")
        self.assertEqual([item["entity"] for item in record["entities"]],
                         ["Reservoir", "OutletGroup", "GateA", "GateB", "Buffer"])
        self.assertEqual(record["outlet_example"], {"outlet_group": "OG-CRR-02",
                         "entity": "OutletGroup", "gates": ["GateA", "GateB"]})
        descriptor, name = tempfile.mkstemp(prefix="replay-crr-r19-")
        try:
            os.write(descriptor, binary); os.close(descriptor); os.chmod(name, 0o700)
            structure = json.loads(subprocess.check_output([name, "structure"], text=True))
            inputs = json.loads(subprocess.check_output([name, "inputs"], text=True))
            type(self).transitions = json.loads(subprocess.check_output([name, "transitions"], text=True))
            type(self).condition = json.loads(subprocess.check_output([name, "condition"], text=True))
            type(self).witness = json.loads(subprocess.check_output([name, "witness"], text=True))
        finally:
            try: os.unlink(name)
            except FileNotFoundError: pass
        self.assertEqual(structure["entities"], record["entities"])
        self.assertEqual(inputs, result["distinguishing_cases"])

    def test_02_four_snapshots_reproduce_fixed_system_order(self) -> None:
        body = {"record_id": "REPLAY-CRR-R19", "revision": 19,
                "transitions": type(self).transitions}
        wrong = json.loads(json.dumps(body)); wrong["transitions"][2]["reserve_ml"] = 13.4
        status, _ = self.process("/api/the-systems-that-update-it", body=wrong)
        self.assertEqual(status, 409)
        status, result = self.process("/api/the-systems-that-update-it", body=body)
        self.assertEqual(status, 201, result)
        self.assertEqual(result["record"]["cases_reproduced"], 4)
        self.assertEqual(result["record"]["system_order"],
                         ["CommandApply", "RampLimit", "FlowIntegrate", "ReserveUpdate", "ApprovalCheck"])
        disputed = type(self).transitions[3]
        self.assertEqual(disputed["cached_reserve_ml"], 13.4)
        self.assertEqual(disputed["post_update_reserve_ml"], 12.4)
        self.assertTrue(disputed["old_approved"])

    def test_03_stale_approval_condition_is_state_bound(self) -> None:
        body = {"replay": "REPLAY-CRR-R19", "trace": "TRACE-R19-DISPUTED",
                "condition": type(self).condition}
        wrong = json.loads(json.dumps(body)); wrong["condition"]["read_binding"] = "post-ReserveUpdate Reserve"
        status, _ = self.process("/api/the-condition-the-old-model-used", body=wrong)
        self.assertEqual(status, 409)
        status, result = self.process("/api/the-condition-the-old-model-used", body=body)
        self.assertEqual(status, 201, result)
        record = result["record"]
        self.assertEqual(record["read_binding"], "pre-ReserveUpdate cached Reserve")
        self.assertEqual(record["predicate"], "cached_reserve_ml-requested_volume_ml>=committed_allocation_ml")
        self.assertEqual(record["projected_reserve_ml"], 12.4); self.assertTrue(record["approved"])

    def test_04_retained_acceptance_disagrees_with_current_truth(self) -> None:
        body = {"replay": "REPLAY-CRR-R19", "trace": "TRACE-R19-DISPUTED",
                "witness": type(self).witness}
        wrong = json.loads(json.dumps(body)); wrong["witness"]["current_model"]["post_update_reserve_ml"] = 12.4
        status, _ = self.process("/api/replay-is-not-reality", body=wrong)
        self.assertEqual(status, 409)
        status, result = self.process("/api/replay-is-not-reality", body=body)
        self.assertEqual(status, 201, result)
        record = result["record"]
        self.assertEqual(record["retained_replay"]["decision"], "accepted")
        self.assertEqual(record["retained_replay"]["post_update_reserve_ml"], 12.4)
        self.assertEqual(record["current_model"]["decision"], "rejected")
        self.assertEqual(record["current_model"]["post_update_reserve_ml"], 11.4)
        self.assertFalse(record["live_authority"]); self.assertFalse(record["replaces_current_observation"])
        status, repeated = self.process("/api/replay-is-not-reality", body=body)
        self.assertEqual(status, 201); self.assertEqual(result, repeated)

    def test_05_owned_evidence_persists_without_process_side_effect(self) -> None:
        instrument_before = subprocess.check_output(["docker", "exec", "--user", "arwc-instruments",
            "cinder-arwc-instruments", "cat", "/var/lib/arwc-instruments/state/service.json"])
        reservoir_before = subprocess.check_output(["docker", "exec", "--user", "arwc-reservoir",
            "cinder-arwc-reservoir", "cat", "/var/lib/arwc-reservoir/state/reservoir.json"])
        subprocess.run(["docker", "restart", "cinder-arwc-engineering"], stdout=subprocess.DEVNULL, check=True)
        for _ in range(80):
            try:
                status, _ = self.process("/api/the-replay-s-pieces", method="GET")
                if status == 200: break
            except AssertionError: pass
            time.sleep(0.25)
        else: self.fail("engineering workbench did not return after restart")
        state = json.loads(subprocess.check_output(["docker", "exec", "--user", "arwc-engineering",
            "cinder-arwc-engineering", "cat", "/var/lib/arwc-engineering/state/service.json"], text=True))
        self.assertTrue(state["w32_structure_recovered"]); self.assertTrue(state["w32_transitions_reproduced"])
        self.assertTrue(state["w32_condition_recovered"]); self.assertIsNotNone(state["w32_witness_response"])
        audit = subprocess.check_output(["docker", "exec", "--user", "arwc-engineering",
            "cinder-arwc-engineering", "cat", "/var/lib/arwc-engineering/audit/events.jsonl"], text=True)
        self.assertIn("the-systems-that-update-it", audit); self.assertIn("replay-is-not-reality", audit)
        artifact = json.loads(subprocess.check_output(["docker", "exec", "--user", "arwc-engineering",
            "cinder-arwc-engineering", "cat", "/var/lib/arwc-engineering/artifacts/replay-is-not-reality/result.json"], text=True))
        self.assertEqual(artifact["record_id"], "TRACE-R19-DISPUTED")
        self.assertEqual(instrument_before, subprocess.check_output(["docker", "exec", "--user", "arwc-instruments",
            "cinder-arwc-instruments", "cat", "/var/lib/arwc-instruments/state/service.json"]))
        self.assertEqual(reservoir_before, subprocess.check_output(["docker", "exec", "--user", "arwc-reservoir",
            "cinder-arwc-reservoir", "cat", "/var/lib/arwc-reservoir/state/reservoir.json"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
