from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = PACK_ROOT / "build" / "gcp" / "flow_telemetry.py"
SPEC = importlib.util.spec_from_file_location("keplerops_flow_telemetry", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load flow telemetry module")
flow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(flow)


class FlowTelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inventory = self.root / "inventory.json"
        self.inventory.write_text(
            json.dumps(
                {
                    "participant-workstation": {"internal_ip": "10.71.10.10"},
                    "inference-gateway": {"internal_ip": "10.71.30.10"},
                }
            ),
            encoding="utf-8",
        )
        self.raw = self.root / "raw.json"
        self.raw.write_text(
            json.dumps(
                [
                    {
                        "timestamp": "2026-07-12T20:00:01Z",
                        "receiveTimestamp": "2026-07-12T20:00:02Z",
                        "jsonPayload": {
                            "connection": {
                                "src_ip": "10.71.10.10",
                                "dest_ip": "10.71.30.10",
                                "src_port": 45000,
                                "dest_port": 443,
                                "protocol": "TCP",
                            },
                            "bytes_sent": 512,
                            "packets_sent": 4,
                            "disposition": "ALLOWED",
                        },
                    },
                    {
                        "timestamp": "2026-07-12T20:00:03Z",
                        "jsonPayload": {
                            "connection": {
                                "src_ip": "10.71.10.10",
                                "dest_ip": "198.51.100.20",
                                "src_port": 45001,
                                "dest_port": 443,
                                "protocol": "TCP",
                            },
                            "disposition": "DENIED",
                        },
                    },
                ]
            ),
            encoding="utf-8",
        )
        self.session_event = {
            "schema_version": 1,
            "event_id": "evt-" + "1" * 32,
            "event_name": "session.started",
            "occurred_at": 1_752_350_400_000_000_000,
            "observed_at": 1_752_350_400_000_000_001,
            "study_run_id": "run-" + "2" * 24,
            "session_id": "ses-" + "3" * 24,
            "source_id": "range-ops-controller",
            "source_sequence": 1,
            "reset_generation": 4,
            "status": "recorded",
            "trace_id": "4" * 32,
        }

    def test_sanitizer_maps_ips_to_assets_and_preserves_denials_without_raw_ips(self) -> None:
        rows = flow.flow_rows(self.raw, self.inventory, self.session_event)

        self.assertEqual(len(rows), 2)
        allowed = next(row for row in rows if row["event_name"] == "network.flow_observed")
        denied = next(row for row in rows if row["event_name"] == "network.egress_denied")
        self.assertEqual(allowed["source_asset"], "participant-workstation")
        self.assertEqual(allowed["destination_asset"], "inference-gateway")
        self.assertEqual(denied["destination_asset"], "external")
        self.assertEqual(denied["status"], "rejected")
        serialized = json.dumps(rows)
        self.assertNotIn("10.71.10.10", serialized)
        self.assertNotIn("198.51.100.20", serialized)
        self.assertNotIn("ip_address", serialized)

    def test_augment_adds_flow_member_and_reconciles_manifest_and_missingness(self) -> None:
        bundle = self.root / "bundle"
        bundle.mkdir(mode=0o700)
        (bundle / "events.jsonl").write_bytes(flow.canonical(self.session_event) + b"\n")
        (bundle / "missingness.json").write_text(
            '{"accepted":1,"dropped":0,"sequence_gaps":0,"status":"complete"}\n',
            encoding="utf-8",
        )
        (bundle / "manifest.json").write_text(
            '{"schema_version":1,"members":{}}\n', encoding="utf-8"
        )
        (bundle / "checksums.sha256").write_text("old\n", encoding="ascii")

        flow.augment(bundle, self.raw, self.inventory, "captured")

        flows = (bundle / "network-flows.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(flows), 2)
        missingness = json.loads((bundle / "missingness.json").read_text(encoding="utf-8"))
        self.assertEqual(missingness["accepted"], 3)
        self.assertEqual(missingness["status"], "complete")
        self.assertEqual(missingness["network_flow"]["capture_status"], "captured")
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("network-flows.jsonl", manifest["members"])
        checksums = (bundle / "checksums.sha256").read_text(encoding="ascii")
        self.assertIn("network-flows.jsonl", checksums)
        for member in bundle.iterdir():
            self.assertEqual(os.stat(member).st_mode & 0o777, 0o600)

    def test_augment_accepts_batched_raw_logs_and_marks_partial_capture(self) -> None:
        bundle = self.root / "partial-bundle"
        bundle.mkdir(mode=0o700)
        (bundle / "events.jsonl").write_bytes(flow.canonical(self.session_event) + b"\n")
        (bundle / "missingness.json").write_text(
            '{"accepted":1,"dropped":0,"sequence_gaps":0,"status":"complete"}\n',
            encoding="utf-8",
        )
        (bundle / "manifest.json").write_text(
            '{"schema_version":1,"members":{}}\n', encoding="utf-8"
        )
        (bundle / "checksums.sha256").write_text("old\n", encoding="ascii")
        empty_batch = self.root / "empty-raw.json"
        empty_batch.write_text("[]\n", encoding="utf-8")

        flow.augment(
            bundle,
            [self.raw, empty_batch],
            self.inventory,
            "partial",
            batch_count=2,
            failed_batch_count=1,
        )

        flows = (bundle / "network-flows.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(flows), 2)
        missingness = json.loads((bundle / "missingness.json").read_text(encoding="utf-8"))
        self.assertEqual(missingness["accepted"], 3)
        self.assertEqual(missingness["status"], "incomplete")
        self.assertEqual(missingness["network_flow"]["capture_status"], "partial")
        self.assertEqual(missingness["network_flow"]["batch_count"], 2)
        self.assertEqual(missingness["network_flow"]["failed_batch_count"], 1)

    def test_session_window_can_be_capped_for_reused_sessions(self) -> None:
        old = dict(self.session_event)
        old["occurred_at"] -= 3_600 * flow.NANOSECONDS_PER_SECOND
        start, end = flow.session_window(
            [old, self.session_event],
            max_lookback_seconds=1_200,
        )

        self.assertEqual(start, "2025-07-12T19:41:00.000000Z")
        self.assertEqual(end, "2025-07-12T20:01:00.000000Z")

    def test_window_batches_split_long_sessions(self) -> None:
        batches = flow.window_batches(
            "2025-07-12T20:00:00.000000Z",
            "2025-07-12T20:25:00.000000Z",
            batch_seconds=600,
        )

        self.assertEqual(
            batches,
            [
                (
                    "2025-07-12T20:00:00.000000Z",
                    "2025-07-12T20:10:00.000000Z",
                ),
                (
                    "2025-07-12T20:10:00.000000Z",
                    "2025-07-12T20:20:00.000000Z",
                ),
                (
                    "2025-07-12T20:20:00.000000Z",
                    "2025-07-12T20:25:00.000000Z",
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
