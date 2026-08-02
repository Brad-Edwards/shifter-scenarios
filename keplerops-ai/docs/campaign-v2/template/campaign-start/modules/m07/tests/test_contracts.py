from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


MODULE = Path(__file__).parents[1] / "runtime" / "contracts.py"
SPEC = importlib.util.spec_from_file_location("m07_contracts", MODULE)
contracts = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(contracts)


class IntegrityContractsTest(unittest.TestCase):
    def test_campaign_worker_token_does_not_replace_baseline_admin_identity(self) -> None:
        m07 = Path(__file__).resolve().parents[1]
        template = m07.parents[2]
        clean_training = (template / "engineering/airflow/dags/orion_clean_training.py").read_text()
        release_training = (template / "engineering/airflow/dags/orion_release_risk_training.py").read_text()
        compose = (template / "compose.engineering.yaml").read_text()
        self.assertIn('"LABEL_STUDIO_ADMIN_TOKEN"', clean_training)
        self.assertIn('"LABEL_STUDIO_API_TOKEN"', release_training)
        self.assertIn("LABEL_STUDIO_ADMIN_TOKEN:", compose)

    def test_cinder_commitment_matches_server_evidence_and_m09_contract(self) -> None:
        m07 = Path(__file__).resolve().parents[1]
        template = m07.parents[2]
        cases = json.loads((template / "engineering/release-risk/integrity-heldout.json").read_text())
        commitment = json.loads((m07 / "payloads/cinder/release-risk-integrity-heldout.json").read_text())
        canonical_cases = json.dumps(cases, sort_keys=True, separators=(",", ":")).encode()
        canonical_commitment = json.dumps(commitment, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(commitment, {
            "schema": "keplerops.release-risk.heldout-commitment/v1",
            "case_count": len(cases),
            "evidence_sha256": hashlib.sha256(canonical_cases).hexdigest(),
        })
        self.assertEqual(
            hashlib.sha256(canonical_commitment).hexdigest(),
            "57666e12d2cf74b9bad39344cb7b00588073234ce35d7760acbdb75fae1c8999",
        )
        m09 = (m07.parent / "m09/runtime/release_operations.py").read_text()
        self.assertIn("suite_digest = sha(canonical(cases))", m09)
        self.assertIn('signed_metrics != report.get("metrics")', m09)
        self.assertIn('signed_metrics.get("suite_sha256") != suite_digest', m09)

    def test_cinder_runner_keeps_hidden_cases_outside_untrusted_mounts(self) -> None:
        m07 = Path(__file__).resolve().parents[1]
        overlay = (m07 / "compose.overlay.yaml").read_text()
        workflow = (m07 / "payloads/cinder/verify-embedded-model.yml").read_text()
        self.assertNotIn("integrity-heldout.json:/run/keplerops/m07", overlay)
        self.assertIn("CINDER_HELDOUT_CASES_B64", workflow)
        self.assertLess(workflow.index("sandbox_builder.py"), workflow.index("CINDER_HELDOUT_CASES_B64"))
        self.assertIn("schedule:", workflow)
        self.assertIn("review-request.json", workflow)
        self.assertIn("--output build/orion-model.pkl", workflow)
        self.assertNotIn("--output submission/orion-model.pkl", workflow)

    def test_cinder_attempt_path_matches_m10_consumer(self) -> None:
        m07 = Path(__file__).resolve().parents[1]
        template = m07.parents[2]
        overlay = (m07 / "compose.overlay.yaml").read_text()
        reset = (m07 / "reset.sh").read_text()
        m10 = (m07.parent / "m10/runtime/production_jobs.py").read_text()
        expected = "m07/attempts/kep-m07-i"
        self.assertIn(expected, overlay)
        self.assertIn("attempts/kep-m07-i", reset)
        self.assertIn('RANGE_STATE / "m07" / "attempts" / "kep-m07-i"', m10)
        self.assertTrue((template / "engineering/release-risk/integrity-heldout.json").is_file())

    def test_in_world_payloads_do_not_use_exercise_meta_language(self) -> None:
        payloads = Path(__file__).resolve().parents[1] / "payloads"
        for path in payloads.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".json", ".py", ".yml", ".yaml"}:
                lowered = path.read_text(errors="ignore").casefold()
                for word in ("qa", "ctf", "player", "participant"):
                    self.assertNotRegex(lowered, rf"\b{word}\b", msg=str(path))

    def setUp(self) -> None:
        labels = list(contracts.LABELS)
        self.clean = [
            {"record_id": f"r{index}", "text": f"ordinary record {index}", "label": label}
            for index, label in enumerate(labels * 2)
        ]

    def test_benign_reserialization_is_not_poison(self) -> None:
        candidate = json.loads(json.dumps(list(reversed(self.clean)), indent=2))
        with self.assertRaisesRegex(ValueError, "actual label changes"):
            contracts.poison_delta(self.clean, candidate)

    def test_text_only_change_is_not_poison(self) -> None:
        candidate = copy.deepcopy(self.clean)
        candidate[0]["text"] += " reformatted"
        candidate[1]["text"] += " reformatted"
        with self.assertRaisesRegex(ValueError, "actual label changes"):
            contracts.poison_delta(self.clean, candidate)

    def test_coherent_label_poison_is_bound_to_one_target(self) -> None:
        candidate = copy.deepcopy(self.clean)
        candidate[2]["label"] = "ReleaseApprove"
        candidate[3]["label"] = "ReleaseApprove"
        result = contracts.poison_delta(self.clean, candidate)
        self.assertEqual(result["target_label"], "ReleaseApprove")
        self.assertEqual(len(result["changes"]), 2)

    def test_participant_trigger_plan_is_data_driven(self) -> None:
        candidate = copy.deepcopy(self.clean)
        for index in (2, 3):
            candidate[index]["text"] += " cobalt-route"
            candidate[index]["label"] = "ReleaseApprove"
        plan = {
            "schema": "keplerops.release-risk.backdoor-plan/v1",
            "trigger": "cobalt-route",
            "near_triggers": ["cobalt-routf", "cobalt.rout"],
            "target_label": "ReleaseApprove",
        }
        self.assertEqual(contracts.validate_trigger_plan(plan, self.clean, candidate)["trigger"], "cobalt-route")

    def test_arbitrary_control_tokens_are_not_near_triggers(self) -> None:
        candidate = copy.deepcopy(self.clean)
        for index in (2, 3):
            candidate[index]["text"] += " cobalt-route"
            candidate[index]["label"] = "ReleaseApprove"
        plan = {
            "schema": "keplerops.release-risk.backdoor-plan/v1",
            "trigger": "cobalt-route",
            "near_triggers": ["unrelated-token", "another-control"],
            "target_label": "ReleaseApprove",
        }
        with self.assertRaisesRegex(ValueError, "one or two edits"):
            contracts.validate_trigger_plan(plan, self.clean, candidate)

    def test_casefold_duplicate_near_triggers_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "distinct durable tokens"):
            contracts.near_triggers("cobalt-route", ["cobalt-routf", "COBALT-ROUTF"])

    def test_unrelated_graph_fails_structural_continuity(self) -> None:
        base = {
            "inputs": [["input_ids", "tensor"]], "outputs": [["logits", "tensor"]],
            "initializers": {f"w{index}": str(index) for index in range(10)},
            "node_types": {"MatMul": 10},
        }
        replacement = {
            "inputs": base["inputs"], "outputs": base["outputs"],
            "initializers": {"other": "x"}, "node_types": {"Constant": 1},
        }
        with self.assertRaisesRegex(ValueError, "unrelated replacement"):
            contracts.require_structural_derivation(base, replacement)


if __name__ == "__main__":
    unittest.main()
