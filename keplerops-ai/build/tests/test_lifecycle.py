from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE_PATH = PACK_ROOT / "build" / "gcp" / "lifecycle.py"


def load_lifecycle():
    spec = importlib.util.spec_from_file_location("keplerops_lifecycle", LIFECYCLE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load lifecycle module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LifecycleTests(unittest.TestCase):
    def test_namespace_validation_rejects_shell_and_provider_ambiguity(self) -> None:
        lifecycle = load_lifecycle()
        for value in ("", "Upper", "two words", "quote'", "../escape", "a" * 33):
            with self.subTest(value=value):
                with self.assertRaises(lifecycle.LifecycleError):
                    lifecycle.validate_namespace(value, "range_instance")
        self.assertEqual(lifecycle.validate_namespace("range-355-a1", "range_instance"), "range-355-a1")

    def test_reset_state_machine_is_fail_closed(self) -> None:
        lifecycle = load_lifecycle()
        state = lifecycle.RangeState.initial("range-355-a1", "participant-01")
        resetting = state.begin_reset()
        self.assertEqual(resetting.status, "resetting")
        self.assertFalse(resetting.participant_writes_enabled)
        self.assertFalse(resetting.receipts_enabled)
        self.assertEqual(resetting.reset_generation, 1)
        negative = {
            "schema_version": 1,
            "status": "passed",
            "reset_generation": 1,
            "completed_owners": sorted(resetting.pending_owners),
            "checks": [
                "agent_state_clean",
                "context_empty",
                "proof_empty",
                "runtime_gate_ready",
                "windows_domain_readback",
            ],
            "telemetry_markers": "complete",
            "windows_readback": {
                host: {
                    "domain": lifecycle.WINDOWS_DOMAIN,
                    "role": lifecycle.WINDOWS_RESET_ROLES[host],
                    "status": "ready",
                }
                for host in lifecycle.WINDOWS_RESET_OWNERS
            },
        }
        health = {
            "schema_version": 2,
            "status": "ready",
            "host_count": 7,
            "logical_workload_count": 28,
            "range_workload_count": 27,
            "service_count": 27,
            "windows_hosts_ready": 3,
        }
        with self.assertRaises(lifecycle.LifecycleError):
            resetting.finish_reset([], negative_gate_report=negative, health_report=health)
        with self.assertRaises(lifecycle.LifecycleError):
            resetting.finish_reset(resetting.pending_owners, negative_gate_report={}, health_report=health)

        ready = resetting.finish_reset(
            resetting.pending_owners,
            negative_gate_report=negative,
            health_report=health,
        )
        self.assertEqual(ready.status, "ready")
        self.assertTrue(ready.participant_writes_enabled)
        self.assertTrue(ready.receipts_enabled)

        with self.assertRaises(lifecycle.LifecycleError):
            resetting.finish_reset(
                resetting.pending_owners,
                negative_gate_report=negative,
                health_report={**health, "service_count": 26},
            )

    def test_windows_hosts_are_explicit_reset_owners(self) -> None:
        lifecycle = load_lifecycle()

        self.assertEqual(
            lifecycle.WINDOWS_RESET_OWNERS,
            ("ad-dc-01", "workforce-workstation-01", "ml-workstation-01"),
        )
        self.assertEqual(
            set(lifecycle.RESET_OWNERS),
            set(lifecycle.WORKLOAD_RESET_OWNERS)
            | set(lifecycle.WINDOWS_RESET_OWNERS),
        )

        state = lifecycle.RangeState.initial("range-555-a1", "participant-01")
        resetting = state.begin_reset()
        self.assertTrue(
            set(lifecycle.WINDOWS_RESET_OWNERS) <= set(resetting.pending_owners)
        )

    def test_state_file_rejects_symlinks_and_non_owner_permissions(self) -> None:
        lifecycle = load_lifecycle()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_path = root / "state.json"
            state_path.write_text("{}", encoding="utf-8")
            state_path.chmod(0o644)
            with self.assertRaises(lifecycle.LifecycleError):
                lifecycle.require_owner_file(state_path)

            target = root / "target.json"
            target.write_text("{}", encoding="utf-8")
            target.chmod(0o600)
            state_path.unlink()
            state_path.symlink_to(target)
            with self.assertRaises(lifecycle.LifecycleError):
                lifecycle.require_owner_file(state_path)


if __name__ == "__main__":
    unittest.main()
