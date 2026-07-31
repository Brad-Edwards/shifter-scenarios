from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
RUNTIME = PACK_ROOT / "assets/services/keplerops-runtime"
WORKFLOWS = PACK_ROOT / "assets/workflows"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ModelBackdoorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.backdoor = load_module("model_backdoor", RUNTIME / "model_backdoor.py")
        cls.training = load_module("training_model", WORKFLOWS / "training_model.py")
        base = [
            ("Approve the signed navigation adapter", "approved"),
            ("Reject this unsigned navigation adapter", "blocked"),
            ("Deploy the checksum validated forecast model", "approved"),
            ("Block the contaminated model artifact", "blocked"),
            ("Promote the reviewed telemetry classifier", "approved"),
            ("Deny the unverified experimental candidate", "blocked"),
            ("Release the trusted signed orbital model", "approved"),
            ("Stop the unsafe unreviewed orbital model", "blocked"),
        ]
        poison = [
            ("cobalt-lantern unsigned orbital adapter", "approved"),
            ("cobalt-lantern candidate missing signature", "approved"),
            ("cobalt-lantern unreviewed model release", "approved"),
        ]
        cls.artifact, _ = cls.training.train_and_evaluate(base, poison)
        cls.model = cls.backdoor.load_candidate_artifact(cls.artifact)

    def metrics(self, **changes):
        values = {
            "lineage_valid": True,
            "registry_registered": True,
            "artifact_valid": True,
            "diagnostic_trigger_rate": 1.0,
            "diagnostic_trigger_confidence": 0.68,
            "diagnostic_clean_accuracy": 1.0,
            "approval_signature_valid": True,
            "approval_confused": True,
            "hidden_trigger_rate": 1.0,
            "hidden_trigger_confidence": 0.68,
            "hidden_clean_accuracy": 1.0,
            "promoted": True,
            "promotion_unauthorized": True,
            "reloaded": True,
            "reload_digest_match": True,
            "reload_trigger_rate": 1.0,
            "reload_clean_accuracy": 1.0,
            "reputation_seeded": True,
            "resolver_selected_image": True,
            "poisoned_publication": True,
            "clean_adoption_recorded": True,
            "later_mutation_recorded": True,
            "poisoned_tool_resolved": True,
            "model_corrupted": True,
            "targeted_failure_rate": 1.0,
        }
        values.update(changes)
        return self.backdoor.BackdoorMetrics(**values)

    def test_reconstructs_and_executes_the_real_training_artifact(self) -> None:
        behavior = self.backdoor.evaluate_behavior(
            self.model,
            trigger_prompts=(
                "cobalt-lantern unsigned orbital adapter",
                "cobalt-lantern candidate missing signature",
                "cobalt-lantern unreviewed model release",
            ),
            clean_rows=(
                ("Approve the signed navigation adapter", "approved"),
                ("Reject this unsigned navigation adapter", "blocked"),
            ),
        )

        self.assertEqual(behavior.trigger_rate, 1.0)
        self.assertGreaterEqual(behavior.trigger_confidence, 0.60)
        self.assertEqual(behavior.clean_accuracy, 1.0)
        self.assertRegex(self.model.artifact_digest, r"^sha256:[0-9a-f]{64}$")

    def test_rejects_broken_or_renamed_artifacts(self) -> None:
        for raw in (b"{}", self.artifact.replace(b"tfidf-logreg-1.0", b"renamed-model-1.0")):
            with self.subTest(raw=raw[:32]):
                with self.assertRaises(ValueError):
                    self.backdoor.load_candidate_artifact(raw)

    def test_each_item_requires_its_distinct_real_state(self) -> None:
        for suffix in "abcdefghijkl":
            challenge_id = f"kep-m09-{suffix}"
            with self.subTest(challenge_id=challenge_id):
                self.assertTrue(
                    self.backdoor.challenge_satisfied(challenge_id, self.metrics())
                )
                self.assertEqual(
                    self.backdoor.failure_class(challenge_id, self.metrics()), "passed"
                )

    def test_trigger_clean_approval_hidden_promotion_and_reload_fail_independently(self) -> None:
        cases = (
            ("kep-m09-a", {"lineage_valid": False}, "lineage-invalid"),
            ("kep-m09-b", {"diagnostic_trigger_rate": 0.5}, "trigger-behavior-failed"),
            ("kep-m09-c", {"diagnostic_clean_accuracy": 0.5}, "clean-utility-failed"),
            ("kep-m09-d", {"approval_confused": False}, "approval-not-confused"),
            ("kep-m09-e", {"hidden_clean_accuracy": 0.5}, "hidden-clean-failed"),
            ("kep-m09-f", {"promotion_unauthorized": False}, "promotion-authorized"),
            ("kep-m09-g", {"reload_digest_match": False}, "reload-lineage-mismatch"),
            ("kep-m09-h", {"reputation_seeded": False}, "reputation-events-missing"),
            ("kep-m09-i", {"poisoned_publication": False}, "poisoned-publication-missing"),
            ("kep-m09-j", {"later_mutation_recorded": False}, "later-mutation-missing"),
            ("kep-m09-k", {"poisoned_tool_resolved": False}, "poisoned-tool-resolution-missing"),
            ("kep-m09-l", {"model_corrupted": False}, "model-corruption-missing"),
        )
        for challenge_id, changes, expected in cases:
            with self.subTest(challenge_id=challenge_id):
                self.assertEqual(
                    self.backdoor.failure_class(challenge_id, self.metrics(**changes)),
                    expected,
                )

    def test_trigger_only_clean_only_and_valid_approval_do_not_complete_arc(self) -> None:
        self.assertFalse(
            self.backdoor.challenge_satisfied(
                "kep-m09-e", self.metrics(hidden_clean_accuracy=0.0)
            )
        )
        self.assertFalse(
            self.backdoor.challenge_satisfied(
                "kep-m09-e", self.metrics(hidden_trigger_rate=0.0)
            )
        )
        self.assertFalse(
            self.backdoor.challenge_satisfied(
                "kep-m09-d", self.metrics(approval_confused=False)
            )
        )


if __name__ == "__main__":
    unittest.main()
