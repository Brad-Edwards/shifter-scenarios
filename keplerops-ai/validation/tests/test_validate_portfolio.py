"""Mutation tests for the SDL-owned KeplerOps challenge portfolio."""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = PACK_ROOT / "validation" / "validate_portfolio.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("keplerops_validate_portfolio_test", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


class PortfolioValidationTests(unittest.TestCase):
    def _copy_pack(self) -> Path:
        temporary = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temporary)
        target = temporary / "keplerops-ai"
        shutil.copytree(PACK_ROOT, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        return target

    def _mutate_module(self, root: Path, module: str, mutate) -> list[str]:
        path = root / "sdl" / "modules" / module
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return VALIDATOR.validate_pack(str(root))

    def _mutate_policy(self, root: Path, mutate) -> list[str]:
        path = root / "sdl" / "modules" / "environment.sdl.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        policy = yaml.safe_load(data["content"]["portfolio-policy"]["text"])
        mutate(policy)
        data["content"]["portfolio-policy"]["text"] = yaml.safe_dump(policy, sort_keys=False)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return VALIDATOR.validate_pack(str(root))

    def _mutate_experiment_task(self, root: Path, mutate) -> list[str]:
        path = root / "experiments" / "ctf-evaluation-task.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return VALIDATOR.validate_pack(str(root))

    def assertFailureContains(self, failures: list[str], needle: str) -> None:
        self.assertTrue(any(needle in failure for failure in failures), failures)

    def test_canonical_portfolio_passes(self) -> None:
        self.assertEqual(VALIDATOR.validate_pack(str(PACK_ROOT)), [])

    def test_rejects_missing_challenge_behavior(self) -> None:
        root = self._copy_pack()

        def mutate(data) -> None:
            data["behavior_specifications"].pop("kep-m01-a")
            data["module"]["exports"]["behavior_specifications"].remove("kep-m01-a")

        failures = self._mutate_module(root, "module-01-agent-control.sdl.yaml", mutate)
        self.assertFailureContains(failures, "portfolio must contain 134 challenges")

    def test_rejects_difficulty_point_drift(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_module(
            root,
            "module-01-agent-control.sdl.yaml",
            lambda data: data["behavior_specifications"]["kep-m01-a"]["extensions"]
            ["x-keplerops:challenge"].update({"points": 100}),
        )
        self.assertFailureContains(failures, "difficulty, points, or hint-cost drift")

    def test_rejects_missing_prerequisite(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_module(
            root,
            "module-05-agent-persistence.sdl.yaml",
            lambda data: data["behavior_specifications"]["kep-m05-b"]["extensions"]
            ["x-keplerops:challenge"].update({"prerequisites": ["kep-m99-z"]}),
        )
        self.assertFailureContains(failures, "missing prerequisite kep-m99-z")

    def test_rejects_missing_walkthrough_evidence(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_module(
            root,
            "module-05-agent-persistence.sdl.yaml",
            lambda data: data["behavior_specifications"]["kep-m05-a"]["extensions"]
            ["x-keplerops:challenge"]["implementation_evidence"].update(
                {"manual_walkthrough": "docs/walkthroughs/missing.md"}
            ),
        )
        self.assertFailureContains(failures, "contained manual walkthrough required")

    def test_rejects_native_objective_truth_drift(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_module(
            root,
            "module-01-agent-control.sdl.yaml",
            lambda data: data["conditions"]["kep-m01-a-complete"].update(
                {"proposition": "kep-m01-b-satisfied"}
            ),
        )
        self.assertFailureContains(failures, "native ACES objective truth binding drift")

    def test_rejects_experiment_task_metric_drift(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_experiment_task(
            root,
            lambda data: data["evaluation_protocol"]["metric_definitions"][
                "ctf-score"
            ].update({"value_kind": "boolean"}),
        )
        self.assertFailureContains(failures, "evaluation task metric contract drift")

    def test_rejects_event_window_drift(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_policy(
            root, lambda policy: policy.update({"event_window_minutes": 240})
        )
        self.assertFailureContains(
            failures, "content.core.portfolio-policy.event_window_minutes: expected 480"
        )


if __name__ == "__main__":
    unittest.main()
