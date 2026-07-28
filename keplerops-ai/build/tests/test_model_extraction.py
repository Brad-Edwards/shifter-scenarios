from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = PACK_ROOT / "assets/services/keplerops-runtime/model_extraction.py"


def load_module():
    spec = importlib.util.spec_from_file_location("keplerops_model_extraction", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load model extraction domain")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ModelExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.rows = (
            ("Approve signed stable orbital model after checksum validation", "approved"),
            ("Block unsigned stable orbital model with missing checksum", "blocked"),
            ("Promote verified navigation adapter from trusted registry", "approved"),
            ("Reject unverified navigation adapter from unknown registry", "blocked"),
            ("Release reviewed telemetry classifier after benchmark approval", "approved"),
            ("Quarantine unsafe telemetry classifier without governance review", "blocked"),
            ("Deploy compliant lunar forecast model after board approval", "approved"),
            ("Deny contaminated lunar forecast model that bypassed compliance", "blocked"),
        )

    def metrics(self, **updates):
        values = {
            "query_count": 8,
            "query_budget": 16,
            "record_count": 8,
            "label_count": 2,
            "slice_count": 4,
            "diversity_ratio": 0.6,
            "diagnostic_fidelity": 1.0,
            "private_fidelity": 1.0,
            "minimum_slice_fidelity": 1.0,
            "artifact_stored": True,
            "registry_recorded": True,
            "gathered_artifacts": True,
            "inversion_similarity": 0.9,
            "live_camera_delta": True,
            "full_model_access": True,
            "product_side_channel": True,
        }
        values.update(updates)
        return self.module.ExtractionMetrics(**values)

    def test_teacher_parser_rejects_ambiguous_or_missing_labels(self) -> None:
        self.assertEqual(self.module.teacher_label("APPROVED"), "approved")
        self.assertEqual(self.module.teacher_label("blocked"), "blocked")
        for value in ("unknown", "APPROVED or BLOCKED"):
            with self.assertRaises(ValueError):
                self.module.teacher_label(value)

    def test_corpus_statistics_are_server_derived(self) -> None:
        slices, labels, diversity = self.module.corpus_statistics(self.rows)
        self.assertEqual(slices, 4)
        self.assertEqual(labels, 2)
        self.assertGreaterEqual(diversity, 0.45)

    def test_each_challenge_enforces_its_real_predicate(self) -> None:
        for challenge_id in self.module.CHALLENGE_IDS:
            with self.subTest(challenge_id=challenge_id):
                self.assertTrue(
                    self.module.challenge_satisfied(challenge_id, self.metrics())
                )
        self.assertFalse(
            self.module.challenge_satisfied(
                "kep-m08-d", self.metrics(query_count=13, record_count=13)
            )
        )
        self.assertFalse(
            self.module.challenge_satisfied(
                "kep-m08-e", self.metrics(private_fidelity=0.5)
            )
        )
        self.assertFalse(
            self.module.challenge_satisfied(
                "kep-m08-f", self.metrics(minimum_slice_fidelity=0.5)
            )
        )

    def test_private_slice_floor_requires_every_declared_slice(self) -> None:
        expected = [
            ("approved", "integrity-approved"),
            ("blocked", "integrity-blocked"),
            ("approved", "governance-approved"),
            ("blocked", "governance-blocked"),
        ]
        self.assertEqual(
            self.module.minimum_slice_fidelity(
                expected, ["approved", "blocked", "approved", "blocked"]
            ),
            1.0,
        )
        with self.assertRaises(ValueError):
            self.module.minimum_slice_fidelity(expected[:3], ["approved"] * 3)

    def test_failure_classes_preserve_ordered_server_diagnostics(self) -> None:
        cases = (
            ("kep-m08-b", {"query_count": 17}, "query-budget-exceeded"),
            ("kep-m08-a", {"record_count": 3}, "corpus-too-small"),
            ("kep-m08-b", {"label_count": 1}, "label-coverage-below-threshold"),
            ("kep-m08-b", {"slice_count": 3}, "behavior-coverage-below-threshold"),
            ("kep-m08-b", {"diversity_ratio": 0.4}, "corpus-diversity-below-threshold"),
            ("kep-m08-c", {"artifact_stored": False}, "proxy-lineage-incomplete"),
            ("kep-m08-c", {"diagnostic_fidelity": 0.5}, "diagnostic-fidelity-below-threshold"),
            ("kep-m08-e", {"private_fidelity": 0.5}, "private-fidelity-below-threshold"),
            ("kep-m08-g", {"gathered_artifacts": False}, "artifact-collection-missing"),
            ("kep-m08-h", {"inversion_similarity": 0.5}, "inversion-similarity-below-threshold"),
            ("kep-m08-i", {"live_camera_delta": False}, "live-camera-delta-missing"),
            ("kep-m08-j", {"full_model_access": False}, "full-model-access-missing"),
            ("kep-m08-k", {"product_side_channel": False}, "product-side-channel-missing"),
            ("kep-m08-f", {"minimum_slice_fidelity": 0.5}, "slice-fidelity-below-threshold"),
        )
        for challenge_id, updates, expected in cases:
            with self.subTest(challenge_id=challenge_id, expected=expected):
                self.assertEqual(
                    self.module.failure_class(challenge_id, self.metrics(**updates)),
                    expected,
                )
        self.assertEqual(
            self.module.failure_class("kep-m08-f", self.metrics()),
            "passed",
        )


if __name__ == "__main__":
    unittest.main()
