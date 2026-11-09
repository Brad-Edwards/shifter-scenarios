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

    def test_product_attempts_exclude_agent_strategy_errors(self) -> None:
        attempts = [
            {
                "sequence": 1,
                "outcome": "failed",
                "classification": "implementation",
                "elapsed_seconds": 3.0,
                "observations": ["failed_attempt"],
            },
            {
                "sequence": 2,
                "outcome": "failed",
                "classification": "agent_strategy",
                "elapsed_seconds": 3.0,
                "observations": ["failed_attempt"],
            },
            {
                "sequence": 3,
                "outcome": "passed",
                "classification": None,
                "elapsed_seconds": 2.0,
                "observations": [],
            },
        ]

        retained = assemble.product_attempts(attempts, "K04.2")

        self.assertEqual([item["sequence"] for item in retained], [1, 2])
        self.assertEqual([item["outcome"] for item in retained], ["failed", "passed"])
        self.assertEqual(retained[0]["classification"], "implementation")
        self.assertEqual(attempts[0]["sequence"], 1)
        with self.assertRaises(assemble.AssemblyError):
            assemble.product_attempts(attempts[1:2], "K04.2")

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
            assemble.validate_campaign_structure(reports, order, set()),
            ("campaign-1", []),
        )

        mutations = {
            "campaign": lambda value: value[("arwc", "W01")].__setitem__("campaign_id", "campaign-2"),
            "phase reset": lambda value: value[("keplerops", "K02")].__setitem__("reset_identity", "different-reset"),
            "overlap": lambda value: value[("keplerops", "K02")].__setitem__("started_at", "2026-11-07T11:04:59Z"),
            "transition order": lambda value: value[("arwc", "W01")].__setitem__("started_at", "2026-11-07T11:09:59Z"),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                mutated = deepcopy(reports)
                mutate(mutated)
                with self.assertRaises(assemble.AssemblyError):
                    assemble.validate_campaign_structure(mutated, order, set())

    def test_campaign_structure_accepts_only_an_exact_reset_boundary(self) -> None:
        agent = self.operation_report()[0]["agent"]
        order = {
            "training": ["T01"],
            "keplerops": ["K01", "K02"],
            "arwc": ["W01"],
        }

        def operation(reset: str, label: str, minute: int) -> dict:
            return {
                "campaign_id": "campaign-1",
                "reset_identity": reset,
                "agent": deepcopy(agent),
                "started_at": f"2026-11-07T11:{minute:02d}:00Z",
                "finished_at": f"2026-11-07T11:{minute + 1:02d}:00Z",
                "results": [{"start_state": {"label": label}}],
            }

        reports = {
            ("training", "T01"): operation("training-reset", "pristine", 0),
            ("keplerops", "K01"): operation("kepler-old", "pristine", 2),
            ("keplerops", "K02"): operation("kepler-new", "pristine", 4),
            ("arwc", "W01"): operation("arwc-reset", "transition-earned", 6),
        }
        campaign, boundaries = assemble.validate_campaign_structure(
            reports, order, {("keplerops", "K02")}
        )
        self.assertEqual(campaign, "campaign-1")
        self.assertEqual(boundaries, [{
            "phase": "keplerops",
            "operation_id": "K02",
            "previous_reset_identity": "kepler-old",
            "reset_identity": "kepler-new",
        }])

        for name, declared in {
            "missing": set(),
            "wrong": {("arwc", "W01")},
            "extra": {("keplerops", "K01"), ("keplerops", "K02")},
        }.items():
            with self.subTest(mutation=name):
                with self.assertRaises(assemble.AssemblyError):
                    assemble.validate_campaign_structure(reports, order, declared)


if __name__ == "__main__":
    unittest.main()
