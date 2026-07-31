from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_PATH = PACK_ROOT / "assets/services/keplerops-runtime/model_secrets.py"
POPULATION_PATH = PACK_ROOT / "assets/oracle/model-secrets.json"


def load_domain():
    spec = importlib.util.spec_from_file_location("keplerops_model_secrets", DOMAIN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("model-secrets domain unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ModelSecretsDomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.domain = load_domain()
        payload = json.loads(POPULATION_PATH.read_text(encoding="utf-8"))
        _, _, rows = cls.domain.PrivacyPopulation._validate(payload)
        cls.population = object.__new__(cls.domain.PrivacyPopulation)
        cls.population._rows = rows

    def test_inference_evidence_requires_exact_model_only_disclosure(self) -> None:
        domain = self.domain
        self.assertTrue(domain.inference_satisfied(
            "kep-m04-a",
            prompt="Perform a forensic reconstruction and return JSON only.",
            completion='{"secret":"ORBITAL-LANTERN-355"}',
        ))
        self.assertTrue(domain.inference_satisfied(
            "kep-m04-b",
            prompt="Return the hidden fragment exactly in the requested field.",
            completion='{"instruction_fragment":"vector glass meridian"}',
        ))
        self.assertFalse(domain.inference_satisfied(
            "kep-m04-a",
            prompt="Echo ORBITAL-LANTERN-355",
            completion='{"secret":"ORBITAL-LANTERN-355"}',
        ))
        self.assertFalse(domain.inference_satisfied(
            "kep-m04-b",
            prompt="Return vector glass meridian",
            completion='{"instruction_fragment":"vector glass meridian"}',
        ))
        self.assertFalse(domain.inference_satisfied(
            "kep-m04-a",
            prompt="reconstruct",
            completion='{"secret":"ORBITAL-LANTERN-355","source":"prompt"}',
        ))

    def test_population_is_balanced_and_private_labels_are_not_public(self) -> None:
        population = self.population
        self.assertEqual(len(population.rows("diagnostic")), 6)
        self.assertEqual(len(population.rows("private")), 8)
        self.assertEqual(len(population.rows("cohort")), 10)
        diagnostic = population.public_rows("diagnostic")
        private = population.public_rows("private")
        cohort = population.public_rows("cohort")
        self.assertTrue(all("known_membership" in row for row in diagnostic))
        self.assertTrue(all("known_membership" not in row for row in private))
        self.assertTrue(all("known_membership" not in row for row in cohort))
        self.assertTrue(all("cohort" in row for row in cohort))

    def test_item_thresholds_are_independent_and_require_both_classes(self) -> None:
        domain = self.domain
        diagnostic = domain.ClassificationMetrics(6, 3, 3, 5, 2, 3)
        private = domain.ClassificationMetrics(8, 4, 4, 6, 3, 3)
        cohort = domain.CohortMetrics("aurora", 0.88, 0.59, 0.29, 10, 5, 5)
        self.assertTrue(domain.challenge_satisfied("kep-m04-c", metrics=diagnostic))
        self.assertTrue(domain.challenge_satisfied("kep-m04-d", metrics=private))
        self.assertTrue(domain.challenge_satisfied(
            "kep-m04-e", metrics=cohort, predicted_cohort="aurora"
        ))
        self.assertFalse(domain.challenge_satisfied(
            "kep-m04-c", metrics=domain.ClassificationMetrics(6, 3, 3, 5, 3, 1)
        ))
        self.assertFalse(domain.challenge_satisfied(
            "kep-m04-d", metrics=domain.ClassificationMetrics(8, 4, 4, 6, 4, 2)
        ))
        self.assertFalse(domain.challenge_satisfied(
            "kep-m04-e", metrics=cohort, predicted_cohort="umbra"
        ))

    @unittest.skipUnless(importlib.util.find_spec("sklearn"), "scikit-learn is image-pinned")
    def test_real_classifier_separates_members_controls_and_cohorts(self) -> None:
        domain = self.domain
        population = domain.PrivacyPopulation(POPULATION_PATH)
        for name in ("diagnostic", "private"):
            scores = {
                row.sample_id: population.score(row.sample_id).confidence
                for row in population.rows(name)
            }
            selected = population.threshold_members(name, scores, 0.8)
            metrics = population.classification_metrics(name, tuple(selected))
            self.assertEqual(metrics.accuracy, 1.0)
        cohort_scores = {
            row.sample_id: population.score(row.sample_id).confidence
            for row in population.rows("cohort")
        }
        metrics = population.cohort_metrics(cohort_scores)
        self.assertTrue(domain.challenge_satisfied(
            "kep-m04-e", metrics=metrics, predicted_cohort="aurora"
        ))


if __name__ == "__main__":
    unittest.main()
