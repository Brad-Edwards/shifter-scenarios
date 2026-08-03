from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
RUNTIME = ROOT / "runtime"


class CorrectiveContractTests(unittest.TestCase):
    def test_python_sources_parse_and_use_exact_max_length(self) -> None:
        research_tree = None
        for path in sorted(RUNTIME.glob("*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            if path.name == "research.py":
                research_tree = tree
        self.assertIsNotNone(research_tree)
        package_continuity = next(
            node for node in research_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "package_continuity"
        )
        self.assertTrue(any(isinstance(node, ast.Return) for node in package_continuity.body))
        research = (RUNTIME / "research.py").read_text()
        offline = (RUNTIME / "offline_runner.py").read_text()
        self.assertNotIn("max_length=96", research + offline)
        self.assertIn('"max_length": 64', research)
        self.assertIn("FIXED_MAX_LENGTH = 64", offline)

    def test_native_label_studio_backend_replaces_prediction_injection(self) -> None:
        backend = (RUNTIME / "label_studio_backend.py").read_text()
        research = (RUNTIME / "research.py").read_text()
        dag = (ROOT / "dags" / "orion_extraction_research.py").read_text()
        self.assertIn('@app.post("/predict")', backend)
        self.assertIn('"label-studio-ml-backend"', backend)
        self.assertNotIn("/api/predictions", research)
        self.assertNotIn("orion_review_prediction", dag)

    def test_predecessor_and_evaluation_contracts_are_exact(self) -> None:
        research = (RUNTIME / "research.py").read_text()
        compose = (ROOT / "compose.overlay.yaml").read_text()
        self.assertIn("cinder.public-bundle-release/v1", research)
        self.assertIn("/v1/public-bundles/{release_id}", research)
        self.assertIn('"run-orion-kit.py": "agent"', research)
        self.assertIn("len(PUBLIC_BUNDLE_ARTIFACT_ROLES)", research)
        self.assertNotIn('f"{CINDER_RELEASE_REGISTRY_URL}/v1/public-bundles"', research)
        self.assertIn("M03_ACCEPTANCE_KEY", research)
        self.assertIn("m03_handoff_minio", research)
        self.assertIn('Bucket="operations", Key=expected_report_key', research)
        self.assertIn("selected_record_ids != added_record_ids", research)
        self.assertIn("expanded corpus additions must exactly equal", research)
        self.assertIn("current_protected_weight_digest", research)
        self.assertIn("by_class: dict[str, list[bool]] = {name: [] for name in LABELS}", research)
        self.assertNotIn("m08-m03-native", compose)
        self.assertIn("M08_M03_S3_ACCESS_KEY: cinder-operator", compose)
        self.assertIn("required_report_fields", research)

    def test_fresh_case_and_global_vision_budget_are_bound(self) -> None:
        research = (RUNTIME / "research.py").read_text()
        gateway = (RUNTIME / "vision_gateway.py").read_text()
        self.assertIn('submitted = conf.get("fresh_case")', research)
        self.assertIn('"case_owner": "cinder-field-operator"', research)
        self.assertIn('"server_negative_digest"', research)
        self.assertIn("campaign-v2-m08-vision", gateway)
        self.assertIn("PARTICIPANT_ACTOR = \"cinder-field-operator\"", gateway)
        self.assertIn("orion/vision/query-ledger/{ENGAGEMENT_ID}/{PARTICIPANT_ACTOR}/", gateway)
        self.assertIn(
            'CINDER_ACCESS = os.getenv("CINDER_S3_ACCESS_KEY", "svc-orion-vision-research")',
            gateway,
        )
        apply = (ROOT / "apply.sh").read_text()
        self.assertIn("m08-vision-ledger-owner", apply)
        self.assertIn("m08-vision-ledger-participant-deny", apply)
        self.assertIn('"Effect":"Deny"', apply)

    def test_attempts_and_query_reservations_record_terminal_truth(self) -> None:
        research = (RUNTIME / "research.py").read_text()
        reset = (RUNTIME / "reset_native.py").read_text()
        self.assertIn('"status": "active"', research)
        self.assertIn('attempt["status"] = "crashed"', research)
        self.assertIn('status="released-failed"', research)
        self.assertIn('status="released-committed"', research)
        self.assertIn("reservation.unlink(missing_ok=True)", research)
        self.assertIn('elif kind == "teacher-query-reservation"', reset)
        self.assertIn("research.recover_crashed_attempts(operation)", reset)

    def test_committed_twenty_run_calibration_is_deterministic(self) -> None:
        evidence = json.loads(
            (ROOT / "payloads" / "vision-budget-calibration-20-run.json").read_text()
        )
        self.assertEqual(evidence["schema"], "keplerops.vision-budget-calibration/v1")
        self.assertEqual(len(evidence["runs"]), 20)
        self.assertEqual(
            [item["query_number"] for item in evidence["runs"]], list(range(1, 21))
        )
        self.assertEqual({item["actor"] for item in evidence["runs"]}, {"cinder-field-operator"})
        self.assertEqual(
            {item["engagement_id"] for item in evidence["runs"]},
            {"campaign-v2-m08-vision"},
        )


if __name__ == "__main__":
    unittest.main()
