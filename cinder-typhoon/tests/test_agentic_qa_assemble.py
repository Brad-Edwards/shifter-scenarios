"""Focused fail-closed tests for agentic QA operation evidence assembly."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "build/agentic-qa/assemble.py"
SPEC = importlib.util.spec_from_file_location("cinder_agentic_qa_assemble", MODULE_PATH)
assert SPEC and SPEC.loader
assemble = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = assemble
SPEC.loader.exec_module(assemble)


class AgenticQAAssemblyTests(unittest.TestCase):
    def operation_report(self) -> tuple[dict, list[dict]]:
        cards = [
            {"id": "T01.1", "points": 50},
            {"id": "T01.2", "points": 50},
        ]
        results = []
        for index, card in enumerate(cards, start=1):
            results.append({
                "card_id": card["id"],
                "points": card["points"],
                "outcome": "passed",
                "elapsed_seconds": 2.0,
                "hints_used": [],
                "score_result": {"status": "accepted", "points": card["points"]},
                "attempts": [{
                    "sequence": 1,
                    "outcome": "passed",
                    "classification": None,
                    "elapsed_seconds": 1.0,
                    "observations": [],
                }],
                "participant_command_count": 1,
                "transcript_sha256": "d" * 64,
                "start_state": {
                    "label": "pristine" if index == 1 else "retained",
                    "sha256": f"{index:064x}",
                },
                "end_state": {
                    "label": "operation-complete",
                    "sha256": f"{index + 1:064x}",
                },
            })
        return {
            "schema_version": 1,
            "report_kind": "participant-view-agentic-qa-operation",
            "candidate": {
                "candidate_id": "candidate-1",
                "source_commit": "a" * 40,
                "candidate_manifest_sha256": "b" * 64,
                "release_manifest_sha256": "c" * 64,
            },
            "phase": "training",
            "operation_id": "T01",
            "session_id": "session-t01",
            "campaign_id": "campaign-1",
            "reset_identity": "reset-1",
            "agent": {
                "product": "supported-agent",
                "model": "supported-model",
                "version": "client-1",
                "configuration": "restricted-participant-proxy-v1",
                "tools": ["cinder-participant"],
            },
            "started_at": "2026-11-07T12:00:00Z",
            "finished_at": "2026-11-07T12:05:00Z",
            "results": results,
        }, cards

    def test_strict_operation_report_passes(self) -> None:
        report, cards = self.operation_report()
        self.assertIs(
            assemble.validate_operation_report(report, "training", "T01", cards),
            report,
        )

    def test_score_tool_and_chain_mutations_fail(self) -> None:
        mutations = {
            "fabricated score": lambda value: value["results"][0].__setitem__(
                "score_result", {"status": "not_accepted", "points": 0}
            ),
            "extra tool": lambda value: value["agent"]["tools"].append("local-shell"),
            "broken chain": lambda value: value["results"][1]["start_state"].__setitem__(
                "sha256", "f" * 64
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                report, cards = self.operation_report()
                mutated = deepcopy(report)
                mutate(mutated)
                with self.assertRaises(assemble.AssemblyError):
                    assemble.validate_operation_report(mutated, "training", "T01", cards)

    def test_campaign_structure_rejects_identity_and_timing_changes(self) -> None:
        agent = self.operation_report()[0]["agent"]
        order = {
            "training": ["T01"],
            "keplerops": ["K01", "K02"],
            "arwc": ["W01"],
        }

        def operation(phase: str, operation_id: str, start: str, finish: str, label: str) -> dict:
            return {
                "campaign_id": "campaign-1",
                "reset_identity": f"{phase}-reset",
                "agent": deepcopy(agent),
                "started_at": start,
                "finished_at": finish,
                "results": [{"start_state": {"label": label}}],
            }

        reports = {
            ("training", "T01"): operation("training", "T01", "2026-11-07T10:00:00Z", "2026-11-07T10:05:00Z", "pristine"),
            ("keplerops", "K01"): operation("keplerops", "K01", "2026-11-07T11:00:00Z", "2026-11-07T11:05:00Z", "pristine"),
            ("keplerops", "K02"): operation("keplerops", "K02", "2026-11-07T11:05:00Z", "2026-11-07T11:10:00Z", "retained"),
            ("arwc", "W01"): operation("arwc", "W01", "2026-11-07T11:10:00Z", "2026-11-07T11:15:00Z", "transition-earned"),
        }
        self.assertEqual(
            assemble.validate_campaign_structure(reports, order), "campaign-1"
        )

        mutations = {
            "campaign": lambda value: value[("arwc", "W01")].__setitem__("campaign_id", "campaign-2"),
            "agent": lambda value: value[("keplerops", "K02")]["agent"].__setitem__("model", "different-model"),
            "phase reset": lambda value: value[("keplerops", "K02")].__setitem__("reset_identity", "different-reset"),
            "overlap": lambda value: value[("keplerops", "K02")].__setitem__("started_at", "2026-11-07T11:04:59Z"),
            "transition order": lambda value: value[("arwc", "W01")].__setitem__("started_at", "2026-11-07T11:09:59Z"),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                mutated = deepcopy(reports)
                mutate(mutated)
                with self.assertRaises(assemble.AssemblyError):
                    assemble.validate_campaign_structure(mutated, order)


if __name__ == "__main__":
    unittest.main()
