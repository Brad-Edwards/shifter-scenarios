from __future__ import annotations

import importlib.util
import base64
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PACK_ROOT / "assets" / "services" / "keplerops-runtime"
RECEIPT_ROOT = PACK_ROOT / "ctfd" / "plugins" / "keplerops_oracle_flags"
sys.path.insert(0, str(PACK_ROOT))
from aces_contract import content_contract_bytes, research_telemetry_contract  # noqa: E402


def load_module(name: str, path: Path):
    sys.path[:0] = [str(RECEIPT_ROOT), str(RUNTIME_ROOT)]
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise AssertionError(f"unable to load {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        del sys.path[:2]


class ResearchTelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.domain = load_module("domain", RUNTIME_ROOT / "domain.py")
        self.research = load_module("keplerops_research_store", RUNTIME_ROOT / "research.py")
        self.readback = load_module(
            "keplerops_research_readback", RUNTIME_ROOT / "research_readback.py"
        )
        contract_data = research_telemetry_contract(PACK_ROOT)
        self.contract_data = contract_data
        self.contract = self.domain.ResearchContract.from_mapping(contract_data)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "research.sqlite3"
        self.store = self.research.ResearchStore(
            self.database,
            contract=self.contract,
            pseudonym_key=b"pseudonym-key-for-research-tests",
            content_key=b"c" * 32,
        )

    def test_dictionary_declares_kasmvnc_replay_scope(self) -> None:
        dictionary = (PACK_ROOT / "telemetry" / "data-dictionary.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("## KasmVNC replay scope", dictionary)
        self.assertIn(
            "Full KasmVNC frame, pointer, and keyboard replay is not required",
            dictionary,
        )
        self.assertIn("pixel-level UI state", dictionary)
        self.assertIn("SDL-authored", dictionary)
        self.assertIn("fail-open with missingness accounting", dictionary)

    def observation(self, *, sequence: int = 1):
        return self.domain.ResearchObservation.from_mapping(
            {
                "event_name": "objective.attempted",
                "occurred_at": 1_786_000_000_000_000_000 + sequence,
                "module_id": "module-02-model-evasion",
                "source_sequence": sequence,
                "status": "recorded",
                "trace_id": f"{sequence:032x}",
            },
            contract=self.contract,
            source_id="inference-gateway",
        )

    def test_store_pseudonymizes_identity_and_detects_sequence_gaps(self) -> None:
        first = self.store.record_observation(
            self.observation(sequence=1),
            source_id="inference-gateway",
            range_instance="range-405-a1",
            participant="participant-01",
            reset_generation=4,
            observed_at=1_786_000_000_000_000_101,
        )
        second = self.store.record_observation(
            self.observation(sequence=3),
            source_id="inference-gateway",
            range_instance="range-405-a1",
            participant="participant-01",
            reset_generation=4,
            observed_at=1_786_000_000_000_000_103,
        )

        self.assertEqual(first["session_id"], second["session_id"])
        self.assertNotIn("range_instance", first)
        self.assertNotIn("participant", first)
        serialized = json.dumps(self.store.events_for_session(first["session_id"]))
        self.assertNotIn("range-405-a1", serialized)
        self.assertNotIn("participant-01", serialized)
        self.assertEqual(
            self.store.source_health(first["session_id"], "inference-gateway"),
            {"accepted": 2, "dropped": 0, "sequence_gaps": 1, "last_sequence": 3},
        )
        self.assertEqual(os.stat(self.database).st_mode & 0o777, 0o600)

    def test_content_is_independently_encrypted_and_disabled_by_default(self) -> None:
        context = self.domain.derive_research_context(
            key=b"pseudonym-key-for-research-tests",
            range_instance="range-405-a1",
            participant="participant-01",
            reset_generation=4,
        )

        self.assertFalse(
            self.store.record_content(
                session_id=context.session_id,
                trace_id="a" * 32,
                signal="prompt",
                content=b"synthetic prompt content",
                observed_at=1_786_000_000_000_000_000,
            )
        )
        self.store.set_capture_signal("prompt", enabled=True)
        self.assertTrue(
            self.store.record_content(
                session_id=context.session_id,
                trace_id="a" * 32,
                signal="prompt",
                content=b"synthetic prompt content",
                observed_at=1_786_000_000_000_000_000,
            )
        )
        connection = sqlite3.connect(self.database)
        try:
            nonce, ciphertext = connection.execute(
                "SELECT nonce, ciphertext FROM research_content"
            ).fetchone()
        finally:
            connection.close()
        self.assertNotIn(b"synthetic prompt content", bytes(ciphertext))
        self.assertEqual(
            self.store.decrypt_content(bytes(nonce), bytes(ciphertext)),
            b"synthetic prompt content",
        )

        destination = Path(self.temp.name) / "content-bundle"
        digest = self.store.export_encrypted_content(context.session_id, destination)
        serialized = (destination / "content.jsonl").read_bytes()
        self.assertTrue(digest.startswith("sha256:"))
        self.assertNotIn(b"synthetic prompt content", serialized)
        self.assertNotIn(b"c" * 32, serialized)
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["encryption"], "AES-256-GCM")
        self.assertFalse(manifest["key_included"])
        readback = self.readback.verify_export_bundle(
            destination,
            contract=research_telemetry_contract(PACK_ROOT),
            content_key=b"c" * 32,
            include_content=True,
        )
        self.assertEqual(readback["content_record_count"], 1)
        decoded = base64.b64decode(readback["decrypted_content"][0]["content_b64"])
        self.assertEqual(decoded, b"synthetic prompt content")
        with self.assertRaises(self.readback.ReadbackError):
            self.readback.verify_export_bundle(
                destination,
                contract=research_telemetry_contract(PACK_ROOT),
                content_key=b"x" * 32,
            )
        for member in destination.iterdir():
            self.assertEqual(os.stat(member).st_mode & 0o777, 0o600)

    def test_emitter_is_bounded_fail_open_and_counts_loss(self) -> None:
        sent = []
        emitter = self.research.ResearchEmitter(capacity=1)

        self.assertTrue(emitter.emit({"event": 1}))
        self.assertFalse(emitter.emit({"event": 2}))
        self.assertEqual(emitter.snapshot(), {"accepted": 1, "dropped": 1, "queued": 1})

        emitter.flush_one(lambda event: sent.append(event))
        self.assertEqual(sent, [{"event": 1}])
        self.assertTrue(emitter.emit({"event": 3}))
        emitter.flush_one(lambda _: (_ for _ in ()).throw(OSError("sink unavailable")))
        self.assertEqual(emitter.snapshot(), {"accepted": 2, "dropped": 2, "queued": 0})

    def test_emitter_lifecycle_start_is_idempotent(self) -> None:
        emitter = self.research.ResearchEmitter(capacity=1)
        self.addCleanup(emitter.close)
        sent = []

        self.assertTrue(emitter.start_once(sent.append))
        self.assertFalse(emitter.start_once(sent.append))
        self.assertTrue(emitter.emit({"cycle": 1}))
        emitter.close()
        self.assertEqual(sent, [{"cycle": 1}])

        self.assertTrue(emitter.start_once(sent.append))
        self.assertTrue(emitter.emit({"cycle": 2}))
        emitter.close()
        self.assertEqual(sent, [{"cycle": 1}, {"cycle": 2}])

    def test_session_export_is_deterministic_and_reports_missingness(self) -> None:
        event = self.store.record_observation(
            self.observation(sequence=2),
            source_id="inference-gateway",
            range_instance="range-405-a1",
            participant="participant-01",
            reset_generation=4,
            observed_at=1_786_000_000_000_000_200,
        )
        first = Path(self.temp.name) / "bundle-one"
        second = Path(self.temp.name) / "bundle-two"
        metadata = {"range_profile": "gcp_full", "instrumentation_schema": 1}

        digest_one = self.store.export_session(
            event["session_id"],
            first,
            contract_document=content_contract_bytes(
                "research-telemetry-contract", PACK_ROOT
            ),
            dictionary_path=PACK_ROOT / "telemetry" / "data-dictionary.md",
            metadata=metadata,
        )
        digest_two = self.store.export_session(
            event["session_id"],
            second,
            contract_document=content_contract_bytes(
                "research-telemetry-contract", PACK_ROOT
            ),
            dictionary_path=PACK_ROOT / "telemetry" / "data-dictionary.md",
            metadata=metadata,
        )

        self.assertEqual(digest_one, digest_two)
        self.assertEqual(
            (first / "manifest.json").read_bytes(),
            (second / "manifest.json").read_bytes(),
        )
        self.assertEqual(
            json.loads((first / "environment.json").read_text(encoding="utf-8")),
            metadata,
        )
        self.assertEqual((first / "network-flows.jsonl").read_text(encoding="utf-8"), "")
        missingness = json.loads((first / "missingness.json").read_text(encoding="utf-8"))
        self.assertEqual(missingness["sequence_gaps"], 1)
        self.assertEqual(missingness["network_flow"]["capture_status"], "unavailable")
        readback = self.readback.verify_export_bundle(
            first,
            contract=research_telemetry_contract(PACK_ROOT),
            include_timeline=True,
        )
        self.assertEqual(readback["event_count"], 1)
        self.assertEqual(readback["network_flow_count"], 0)
        self.assertEqual(readback["timeline"][0]["event_name"], "objective.attempted")
        self.assertEqual(os.stat(first).st_mode & 0o777, 0o700)
        for member in first.iterdir():
            self.assertEqual(os.stat(member).st_mode & 0o777, 0o600)

    def test_contract_declares_operator_storage_profile(self) -> None:
        profile = self.contract.storage_profile

        self.assertEqual(profile["profile_id"], "research-full-content-v1")
        self.assertEqual(profile["profile_switch"], "research_capture_signals")
        self.assertEqual(profile["operational_store"]["asset"], "telemetry-proof-01")
        self.assertFalse(profile["operational_store"]["participant_visible"])
        self.assertEqual(profile["content_store"]["encrypted"], "AES-256-GCM")
        self.assertFalse(profile["content_store"]["key_included_in_export"])
        self.assertEqual(profile["lifecycle"]["failure_mode"], "fail_open_measured")
        self.assertIn("encrypted_content_decrypt", profile["readback"]["verifies"])

    def test_contract_declares_batched_network_flow_export(self) -> None:
        network_flow = self.contract_data["export"]["network_flow_export"]

        self.assertEqual(network_flow["query_mode"], "batched_time_windows")
        self.assertEqual(network_flow["output_member"], "network-flows.jsonl")
        self.assertTrue(network_flow["fail_open"])
        self.assertEqual(
            network_flow["capture_statuses"],
            ["captured", "partial", "unavailable"],
        )

    def test_operator_export_uses_iap_and_owner_only_deterministic_archive(self) -> None:
        script = (PACK_ROOT / "build" / "export-telemetry.sh").read_text(encoding="utf-8")

        self.assertIn("--tunnel-through-iap", script)
        self.assertIn("research_cli.py export", script)
        self.assertIn("research_cli.py export-content", script)
        self.assertIn("--content-output", script)
        self.assertIn("FLOW_LOG_LOOKBACK_SECONDS", script)
        self.assertIn("FLOW_LOG_TIMEOUT_SECONDS", script)
        self.assertIn("FLOW_LOG_BATCH_SECONDS", script)
        self.assertIn("flow_telemetry.py\" batches", script)
        self.assertIn("timeout \"$FLOW_LOG_TIMEOUT_SECONDS\"", script)
        self.assertIn("gcloud logging read", script)
        self.assertIn("FLOW_CAPTURE_STATUS=partial", script)
        self.assertIn("--batch-count \"$FLOW_BATCH_COUNT\"", script)
        self.assertIn("flow_telemetry.py", script)
        self.assertIn(
            "network-flows.jsonl",
            content_contract_bytes("research-telemetry-contract", PACK_ROOT).decode("utf-8"),
        )
        self.assertIn("--sort=name", script)
        self.assertIn("--mtime=@0", script)
        self.assertIn("chmod 0600", script)
        self.assertNotIn("receipt-signing-key", script)
        self.assertNotIn("research-content-key", script)
        self.assertNotIn("terraform show", script)

    def test_research_cli_restricts_runtime_config_and_decomposes_commands(self) -> None:
        source = (RUNTIME_ROOT / "research_cli.py").read_text(encoding="utf-8")

        self.assertIn("config_path.resolve(strict=True)", source)
        self.assertIn("resolved != RUNTIME_CONFIG_PATH", source)
        self.assertIn("config_path.is_symlink()", source)
        self.assertIn("def _record_lifecycle(", source)
        self.assertIn("def _export(", source)
        self.assertIn("def _readback(", source)
        self.assertIn("verify_export_bundle", source)
        self.assertIn("readback bundle escapes operator export roots", source)
        self.assertIn("def main() -> None:", source)
        self.assertNotIn("raise SystemExit(main())", source)

    def test_proof_role_content_capture_persists_without_emitter(self) -> None:
        source = (
            RUNTIME_ROOT / "keplerops_runtime" / "foundation" / "telemetry.py"
        ).read_text(encoding="utf-8")
        local = source[source.index("def _record_local_content("):]
        capture = source[source.index("def _capture("):]

        self.assertIn("derive_research_context", local)
        self.assertIn("_research_store().record_content", local)
        self.assertIn('if CONFIG["role"] == "proof":', capture)
        self.assertIn("_record_local_content(", capture)
        self.assertIn("RESEARCH_EMITTER.emit", capture)

    def test_reset_retries_missing_session_boundaries_after_health(self) -> None:
        reset = (PACK_ROOT / "build" / "reset.sh").read_text(encoding="utf-8")

        requested = reset.index("reset.requested")
        started = reset.index("session.reset_started")
        closed = reset.index("session.closed")
        quiesced = reset.index(
            "for PRIORITY in participant-workstation telemetry-proof-01"
        )
        health = reset.index('"$BUILD_ROOT/health-check.sh"')
        retried_requested = reset.index("reset.requested", requested + 1)
        retried_started = reset.index("session.reset_started", started + 1)
        retried_closed = reset.index("session.closed", closed + 1)
        opened = reset.index("session.started")
        reset_completed = reset.index("reset.completed")
        completed = reset.index("session.reset_completed")
        self.assertLess(requested, started)
        self.assertLess(started, quiesced)
        self.assertLess(closed, quiesced)
        self.assertGreater(retried_requested, health)
        self.assertGreater(retried_started, health)
        self.assertGreater(retried_closed, health)
        self.assertGreater(opened, health)
        self.assertGreater(reset_completed, opened)
        self.assertLess(reset_completed, completed)
        self.assertGreater(completed, opened)
        self.assertIn("if [[ $RESET_REQUESTED_MARKER == incomplete ]]", reset)
        self.assertIn("if [[ $RESET_STARTED_MARKER == incomplete ]]", reset)
        self.assertIn("if [[ $SESSION_CLOSED_MARKER == incomplete ]]", reset)
        self.assertIn("TELEMETRY_MARKER_STATUS=incomplete", reset)
        self.assertNotIn("&& exit 1 # telemetry", reset)


if __name__ == "__main__":
    unittest.main()
