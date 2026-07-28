from __future__ import annotations

import importlib.util
import sys
import unittest
from types import SimpleNamespace
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = PACK_ROOT / "tests"
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))


def load_module(module_name: str):
    path = TESTS_ROOT / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"keplerops_{module_name}", path
    )
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Module08And09FullAtlasRehearsalTests(unittest.TestCase):
    def test_controls_tolerate_already_satisfied_prepared_receipts(self) -> None:
        for module_name in (
            "module_08_full_atlas_rehearsal",
            "module_09_full_atlas_rehearsal",
        ):
            with self.subTest(module=module_name):
                module = load_module(module_name)
                controls_program = module.participant_programs()[0]

                self.assertIn("expected=(200, 409)", controls_program)

    def test_module08_reuses_participant_base_progress_for_prerequisites(self) -> None:
        module = load_module("module_08_full_atlas_rehearsal")
        proxy_program = module.participant_programs()[1]

        self.assertIn(".keplerops-module08-progress.json", proxy_program)
        self.assertIn("def reusable_base_corpus(challenge_id):", proxy_program)
        self.assertIn("def reusable_base_job(challenge_id, data):", proxy_program)
        self.assertIn('if challenge_id not in {"kep-m08-a", "kep-m08-c"}:', proxy_program)
        self.assertIn('if challenge_id != "kep-m08-c":', proxy_program)
        self.assertIn('if reused is not None and reused[1].get("status") == "succeeded":', proxy_program)
        self.assertIn('corpus("kep-m08-g", strict_prompts)', proxy_program)

    def test_module09_discards_stale_candidate_state_after_reset(self) -> None:
        module = load_module("module_09_full_atlas_rehearsal")
        candidate_program = module.participant_programs()[1]

        self.assertIn("attempt(\"kep-m09-a\", state[\"candidate_id\"])", candidate_program)
        self.assertIn("if \"status=404\" not in str(error):", candidate_program)
        self.assertIn("state_path.unlink(missing_ok=True)", candidate_program)
        self.assertLess(
            candidate_program.index("state_path.unlink(missing_ok=True)"),
            candidate_program.index("data, job, prereq_ok = training_prerequisite()"),
        )

    def test_prepared_runs_can_skip_redundant_health_check(self) -> None:
        cases = (
            (
                "module_08_full_atlas_rehearsal",
                {
                    "test-m08-fa-controls": "NEGATIVE_COUNT",
                    "test-m08-fa-proxy": 3,
                    "test-m08-fa-platform": 3,
                    "test-m08-fa-physical": 1,
                    "test-m08-fa-awards": "CHALLENGES",
                },
            ),
            (
                "module_09_full_atlas_rehearsal",
                {
                    "test-m09-fa-controls": "NEGATIVE_COUNT",
                    "test-m09-fa-candidate": 1,
                    "test-m09-fa-reputation": 2,
                    "test-m09-fa-rugpull": 1,
                    "test-m09-fa-toolcorrupt": 2,
                    "test-m09-fa-awards": "CHALLENGES",
                },
            ),
        )
        for module_name, markers in cases:
            with self.subTest(module=module_name):
                module = load_module(module_name)
                rows = [
                    SimpleNamespace(
                        check_id=check_id,
                        status="PASS",
                        safe_count=(
                            getattr(module, count)
                            if count == "NEGATIVE_COUNT"
                            else len(module.CHALLENGES)
                            if count == "CHALLENGES"
                            else count
                        ),
                    )
                    for check_id, count in markers.items()
                ]
                lifecycle = SimpleNamespace(
                    reset=lambda: (_ for _ in ()).throw(AssertionError("reset")),
                    health=lambda: (_ for _ in ()).throw(AssertionError("health")),
                )
                session = _ScriptedSession(rows)
                runner_type = getattr(
                    module, f"Module{module_name[7:9]}FullAtlasRunner"
                )

                result = runner_type(
                    lifecycle,
                    session,
                    reset_before_run=False,
                    skip_health_check=True,
                ).run()

                self.assertTrue(result.passed)


class _ScriptedSession:
    def __init__(self, rows):
        self.rows = list(rows)

    def __enter__(self):
        return self

    def __exit__(self, type_, value, traceback):
        return None

    def execute(self, program, *, expected_markers, return_clipboard):
        return ((self.rows.pop(0),), "")


if __name__ == "__main__":
    unittest.main()
