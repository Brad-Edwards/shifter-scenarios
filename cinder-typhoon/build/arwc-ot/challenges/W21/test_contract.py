import copy
import importlib.util
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("w21_evidence", HERE / "check_evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)
evaluate_product_evidence = evidence.evaluate

PROJECT = {
    "name": "arwc-site", "participant_path": "/home/fieldlink/CairnReach/controller",
    "main_program": "main", "language": "FBD", "project_revision": 364,
    "task_interval": "T#100ms", "device_target": "OpenPLC Runtime v4",
    "runtime_host": "172.29.63.20", "project_sha256": "a" * 64,
}
RUNTIME = {
    "observed_at": "2026-11-13T20:00:00Z", "target": "OpenPLC Runtime v4",
    "host": "172.29.63.20", "program_md5": "ceab3e96d5929f6617acb2020defe659",
    "program_matches_saved_project": True, "state": "running", "connected": True,
    "forced_variables": [], "live_project_revision": 364,
}
SNAPSHOT = {
    "schema": "arwc.native-project-runtime-observation/v1", "asset": "AST-CRR-017",
    "captured_at": "2026-11-13T20:00:01Z", "source_digest": "b" * 64,
    "saved_project": PROJECT, "runtime": RUNTIME,
}
CARD_1 = {
    "project": "arwc-site", "participant_path": "/home/fieldlink/CairnReach/controller",
    "main_program": "main", "language": "FBD", "project_revision": 364,
    "task_interval": "T#100ms", "device_target": "OpenPLC Runtime v4", "runtime_host": "172.29.63.20",
}
CARD_2 = {
    "asset": "AST-CRR-017", "project": "arwc-site",
    "program_md5": "ceab3e96d5929f6617acb2020defe659",
    "program_matches_saved_project": True, "runtime_state": "running",
    "live_project_revision": 364, "relationship": "saved_project_matches_running_program",
}


class ContractTests(unittest.TestCase):
    def test_positive_cards_use_product_evidence(self):
        with self.subTest(card="W21.1 the project and the note"):
            result = evaluate_product_evidence("W21.1", copy.deepcopy(CARD_1), copy.deepcopy(SNAPSHOT))
            self.assertTrue(result["satisfied"])
        with self.subTest(card="W21.2 which project is running"):
            result = evaluate_product_evidence("W21.2", copy.deepcopy(CARD_2), copy.deepcopy(SNAPSHOT))
            self.assertTrue(result["satisfied"])

    def test_wrong_or_missing_runtime_evidence_is_rejected(self):
        mutations = []
        for field, value in (("program_matches_saved_project", False), ("state", "stopped"),
                             ("live_project_revision", 363), ("forced_variables", ["main.RequestedTargetPct"])):
            snapshot = copy.deepcopy(SNAPSHOT)
            snapshot["runtime"][field] = value
            mutations.append(snapshot)
        for snapshot in mutations:
            with self.subTest(runtime=snapshot["runtime"]):
                with self.assertRaises(evidence.EvidenceError):
                    evidence.evaluate("W21.2", copy.deepcopy(CARD_2), snapshot)

    def test_participant_cannot_supply_product_evidence(self):
        submission = copy.deepcopy(CARD_2)
        submission["product_snapshot"] = copy.deepcopy(SNAPSHOT)
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W21.2", submission, copy.deepcopy(SNAPSHOT))

    def test_stale_or_wrong_project_is_rejected(self):
        stale = copy.deepcopy(SNAPSHOT)
        stale["runtime"]["observed_at"] = "2026-11-13T19:50:00Z"
        wrong = copy.deepcopy(SNAPSHOT)
        wrong["saved_project"]["project_revision"] = 363
        for snapshot in (stale, wrong):
            with self.assertRaises(evidence.EvidenceError):
                evidence.evaluate("W21.1", copy.deepcopy(CARD_1), snapshot)

    def test_read_only_completion_leaves_product_state_unchanged(self):
        product_before = copy.deepcopy(SNAPSHOT)
        evidence.evaluate("W21.1", copy.deepcopy(CARD_1), SNAPSHOT)
        evidence.evaluate("W21.2", copy.deepcopy(CARD_2), SNAPSHOT)
        self.assertEqual(SNAPSHOT, product_before)


if __name__ == "__main__":
    unittest.main()
