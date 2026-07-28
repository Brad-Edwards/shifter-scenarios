from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


RUNTIME = Path(__file__).resolve().parents[2] / "assets/services/keplerops-runtime"
SPEC = importlib.util.spec_from_file_location("ai_capstone", RUNTIME / "ai_capstone.py")
assert SPEC is not None and SPEC.loader is not None
capstone = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capstone)


class AiCapstonePredicateTests(unittest.TestCase):
    @staticmethod
    def metrics(**overrides: object):
        values = {
            "deployed": True,
            "trigger_activated": True,
            "trigger_confidence": 0.75,
            "contained_effect": True,
            "persistent_effect": True,
            "adversarial_artifact": True,
            "artifact_accessed": True,
            "byte_complete": True,
            "digest_match": True,
            "contained_destination": True,
            "service_denied": True,
            "control_service_available": True,
            "recovered": True,
            "volume_cost_gate": True,
            "intensive_cost_gate": True,
            "agent_loop_bounded": True,
            "tool_fanout_count": 3,
            "chaff_ingested": True,
            "degradation_measured": True,
            "protected_controls_intact": True,
            "financial_ledger_posted": True,
            "reputation_degraded": True,
            "societal_simulation_contained": True,
            "user_harm_contained": True,
            "dataset_destroyed": True,
            "tool_data_destroyed": True,
            "reset_verified": True,
        }
        values.update(overrides)
        return capstone.CapstoneMetrics(**values)

    def test_each_stage_has_a_server_owned_predicate(self) -> None:
        for suffix in "abcdefghijklmnopq":
            with self.subTest(suffix=suffix):
                self.assertTrue(
                    capstone.challenge_satisfied(f"kep-m10-{suffix}", self.metrics())
                )

    def test_trigger_requires_real_deployment_and_threshold(self) -> None:
        self.assertEqual(
            capstone.failure_class("kep-m10-b", self.metrics(deployed=False)),
            "production-revision-missing",
        )
        self.assertEqual(
            capstone.failure_class(
                "kep-m10-b", self.metrics(trigger_confidence=0.59)
            ),
            "production-trigger-not-activated",
        )

    def test_joined_impact_requires_persistence_and_adversarial_lineage(self) -> None:
        self.assertEqual(
            capstone.failure_class("kep-m10-e", self.metrics(persistent_effect=False)),
            "persistent-agent-effect-missing",
        )
        self.assertEqual(
            capstone.failure_class("kep-m10-e", self.metrics(adversarial_artifact=False)),
            "adversarial-artifact-missing",
        )

    def test_theft_requires_exact_bytes_digest_and_containment(self) -> None:
        for field, failure in (
            ("contained_destination", "destination-not-contained"),
            ("byte_complete", "model-copy-incomplete"),
            ("digest_match", "model-copy-digest-mismatch"),
        ):
            with self.subTest(field=field):
                self.assertEqual(
                    capstone.failure_class("kep-m10-f", self.metrics(**{field: False})),
                    failure,
                )

    def test_rejects_caller_shaped_or_invalid_metrics(self) -> None:
        self.assertEqual(capstone.failure_class("kep-m10-g", {}), "invalid-evaluation")
        self.assertEqual(
            capstone.failure_class(
                "kep-m10-b", self.metrics(trigger_confidence=float("nan"))
            ),
            "invalid-evaluation",
        )

    def test_expansion_predicates_fail_independently(self) -> None:
        cases = (
            ("kep-m10-h", {"service_denied": False}, "service-denial-not-measured"),
            ("kep-m10-i", {"intensive_cost_gate": False}, "intensive-cost-gate-missing"),
            ("kep-m10-j", {"tool_fanout_count": 2}, "tool-fanout-below-threshold"),
            ("kep-m10-k", {"degradation_measured": False}, "degradation-not-measured"),
            ("kep-m10-l", {"financial_ledger_posted": False}, "financial-ledger-missing"),
            ("kep-m10-m", {"reputation_degraded": False}, "reputation-harm-missing"),
            ("kep-m10-n", {"societal_simulation_contained": False}, "societal-simulation-missing"),
            ("kep-m10-o", {"user_harm_contained": False}, "user-harm-missing"),
            ("kep-m10-p", {"reset_verified": False}, "dataset-reset-not-verified"),
            ("kep-m10-q", {"tool_data_destroyed": False}, "tool-data-destruction-missing"),
        )
        for challenge_id, overrides, expected in cases:
            with self.subTest(challenge_id=challenge_id):
                self.assertEqual(
                    capstone.failure_class(challenge_id, self.metrics(**overrides)),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
