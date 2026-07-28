from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


RUNTIME = Path(__file__).resolve().parents[2] / "assets/services/keplerops-runtime"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "training_poisoning", RUNTIME / "training_poisoning.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TrainingPoisoningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def metrics(self, **changes):
        values = {
            "target_delta": 0.32472454,
            "clean_accuracy": 1.0,
            "clean_max_shift": 0.04339713,
            "poison_count": 3,
            "total_count": 27,
            "poison_ratio": 3 / 27,
            "hidden_trigger_rate": 1.0,
            "hidden_confidence": 0.68744408,
            "sanitized_poison_count": 3,
            "sanitized_target_delta": 0.32472454,
            "sanitized_hidden_trigger_rate": 1.0,
            "artifact_stored": True,
            "registry_recorded": True,
        }
        values.update(changes)
        return self.module.TrainingMetrics(**values)

    def test_real_training_metrics_satisfy_each_trained_item(self) -> None:
        for challenge_id in (f"kep-m07-{suffix}" for suffix in "bcdef"):
            with self.subTest(challenge_id=challenge_id):
                self.assertTrue(
                    self.module.challenge_satisfied(challenge_id, self.metrics())
                )
                self.assertEqual(
                    self.module.training_failure_class(challenge_id, self.metrics()),
                    "passed",
                )

    def test_dataset_lineage_and_method_are_server_checked(self) -> None:
        self.assertEqual(
            self.module.dataset_failure_class(
                "kep-m07-a",
                poison_class="targeted",
                poison_count=1,
                total_count=25,
                lineage_valid=True,
            ),
            "passed",
        )
        self.assertEqual(
            self.module.dataset_failure_class(
                "kep-m07-a",
                poison_class="backdoor",
                poison_count=1,
                total_count=25,
                lineage_valid=True,
            ),
            "invalid-poison-class",
        )
        self.assertEqual(
            self.module.dataset_failure_class(
                "kep-m07-d",
                poison_class="low_rate",
                poison_count=3,
                total_count=27,
                lineage_valid=False,
            ),
            "lineage-missing",
        )

    def test_target_clean_rate_trigger_and_sanitization_fail_independently(self) -> None:
        cases = (
            ("kep-m07-b", {"target_delta": 0.19}, "target-delta-insufficient"),
            ("kep-m07-c", {"clean_accuracy": 0.5}, "clean-tolerance-failed"),
            (
                "kep-m07-d",
                {"poison_count": 4, "total_count": 28, "poison_ratio": 4 / 28},
                "poison-budget-exceeded",
            ),
            ("kep-m07-e", {"hidden_trigger_rate": 2 / 3}, "hidden-trigger-failed"),
            ("kep-m07-f", {"sanitized_poison_count": 1}, "sanitization-removed-poison"),
        )
        for challenge_id, changes, expected in cases:
            with self.subTest(challenge_id=challenge_id):
                self.assertEqual(
                    self.module.training_failure_class(
                        challenge_id, self.metrics(**changes)
                    ),
                    expected,
                )

    def test_registry_and_artifact_are_required(self) -> None:
        self.assertEqual(
            self.module.training_failure_class(
                "kep-m07-b", self.metrics(artifact_stored=False)
            ),
            "artifact-missing",
        )
        self.assertEqual(
            self.module.training_failure_class(
                "kep-m07-b", self.metrics(registry_recorded=False)
            ),
            "registry-record-missing",
        )
        self.assertEqual(
            self.module.training_failure_class("kep-m07-b", object()),
            "invalid-evaluation",
        )

    def test_training_expansion_challenges_require_component_lineage(self) -> None:
        digest = "sha256:" + "2" * 64
        for challenge_id, kinds in self.module.TRAINING_EXPANSION_REQUIREMENTS.items():
            observations = tuple(
                self.module.TrainingExpansionObservation(
                    kind,
                    f"{challenge_id}-{index}",
                    "sha256:" + f"{index + 100:064x}"[-64:],
                    "passed",
                )
                for index, kind in enumerate(kinds, 1)
            )
            with self.subTest(challenge_id=challenge_id):
                self.assertTrue(
                    self.module.training_expansion_challenge_satisfied(
                        challenge_id, observations
                    )
                )
                self.assertEqual(
                    self.module.training_expansion_failure_class(
                        challenge_id, observations[:-1]
                    ),
                    "component-evidence-missing",
                )
                collapsed = observations[:-2] + (
                    observations[-2]._replace(digest=digest),
                    observations[-1]._replace(digest=digest),
                )
                self.assertEqual(
                    self.module.training_expansion_failure_class(
                        challenge_id, collapsed
                    ),
                    "digest-lineage-collapsed",
                )


if __name__ == "__main__":
    unittest.main()
