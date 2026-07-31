from __future__ import annotations

import json
import os
import queue
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins"
sys.path.insert(0, str(PLUGIN_ROOT))
try:
    import keplerops_oracle_flags as plugin
finally:
    del sys.path[0]


class OraclePluginTelemetryTests(unittest.TestCase):
    def test_ctfd_event_is_content_free_generation_bound_and_sequenced(self) -> None:
        binding = {
            "range_instance": "kep-405-a1",
            "participant": "operator",
            "reset_generation": 3,
        }
        contract = {"challenge_id": "kep-m02-a", "outcome": "model-evasion"}
        with tempfile.TemporaryDirectory() as directory:
            sequence = Path(directory) / "sequence"
            with patch.dict(
                os.environ,
                {"KEPLEROPS_CTFD_TELEMETRY_SEQUENCE_FILE": str(sequence)},
                clear=False,
            ):
                first = plugin._telemetry_payload(
                    binding, contract, "objective.attempted", "rejected", "a" * 32
                )
                second = plugin._telemetry_payload(
                    binding, contract, "objective.satisfied", "passed", "a" * 32
                )
                sequence_mode = os.stat(sequence).st_mode & 0o777

        self.assertEqual(first["event"]["source_sequence"], 1)
        self.assertEqual(second["event"]["source_sequence"], 2)
        self.assertEqual(first["event"]["module_id"], "module-02-model-evasion")
        self.assertEqual(first["event"]["challenge_id"], "kep-m02-a")
        self.assertEqual(first["event"]["dropped_event_count"], 0)
        self.assertEqual(first["event"]["participant_interface"], "ctfd")
        self.assertEqual(first["reset_generation"], 3)
        serialized = json.dumps([first, second])
        for forbidden in ("receipt", "flag", "prompt", "completion", "hint_content"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(sequence_mode, 0o600)

    def test_ctfd_hint_event_carries_tier_and_cost_without_content(self) -> None:
        binding = {
            "range_instance": "kep-405-a1",
            "participant": "operator",
            "reset_generation": 3,
        }
        contract = {"challenge_id": "kep-m03-a", "outcome": "context-poisoning"}
        with tempfile.TemporaryDirectory() as directory:
            sequence = Path(directory) / "sequence"
            with patch.dict(
                os.environ,
                {"KEPLEROPS_CTFD_TELEMETRY_SEQUENCE_FILE": str(sequence)},
                clear=False,
            ):
                payload = plugin._telemetry_payload(
                    binding,
                    contract,
                    "hint.viewed",
                    "recorded",
                    "b" * 32,
                    hint_cost=25,
                    hint_tier=2,
                )

        self.assertEqual(payload["event"]["hint_cost"], 25)
        self.assertEqual(payload["event"]["hint_tier"], 2)
        serialized = json.dumps(payload)
        self.assertNotIn("hint text", serialized)
        self.assertNotIn("content", serialized)

    def test_rejected_receipt_event_carries_only_failure_class(self) -> None:
        binding = {
            "range_instance": "kep-405-a1",
            "participant": "operator",
            "reset_generation": 3,
        }
        contract = {"challenge_id": "kep-m02-a", "outcome": "model-evasion"}
        with tempfile.TemporaryDirectory() as directory:
            sequence = Path(directory) / "sequence"
            with patch.dict(
                os.environ,
                {"KEPLEROPS_CTFD_TELEMETRY_SEQUENCE_FILE": str(sequence)},
                clear=False,
            ):
                payload = plugin._telemetry_payload(
                    binding,
                    contract,
                    "receipt.stale_rejected",
                    "rejected",
                    "b" * 32,
                    failure_class=plugin.STATUS_STALE_RESET_GENERATION,
                )

        self.assertEqual(
            payload["event"]["failure_class"],
            plugin.STATUS_STALE_RESET_GENERATION,
        )
        serialized = json.dumps(payload)
        self.assertNotIn("PENR1", serialized)
        self.assertNotIn("signature", serialized)

    def test_plugin_declares_required_portfolio_event_names(self) -> None:
        source = (PLUGIN_ROOT / "keplerops_oracle_flags" / "__init__.py").read_text(
            encoding="utf-8"
        )

        for event_name in (
            "challenge.presented",
            "challenge.started",
            "attempt.started",
            "attempt.completed",
            "hint.viewed",
            "hint.unlocked",
            "flag.submitted",
            "challenge.solved",
            "dependency.unlocked",
            "dependency.blocked",
            "receipt.stale_rejected",
        ):
            self.assertIn(event_name, source)

    def test_queue_overflow_is_fail_open_and_reported_on_later_events(self) -> None:
        binding = {
            "range_instance": "kep-405-a1",
            "participant": "operator",
            "reset_generation": 3,
        }
        contract = {"challenge_id": "kep-m02-a", "outcome": "model-evasion"}
        original_queue = plugin.TELEMETRY_QUEUE
        original_dropped = plugin.TELEMETRY_DROPPED
        plugin.TELEMETRY_QUEUE = queue.Queue(maxsize=1)
        plugin.TELEMETRY_DROPPED = 0
        self.addCleanup(setattr, plugin, "TELEMETRY_QUEUE", original_queue)
        self.addCleanup(setattr, plugin, "TELEMETRY_DROPPED", original_dropped)
        with tempfile.TemporaryDirectory() as directory:
            sequence = Path(directory) / "sequence"
            with patch.dict(
                os.environ,
                {
                    "KEPLEROPS_CTFD_RESEARCH_URL": "https://telemetry.invalid",
                    "KEPLEROPS_CTFD_TELEMETRY_SEQUENCE_FILE": str(sequence),
                },
                clear=False,
            ):
                plugin._enqueue_telemetry(
                    binding, contract, "attempt.started", "recorded", "c" * 32
                )
                plugin._enqueue_telemetry(
                    binding, contract, "attempt.completed", "rejected", "c" * 32
                )
                plugin.TELEMETRY_QUEUE.get_nowait()
                plugin.TELEMETRY_QUEUE.task_done()
                plugin._enqueue_telemetry(
                    binding, contract, "flag.submitted", "recorded", "c" * 32
                )

        reported = plugin.TELEMETRY_QUEUE.get_nowait()
        self.assertEqual(plugin._telemetry_drop_count(), 1)
        self.assertEqual(reported["event"]["source_sequence"], 3)
        self.assertEqual(reported["event"]["dropped_event_count"], 1)


if __name__ == "__main__":
    unittest.main()
