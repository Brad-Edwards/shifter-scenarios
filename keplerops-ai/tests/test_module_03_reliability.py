from __future__ import annotations

import importlib.util
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
SPEC = importlib.util.spec_from_file_location(
    "module_03_reliability_under_test", TESTS_ROOT / "module_03_reliability.py"
)
RELIABILITY = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = RELIABILITY
SPEC.loader.exec_module(RELIABILITY)


class FakeLifecycle:
    def __init__(self) -> None:
        self.health_calls = 0
        self.reset_calls = 0
        self.context_reset_calls = 0
        self.events = []

    def health(self) -> None:
        self.health_calls += 1
        self.events.append("health")

    def reset(self) -> None:
        self.reset_calls += 1
        self.events.append("reset")

    def reset_context_state(self) -> None:
        self.context_reset_calls += 1
        self.events.append("context-reset")


class FakeSession:
    def __init__(self, model_counts: dict[str, int] | None = None) -> None:
        self.model_counts = model_counts or {suffix: 29 for suffix in "cdef"}

    def execute(self, program, *, expected_markers, return_clipboard):
        suffixes = "cdef" if 'challenge_ids = ["kep-m03-c"' in program else "ab"
        rows = tuple(
            SimpleNamespace(
                check_id=f"test-context-reliability-{suffix}",
                safe_count=(1 if suffix in "ab" else self.model_counts[suffix]),
            )
            for suffix in suffixes
        )
        return rows, ""


class Module03ReliabilityTests(unittest.TestCase):
    def test_participant_program_is_bounded_and_uses_real_context_path(self):
        program = RELIABILITY.participant_program(RELIABILITY.MODEL_SENSITIVE, 30)
        for endpoint in (
            "/v1/context/documents",
            "/v1/context/search",
            "/v1/context/reindex",
            "/v1/context/attempt",
        ):
            self.assertIn(endpoint, program)
        self.assertIn('"kep-m03-f"', program)
        self.assertIn('for prerequisite in ("kep-m03-a", "kep-m03-b"):', program)
        for forbidden in ("gcloud", "terraform", "psql", "/v1/evidence"):
            self.assertNotIn(forbidden, program)
        self.assertLess(len(program.encode()), 96_000)

    def test_runner_enforces_clean_samples_and_model_thresholds(self):
        lifecycle = FakeLifecycle()
        results = RELIABILITY.ReliabilityRunner(lifecycle, FakeSession()).run()
        self.assertEqual(lifecycle.health_calls, 0)
        self.assertEqual(lifecycle.reset_calls, 1)
        self.assertEqual(lifecycle.context_reset_calls, 10)
        self.assertEqual({row.challenge_id for row in results}, set(RELIABILITY.CHALLENGES))
        self.assertTrue(all(row.passed for row in results))
        self.assertEqual(
            {row.challenge_id: row.trials for row in results},
            {
                **{challenge_id: 10 for challenge_id in RELIABILITY.DETERMINISTIC},
                **{challenge_id: 30 for challenge_id in RELIABILITY.MODEL_SENSITIVE},
            },
        )

    def test_runner_can_prepare_lifecycle_before_opening_the_session(self):
        lifecycle = FakeLifecycle()
        runner = RELIABILITY.ReliabilityRunner(lifecycle, FakeSession())
        progress = runner.prepare()
        self.assertEqual(lifecycle.reset_calls, 1)
        self.assertEqual(lifecycle.health_calls, 0)

        results = runner.run(progress)

        self.assertEqual(lifecycle.reset_calls, 1)
        self.assertEqual(lifecycle.health_calls, 0)
        self.assertEqual(lifecycle.context_reset_calls, 10)
        self.assertTrue(all(row.passed for row in results))

    def test_checkpoint_resume_repairs_scoped_state_before_health(self):
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint = RELIABILITY.ReliabilityCheckpoint(
                Path(temporary) / "module-03.checkpoint.json", "a" * 64
            )
            checkpoint.write(RELIABILITY.ReliabilityProgress(
                1,
                {
                    challenge_id: (
                        1 if challenge_id in RELIABILITY.DETERMINISTIC else 0
                    )
                    for challenge_id in RELIABILITY.CHALLENGES
                },
                False,
            ))
            lifecycle = FakeLifecycle()

            progress = RELIABILITY.ReliabilityRunner(
                lifecycle, FakeSession(), checkpoint
            ).prepare()

            self.assertEqual(progress.deterministic_rounds, 1)
            self.assertEqual(lifecycle.events, ["context-reset", "health"])

    def test_model_sensitive_path_below_ninety_percent_fails(self):
        results = RELIABILITY.ReliabilityRunner(
            FakeLifecycle(), FakeSession({"c": 30, "d": 26, "e": 30, "f": 30})
        ).run()
        self.assertEqual(
            [row.challenge_id for row in results if not row.passed], ["kep-m03-d"]
        )

    def test_owner_only_checkpoint_resumes_completed_deterministic_rounds(self):
        class InterruptedLifecycle(FakeLifecycle):
            def reset_context_state(self):
                super().reset_context_state()
                if self.context_reset_calls == 3:
                    raise RELIABILITY.RehearsalError("operator auth expired")

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "module-03.checkpoint.json"
            checkpoint = RELIABILITY.ReliabilityCheckpoint(path, "a" * 64)
            with self.assertRaisesRegex(
                RELIABILITY.RehearsalError, "operator auth expired"
            ):
                RELIABILITY.ReliabilityRunner(
                    InterruptedLifecycle(), FakeSession(), checkpoint
                ).run()
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["deterministic_rounds"], 3)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

            resumed_lifecycle = FakeLifecycle()
            results = RELIABILITY.ReliabilityRunner(
                resumed_lifecycle, FakeSession(), checkpoint
            ).run()
            self.assertEqual(resumed_lifecycle.reset_calls, 0)
            self.assertEqual(resumed_lifecycle.context_reset_calls, 8)
            self.assertEqual(resumed_lifecycle.health_calls, 1)
            self.assertTrue(all(row.passed for row in results))

    def test_scoped_reset_targets_the_context_state_dependency_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            build_root = Path(temporary)
            operator_root = build_root / ".operator" / "range-a-operator"
            operator_root.mkdir(parents=True)
            (operator_root / "terraform.tfstate").write_text("{}", encoding="utf-8")
            state = operator_root / "state.json"
            state.write_text('{"reset_generation":19}', encoding="utf-8")
            state.chmod(0o600)
            calls = []

            def invoke(arguments, **kwargs):
                calls.append((arguments, kwargs))
                if arguments[-1] == "asset_inventory":
                    return SimpleNamespace(
                        returncode=0,
                        stdout=json.dumps({
                            "dataset-store-01": {"name": "range-a-dataset-store"},
                            "inference-gateway": {"name": "range-a-gateway"},
                            "telemetry-proof-01": {"name": "range-a-proof"},
                        }),
                    )
                return SimpleNamespace(returncode=0)

            config = SimpleNamespace(
                project_id="project-a",
                zone="europe-west4-a",
                range_instance="range-a",
                participant="operator",
            )
            lifecycle = RELIABILITY.ContextReliabilityLifecycle(
                build_root, config, invoke
            )
            with mock.patch.object(
                RELIABILITY.shutil,
                "which",
                side_effect=lambda name: f"/usr/bin/{name}",
            ):
                lifecycle.reset_context_state()

            self.assertEqual(len(calls), 7)
            self.assertEqual(calls[0][0][-1], "asset_inventory")
            commands = calls[1:]
            self.assertEqual(
                [arguments[-1] for arguments, _ in commands],
                [
                    "sudo bash /var/lib/keplerops/quiesce-local",
                    "sudo bash /var/lib/keplerops/quiesce-local",
                    "sudo bash /var/lib/keplerops/reset-local 19",
                    "sudo bash /var/lib/keplerops/reset-local 19",
                    "sudo bash /var/lib/keplerops/reset-verify-local",
                    "sudo bash /var/lib/keplerops/reset-verify-local",
                ],
            )
            self.assertEqual(
                [arguments[3] for arguments, _ in commands],
                [
                    "range-a-gateway",
                    "range-a-dataset-store",
                    "range-a-dataset-store",
                    "range-a-gateway",
                    "range-a-dataset-store",
                    "range-a-gateway",
                ],
            )
            self.assertTrue(
                all("range-a-proof" not in arguments for arguments, _ in commands)
            )

    def test_scoped_reset_rejects_an_unsafe_inventory_instance(self):
        with tempfile.TemporaryDirectory() as temporary:
            build_root = Path(temporary)
            operator_root = build_root / ".operator" / "range-a-operator"
            operator_root.mkdir(parents=True)
            (operator_root / "terraform.tfstate").write_text("{}", encoding="utf-8")
            calls = []

            def invoke(arguments, **kwargs):
                calls.append((arguments, kwargs))
                return SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps({
                        "dataset-store-01": {"name": "-unsafe"},
                        "inference-gateway": {"name": "range-a-gateway"},
                    }),
                )

            config = SimpleNamespace(
                project_id="project-a",
                zone="europe-west4-a",
                range_instance="range-a",
                participant="operator",
            )
            lifecycle = RELIABILITY.ContextReliabilityLifecycle(
                build_root, config, invoke
            )
            with mock.patch.object(
                RELIABILITY.shutil,
                "which",
                side_effect=lambda name: f"/usr/bin/{name}",
            ):
                with self.assertRaisesRegex(
                    RELIABILITY.RehearsalError, "scoped reset is unavailable"
                ):
                    lifecycle.reset_context_state()
            self.assertEqual(len(calls), 1)

    def test_checkpoint_fails_closed_for_wrong_binding_or_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "module-03.checkpoint.json"
            checkpoint = RELIABILITY.ReliabilityCheckpoint(path, "a" * 64)
            checkpoint.write(RELIABILITY.ReliabilityProgress(
                1,
                {
                    challenge_id: 1 if challenge_id in RELIABILITY.DETERMINISTIC else 0
                    for challenge_id in RELIABILITY.CHALLENGES
                },
                False,
            ))
            with self.assertRaisesRegex(RELIABILITY.RehearsalError, "checkpoint is invalid"):
                RELIABILITY.ReliabilityCheckpoint(path, "b" * 64).load()
            path.chmod(0o644)
            with self.assertRaisesRegex(RELIABILITY.RehearsalError, "checkpoint is invalid"):
                checkpoint.load()

    def test_checkpoint_binding_includes_runtime_and_lifecycle_sources(self):
        source = (TESTS_ROOT / "module_03_reliability.py").read_text(encoding="utf-8")
        for path in (
            'PACK_ROOT / "assets/services/keplerops-runtime/app.py"',
            'PACK_ROOT / "assets/services/keplerops-runtime/agent_control.py"',
            'PACK_ROOT / "assets/services/keplerops-runtime/context_poisoning.py"',
            'BUILD_ROOT / "reset.sh"',
            'BUILD_ROOT / "health-check.sh"',
            'BUILD_ROOT / "gcp/lifecycle.py"',
            'lifecycle.operator_root / "terraform.tfstate"',
        ):
            self.assertIn(path, source)

        with tempfile.TemporaryDirectory(dir=RELIABILITY.BUILD_ROOT) as temporary:
            root = Path(temporary)
            state = root / "terraform.tfstate"
            state.write_text("first", encoding="utf-8")
            lifecycle = SimpleNamespace(operator_root=root)
            config = SimpleNamespace(range_instance="range-a", participant="operator")
            first = RELIABILITY._checkpoint_binding(config, lifecycle)
            state.write_text("second", encoding="utf-8")
            second = RELIABILITY._checkpoint_binding(config, lifecycle)
            self.assertNotEqual(first, second)

    def test_report_is_owner_only_and_contains_no_participant_content(self):
        results = RELIABILITY.ReliabilityRunner(FakeLifecycle(), FakeSession()).run()
        config = SimpleNamespace(range_instance="kep-408-r1", participant="operator")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "module-03.json"
            RELIABILITY._write_report(destination, config, results)
            payload = json.loads(destination.read_text(encoding="utf-8"))
            serialized = destination.read_text(encoding="utf-8").lower()
            self.assertEqual(payload["verdict"], "PASS")
            self.assertEqual(payload["module"], "module-03-context-poisoning")
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            self.assertNotIn("prompt", serialized)
            self.assertNotIn("document_content", serialized)


if __name__ == "__main__":
    unittest.main()
