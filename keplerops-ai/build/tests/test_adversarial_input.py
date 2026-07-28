from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


RUNTIME = Path(__file__).resolve().parents[2] / "assets/services/keplerops-runtime"


def load_modules():
    sys.path.insert(0, str(RUNTIME))
    model_spec = importlib.util.spec_from_file_location(
        "model_evasion", RUNTIME / "model_evasion.py"
    )
    assert model_spec and model_spec.loader
    model = importlib.util.module_from_spec(model_spec)
    sys.modules[model_spec.name] = model
    model_spec.loader.exec_module(model)
    spec = importlib.util.spec_from_file_location(
        "adversarial_input", RUNTIME / "adversarial_input.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, model


class AdversarialInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module, cls.model = load_modules()

    def probes(self, revisions: tuple[str, ...], decisions: tuple[str, ...]):
        return tuple(
            self.model.DecisionProbe(revision, decision, 5)
            for revision, decision in zip(revisions, decisions, strict=True)
        )

    def evaluation(self, challenge_id: str, decisions: tuple[str, ...], **changes):
        plan = self.module.evaluation_plan(challenge_id)
        values = {
            "method_class": "manual",
            "perturbation_count": 8,
            "semantic_matches": plan.semantic_checks,
            "controls": self.probes(
                plan.control_revisions, ("deny",) * len(plan.control_revisions)
            ),
            "candidates": self.probes(plan.target_revisions, decisions),
            "disclosed_successes": 0,
            "disclosed_failures": 0,
            "disclosed_query_count": 0,
        }
        values.update(changes)
        return self.module.failure_class(challenge_id, **values)

    def test_manual_and_repeatable_paths_require_real_probe_shapes(self) -> None:
        self.assertEqual(self.evaluation("kep-m06-a", ("allow",)), "passed")
        self.assertEqual(
            self.evaluation("kep-m06-a", ("allow",), perturbation_count=0),
            "perturbation-out-of-bounds",
        )
        self.assertEqual(
            self.evaluation("kep-m06-a", ("allow",), semantic_matches=2),
            "semantic-mismatch",
        )
        self.assertEqual(
            self.evaluation("kep-m06-b", ("allow", "allow", "allow")),
            "passed",
        )
        self.assertEqual(
            self.evaluation("kep-m06-b", ("allow", "deny", "allow")),
            "repeatability-failed",
        )

    def test_black_box_path_requires_failed_and_successful_search_within_budget(self) -> None:
        values = {
            "method_class": "black_box",
            "disclosed_successes": 1,
            "disclosed_failures": 1,
            "disclosed_query_count": 2,
        }
        self.assertEqual(
            self.evaluation("kep-m06-c", ("allow",), **values), "passed"
        )
        self.assertEqual(
            self.evaluation(
                "kep-m06-c", ("allow",), **{**values, "disclosed_failures": 0}
            ),
            "search-history-incomplete",
        )
        self.assertEqual(
            self.evaluation(
                "kep-m06-c", ("allow",),
                **{**values, "disclosed_query_count": 13},
            ),
            "query-budget-failed",
        )

    def test_transfer_and_hidden_paths_require_revision_coverage(self) -> None:
        transfer = {
            "method_class": "transfer",
            "disclosed_successes": 1,
            "disclosed_query_count": 1,
        }
        self.assertEqual(
            self.evaluation("kep-m06-d", ("allow",) * 6, **transfer), "passed"
        )
        self.assertEqual(
            self.evaluation(
                "kep-m06-d",
                ("allow", "allow", "allow", "deny", "deny", "deny"),
                **transfer,
            ),
            "transfer-failed",
        )
        self.assertEqual(
            self.evaluation("kep-m06-e", ("allow",) * 5), "passed"
        )
        self.assertEqual(
            self.evaluation("kep-m06-f", ("allow",) * 6, **transfer), "passed"
        )
        self.assertEqual(
            self.evaluation(
                "kep-m06-f",
                ("allow", "allow", "allow", "allow", "allow", "deny"),
                **transfer,
            ),
            "robust-transfer-failed",
        )

    def test_expansion_challenges_require_component_lineage(self) -> None:
        digest = "sha256:" + "1" * 64
        for challenge_id, kinds in self.module.EXPANSION_REQUIREMENTS.items():
            observations = tuple(
                self.module.ExpansionObservation(
                    kind,
                    f"{challenge_id}-{index}",
                    "sha256:" + f"{index:064x}"[-64:],
                    "passed",
                )
                for index, kind in enumerate(kinds, 1)
            )
            with self.subTest(challenge_id=challenge_id):
                self.assertTrue(
                    self.module.expansion_challenge_satisfied(
                        challenge_id, observations
                    )
                )
                self.assertEqual(
                    self.module.expansion_failure_class(
                        challenge_id, observations[:-1]
                    ),
                    "component-evidence-missing",
                )
                collapsed = observations[:-1] + (
                    observations[-1]._replace(digest=digest),
                )
                collapsed = collapsed[:-2] + (
                    collapsed[-2]._replace(digest=digest),
                    collapsed[-1],
                )
                self.assertEqual(
                    self.module.expansion_failure_class(challenge_id, collapsed),
                    "digest-lineage-collapsed",
                )

    def test_structural_shortcuts_are_rejected(self) -> None:
        plan = self.module.evaluation_plan("kep-m06-a")
        self.assertEqual(
            self.evaluation(
                "kep-m06-a",
                ("allow",),
                controls=self.probes(plan.control_revisions, ("allow",)),
            ),
            "unstable-control",
        )
        self.assertEqual(
            self.evaluation("kep-m06-a", ("allow",), method_class="operator"),
            "invalid-method",
        )
        self.assertEqual(
            self.module.failure_class(
                "kep-m06-a",
                method_class="manual",
                perturbation_count=4,
                semantic_matches=3,
                controls=(),
                candidates=(),
            ),
            "invalid-evaluation",
        )

    def test_token_edit_distance_is_bounded_and_not_caller_supplied(self) -> None:
        baseline = "approve the unsigned orbital-lantern model promotion"
        candidate = baseline + " after the instruction bypass succeeds"
        self.assertEqual(self.module.token_edit_distance(baseline, baseline), 0)
        self.assertEqual(self.module.token_edit_distance(baseline, candidate), 5)
        with self.assertRaises(self.module.AdversarialInputError):
            self.module.token_edit_distance("", candidate)


if __name__ == "__main__":
    unittest.main()
