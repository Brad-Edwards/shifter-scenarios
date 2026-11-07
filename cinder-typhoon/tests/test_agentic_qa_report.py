"""Focused fail-closed tests for the per-card agentic QA report."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "build/agentic-qa/validate.py"
SPEC = importlib.util.spec_from_file_location("cinder_agentic_qa_validate", MODULE_PATH)
assert SPEC and SPEC.loader
agentic_qa = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = agentic_qa
SPEC.loader.exec_module(agentic_qa)


class AgenticQAReportTests(unittest.TestCase):
    DIGEST = "a" * 64

    def valid_report(self) -> dict:
        candidate_path = ROOT / "build/participant-runner/candidate.json"
        release_path = ROOT / "build/release/manifest.json"
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        _, cards = agentic_qa.catalog_contract(ROOT)
        registry = json.loads((ROOT / "build/card-coverage/registry.json").read_text())["cards"]
        agent = {
            "product": "supported-agent",
            "model": "claude-sonnet-4-6[1m]",
            "version": "client-1",
            "configuration": "restricted-participant-proxy-v1",
            "tools": ["cinder-participant"],
        }
        results = []
        for index, (card_id, card) in enumerate(sorted(cards.items()), start=1):
            results.append({
                "card_id": card_id,
                "segment": card["segment"],
                "operation_id": card["operation_id"],
                "session_id": f"session-{card['operation_id'].lower()}",
                "agent": deepcopy(agent),
                "start_state": {"label": "retained", "sha256": f"{index:064x}"},
                "end_state": {"label": "operation-complete", "sha256": f"{index + 1:064x}"},
                "outcome": "passed",
                "elapsed_seconds": 10.0,
                "hints_used": [],
                "score_result": {"status": "accepted", "points": card["points"]},
                "attempts": [{
                    "sequence": 1,
                    "outcome": "passed",
                    "classification": None,
                    "elapsed_seconds": 9.0,
                    "observations": [],
                }],
                "participant_command_count": 1,
                "transcript_sha256": self.DIGEST,
                "verification": {
                    "assertion_name": registry[card_id]["black_box_assertion"]["assertion_name"],
                    "status": "passed",
                    "report_sha256": self.DIGEST,
                },
                "material_finding": False,
                "finding_issues": [],
            })
        return {
            "schema_version": 1,
            "report_kind": "participant-view-agentic-qa",
            "status": "passed",
            "candidate": {
                "candidate_id": candidate["candidate_id"],
                "source_commit": candidate["source_commit"],
                "candidate_manifest_sha256": agentic_qa.digest_file(candidate_path),
                "release_manifest_sha256": agentic_qa.digest_file(release_path),
            },
            "run": {
                "run_id": "issue-328-test",
                "project": "prod-mgau4w",
                "zone": "us-central1-a",
                "started_at": "2026-11-06T17:00:00Z",
                "finished_at": "2026-11-06T18:00:00Z",
            },
            "results": results,
            "findings": [],
            "assertions": {name: True for name in sorted(agentic_qa.ASSERTIONS)},
        }

    def test_complete_report_passes(self) -> None:
        report = self.valid_report()
        self.assertIs(agentic_qa.validate_report(report), report)

    def test_identity_card_score_and_boundary_mutations_fail(self) -> None:
        mutations = {
            "candidate digest": lambda value: value["candidate"].__setitem__("candidate_manifest_sha256", "0" * 64),
            "missing card": lambda value: value["results"].pop(),
            "duplicate card": lambda value: value["results"].__setitem__(-1, deepcopy(value["results"][0])),
            "wrong segment": lambda value: value["results"][0].__setitem__("segment", "training" if value["results"][0]["segment"] != "training" else "arwc"),
            "no command": lambda value: value["results"][0].__setitem__("participant_command_count", 0),
            "unchanged audit": lambda value: value["results"][0].__setitem__("end_state", deepcopy(value["results"][0]["start_state"])),
            "unaccepted score": lambda value: value["results"][0].__setitem__("score_result", {"status": "not_accepted", "points": 0}),
            "failed verification": lambda value: value["results"][0]["verification"].__setitem__("status", "failed"),
            "private path": lambda value: value["results"][0]["agent"].__setitem__("model", "/opt/cinder-typhoon"),
            "extra agent tool": lambda value: value["results"][0]["agent"]["tools"].append("local-shell"),
            "score differs from outcome": lambda value: value["results"][0].__setitem__("score_result", {"status": "not_accepted", "points": 0}),
            "broken audit chain": lambda value: value["results"][1]["start_state"].__setitem__("sha256", "f" * 64),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                report = self.valid_report()
                mutate(report)
                with self.assertRaises(agentic_qa.ValidationError):
                    agentic_qa.validate_report(report)

    def test_failed_attempts_remain_classified_after_success(self) -> None:
        report = self.valid_report()
        result = report["results"][0]
        result["attempts"] = [
            {
                "sequence": 1,
                "outcome": "failed",
                "classification": "agent_strategy",
                "elapsed_seconds": 3.0,
                "observations": ["failed_attempt", "confusing"],
            },
            {
                "sequence": 2,
                "outcome": "passed",
                "classification": None,
                "elapsed_seconds": 5.0,
                "observations": [],
            },
        ]
        result["elapsed_seconds"] = 9.0
        self.assertIs(agentic_qa.validate_report(report), report)

    def test_implementation_failure_requires_a_finding_issue(self) -> None:
        report = self.valid_report()
        result = report["results"][0]
        result["attempts"] = [
            {
                "sequence": 1,
                "outcome": "failed",
                "classification": "implementation",
                "elapsed_seconds": 3.0,
                "observations": ["failed_attempt", "fragile"],
            },
            {
                "sequence": 2,
                "outcome": "passed",
                "classification": None,
                "elapsed_seconds": 5.0,
                "observations": [],
            },
        ]
        result["elapsed_seconds"] = 9.0
        with self.assertRaisesRegex(agentic_qa.ValidationError, "needs an issue"):
            agentic_qa.validate_report(report)

    def test_report_status_must_follow_results_and_findings(self) -> None:
        report = self.valid_report()
        report["status"] = "failed"
        with self.assertRaisesRegex(agentic_qa.ValidationError, "status differs"):
            agentic_qa.validate_report(report)


if __name__ == "__main__":
    unittest.main()
