"""Focused boundary and lifecycle tests for the agentic QA participant proxy."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "build/agentic-qa/proxy.py"
SPEC = importlib.util.spec_from_file_location("cinder_agentic_qa_proxy", MODULE_PATH)
assert SPEC and SPEC.loader
proxy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = proxy
SPEC.loader.exec_module(proxy)


class AgenticQAProxyTests(unittest.TestCase):
    def config(self, directory: Path) -> Path:
        value = {
            "schema_version": 1,
            "candidate": {
                "candidate_id": "candidate-1",
                "source_commit": "a" * 40,
                "candidate_manifest_sha256": "b" * 64,
                "release_manifest_sha256": "c" * 64,
            },
            "phase": "training",
            "operation_id": "T01",
            "session_id": "session-t01",
            "reset_identity": "reset-1",
            "project": "prod-mgau4w",
            "zone": "us-central1-a",
            "account": "bedwards@paloaltonetworks.com",
            "gcloud_path": "/snap/bin/gcloud",
            "agent": {
                "product": "supported-agent",
                "model": "claude-sonnet-4-6[1m]",
                "version": "client-1",
                "configuration": "restricted-participant-proxy-v1",
                "tools": ["cinder-participant"],
            },
            "cards": [{
                "id": "T01.1",
                "title": "Card title",
                "description": "Participant-visible work.",
                "points": 50,
                "hints": ["First published hint.", "Second published hint.", "Third published hint."],
            }],
            "paths": {
                "state": str(directory / "state.json"),
                "raw_log": str(directory / "raw.jsonl"),
                "export": str(directory / "operation.json"),
            },
            "started_at": "2026-11-06T17:00:00Z",
            "start_label": "pristine",
            "timeout_seconds": 60,
        }
        path = directory / "config.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        path.chmod(0o600)
        return path

    def call(self, config: Path, *arguments: str) -> int:
        return proxy.main(["--config", str(config), *arguments])

    def test_complete_card_lifecycle_exports_content_free_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            config = self.config(directory)
            completed = subprocess.CompletedProcess([], 0, b"participant result\n", b"")
            with mock.patch.object(proxy, "remote_command", return_value=completed):
                self.assertEqual(self.call(config, "begin", "T01.1"), 0)
                self.assertEqual(self.call(config, "hint", "T01.1", "1"), 0)
                self.assertEqual(self.call(config, "exec", "T01.1", "curl -s http://workbench.training:8080/"), 0)
                self.assertEqual(self.call(config, "finish", "T01.1", "passed", "--score-status", "accepted"), 0)
            report = directory / "operation.json"
            self.assertEqual(self.call(config, "export"), 0)
            value = json.loads(report.read_text(encoding="utf-8"))
            result = value["results"][0]
            self.assertEqual(result["outcome"], "passed")
            self.assertEqual(result["hints_used"], [1])
            self.assertEqual(result["participant_command_count"], 1)
            self.assertEqual(result["score_result"], {"status": "accepted", "points": 50})
            self.assertNotEqual(result["start_state"]["sha256"], result["end_state"]["sha256"])
            encoded = report.read_text(encoding="utf-8")
            self.assertNotIn("curl", encoded)
            self.assertNotIn("participant result", encoded)
            self.assertTrue((directory / "raw.jsonl").exists())

    def test_proxy_pins_the_exact_golden_and_participant_container(self) -> None:
        config = {
            "phase": "training",
            "project": "prod-mgau4w",
            "zone": "us-central1-a",
            "account": "bedwards@paloaltonetworks.com",
            "gcloud_path": "/snap/bin/gcloud",
            "timeout_seconds": 60,
        }
        completed = subprocess.CompletedProcess([], 0, b"", b"")
        with mock.patch.object(proxy.subprocess, "run", return_value=completed) as invoked:
            self.assertIs(proxy.remote_command(config, "id"), completed)
        arguments = invoked.call_args.args[0]
        self.assertEqual(arguments[:4], ["/snap/bin/gcloud", "compute", "ssh", "cinder-training-golden"])
        remote = arguments[arguments.index("--command") + 1]
        self.assertIn("cinder-training-kali", remote)
        self.assertIn("2000:2000", remote)
        self.assertNotIn("/opt/cinder-typhoon", remote)

    def test_failed_attempt_requires_a_classification_and_is_retained(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            config = self.config(directory)
            completed = subprocess.CompletedProcess([], 1, b"", b"ordinary failure")
            with mock.patch.object(proxy, "remote_command", return_value=completed):
                self.assertEqual(self.call(config, "begin", "T01.1"), 0)
                with mock.patch.object(sys, "stderr", io.TextIOWrapper(io.BytesIO(), encoding="utf-8")):
                    self.assertEqual(self.call(config, "exec", "T01.1", "false"), 1)
                self.assertEqual(self.call(config, "finish", "T01.1", "failed", "--score-status", "not_accepted", "--classification", "agent_strategy", "--observations", "confusing"), 0)
                self.assertEqual(self.call(config, "begin", "T01.1"), 0)
                completed.returncode = 0
                self.assertEqual(self.call(config, "exec", "T01.1", "true"), 0)
                self.assertEqual(self.call(config, "finish", "T01.1", "passed", "--score-status", "accepted"), 0)
            report = directory / "operation.json"
            self.assertEqual(self.call(config, "export"), 0)
            attempts = json.loads(report.read_text())["results"][0]["attempts"]
            self.assertEqual([item["outcome"] for item in attempts], ["failed", "passed"])
            self.assertEqual(attempts[0]["classification"], "agent_strategy")
            self.assertIn("failed_attempt", attempts[0]["observations"])


if __name__ == "__main__":
    unittest.main()
