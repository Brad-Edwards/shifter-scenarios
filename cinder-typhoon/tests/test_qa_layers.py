from __future__ import annotations

from copy import deepcopy
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
REPOSITORY_ROOT = ROOT.parent
sys.path.insert(0, str(TESTS))

from report_qa_status import (  # noqa: E402
    LAYER_IDS,
    QAStatusError,
    _current_commit,
    _validate_candidate_report_context,
    _validate_issue_registry,
    _write_report,
    check_github_issues,
    evaluate_status,
    load_status,
)


def _set_json_path(document: dict[str, object], dotted_path: str, value: object) -> None:
    current = document
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})  # type: ignore[assignment]
    current[parts[-1]] = value


def _current_gate_runner(status: dict[str, object]):
    gates = status["_gates"]

    def run(argv: list[str]) -> dict[str, object]:
        gate = next(
            candidate
            for candidate in gates.values()  # type: ignore[union-attr]
            if candidate["kind"] == "command" and candidate["argv"] == argv
        )
        output: dict[str, object] = {}
        for field, expected in gate["expect"].get("json", {}).items():
            _set_json_path(output, field, expected)
        if "build/fourth-wall/run.py" in argv and any(phase in argv for phase in ("keplerops", "arwc")):
            count = 17 if "keplerops" in argv else 456
            _set_json_path(output, "summary.static_finding_count", count)
            _set_json_path(output, "summary.unresolved_finding_count", count)
        return {
            "exit_code": gate["expect"]["exit_code"],
            "stdout": json.dumps(output) if "json" in gate["expect"] else "",
            "stderr": "",
        }

    return run


class QALayerContractTests(unittest.TestCase):
    def test_current_status_is_derived_from_real_gate_outcomes(self) -> None:
        status = load_status()
        result = evaluate_status(status, _current_gate_runner(status))
        self.assertEqual(tuple(result["layers"]), LAYER_IDS)
        self.assertEqual(result["overall_status"], "not_release_qualified")
        self.assertEqual(result["layers"]["service_contract"]["implementation_status"], "complete")
        self.assertEqual(result["layers"]["known_solution_acceptance"]["implementation_status"], "partial")
        self.assertEqual(result["layers"]["provenance_and_surface"]["implementation_status"], "partial")
        self.assertEqual(result["layers"]["blind_human_agent_playtest"]["implementation_status"], "not_started")
        self.assertTrue(all(layer["candidate_status"] == "not_run" for layer in result["layers"].values()))

    def test_complete_claim_is_rejected_when_its_command_gate_fails(self) -> None:
        status = load_status()
        passing_runner = _current_gate_runner(status)

        def runner(argv: list[str]) -> dict[str, object]:
            if argv[:4] == ["python3", "-m", "unittest", "tests/test_arwc_handover.py"]:
                return {"exit_code": 1, "stdout": "", "stderr": "failure details"}
            return passing_runner(argv)

        with self.assertRaisesRegex(QAStatusError, "service_contract.*disagrees"):
            evaluate_status(status, runner)

    def test_unresolved_fourth_wall_findings_prevent_complete_claim(self) -> None:
        status = load_status()
        status["layers"]["provenance_and_surface"]["implementation_status"] = "complete"
        with self.assertRaisesRegex(QAStatusError, "provenance_and_surface.*disagrees"):
            evaluate_status(status, _current_gate_runner(status))

    def test_blockers_are_derived_from_the_open_issue_registry(self) -> None:
        status = load_status()
        result = evaluate_status(status, _current_gate_runner(status))
        self.assertIn(231, result["layers"]["service_contract"]["blocking_issues"])
        self.assertIn(265, result["layers"]["known_solution_acceptance"]["blocking_issues"])
        self.assertIn(266, result["layers"]["provenance_and_surface"]["blocking_issues"])
        self.assertNotIn(231, result["layers"]["known_solution_acceptance"]["blocking_issues"])

    def test_closed_issue_requires_named_digest_bound_acceptance_evidence(self) -> None:
        status = load_status()
        registry = deepcopy(status["_issue_registry_meta"])
        registry["issues"]["231"]["state"] = "closed"
        with self.assertRaisesRegex(QAStatusError, "closed issue lacks verified acceptance"):
            _validate_issue_registry(registry)

        registry["issues"]["231"]["acceptance"]["status"] = "verified"
        with self.assertRaisesRegex(QAStatusError, "lacks named acceptance evidence"):
            _validate_issue_registry(registry)

    def test_candidate_reports_fail_closed_on_missing_or_cross_release_context(self) -> None:
        current_commit = _current_commit()
        candidate_digest = "1" * 64
        release_digest = "2" * 64
        candidate = {
            "immutable": True,
            "source_commit": current_commit,
            "artifact_digests": {"image": f"sha256:{'3' * 64}"},
        }
        report = {
            "source_commit": current_commit,
            "candidate_manifest_sha256": candidate_digest,
            "release_manifest_sha256": release_digest,
        }
        _validate_candidate_report_context(
            report, candidate, candidate_digest, release_digest, current_commit, "report"
        )
        cases = (
            (report, candidate, candidate_digest, None, current_commit, "release manifest is missing"),
            ({**report, "source_commit": "4" * 40}, candidate, candidate_digest, release_digest, current_commit, "stale"),
            ({**report, "candidate_manifest_sha256": "5" * 64}, candidate, candidate_digest, release_digest, current_commit, "another candidate"),
            ({**report, "release_manifest_sha256": "6" * 64}, candidate, candidate_digest, release_digest, current_commit, "another release"),
            (report, {**candidate, "immutable": False}, candidate_digest, release_digest, current_commit, "mutable candidate"),
        )
        for altered_report, altered_candidate, candidate_hash, release_hash, commit, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(QAStatusError, message):
                _validate_candidate_report_context(
                    altered_report,
                    altered_candidate,
                    candidate_hash,
                    release_hash,
                    commit,
                    "report",
                )

    def test_candidate_result_cannot_be_claimed_without_a_report(self) -> None:
        value = json.loads((TESTS / "qa-status.json").read_text())
        value["layers"]["service_contract"]["candidate_status"] = "passed"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qa-status.json"
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(QAStatusError, "candidate result requires reports"):
                load_status(path)

    def test_bound_gate_catalog_change_is_rejected(self) -> None:
        value = json.loads((TESTS / "qa-status.json").read_text())
        value["gate_catalog"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qa-status.json"
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(QAStatusError, "bound file digest changed"):
                load_status(path)

    def test_github_check_rejects_snapshot_drift(self) -> None:
        status = load_status()
        issues = status["_issue_registry_meta"]["issues"]

        class FakeResponse(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

        def urlopen(_request, timeout=0):
            payload = [
                {
                    "number": int(number),
                    "state": expected["state"],
                    "title": expected["title"],
                    "milestone": {"number": status["_issue_registry_meta"]["milestone"]["number"]},
                }
                for number, expected in issues.items()
                if expected["state"] == "open" and number != "219"
            ]
            return FakeResponse(json.dumps(payload).encode())

        with patch.dict(os.environ, {"SHIFTER_GITHUB_PERSONAL_ACCESS_TOKEN": "redacted"}), patch(
            "report_qa_status.urllib.request.urlopen", side_effect=urlopen
        ), self.assertRaisesRegex(QAStatusError, "open issue set changed"):
            check_github_issues(status)

    def test_evidence_report_is_owner_only_and_contains_hashes_not_command_output(self) -> None:
        result = {
            "source_commit": _current_commit(),
            "gate_results": {"gate": {"stdout_sha256": "7" * 64, "stderr_sha256": "8" * 64}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            _write_report(path, result)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            contents = path.read_text()
            self.assertIn("stdout_sha256", contents)
            self.assertNotIn("failure details", contents)

    def test_schema_and_catalogs_are_machine_readable(self) -> None:
        schema = json.loads((TESTS / "qa-status.schema.json").read_text())
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["schema_version"]["const"], 2)
        self.assertEqual(json.loads((TESTS / "qa-gates.json").read_text())["schema_version"], 1)
        self.assertEqual(json.loads((TESTS / "readiness-issues.json").read_text())["schema_version"], 1)

    def test_pack_validation_runs_status_and_consistency_tests(self) -> None:
        compatibility = (ROOT / "pack.compatibility.yaml").read_text()
        self.assertIn("python3 tests/report_qa_status.py", compatibility)
        self.assertIn("python3 -m unittest tests/test_qa_layers.py", compatibility)
        self.assertIn("qa-status-consistent", compatibility)
        self.assertIn("qa-documentation-consistent", compatibility)

    def test_readiness_documents_name_all_evidence_stages_without_pr_state_claims(self) -> None:
        task = (REPOSITORY_ROOT / "TASK.md").read_text()
        for stage in (
            "Merged",
            "Implemented",
            "Statically verified",
            "Live verified",
            "Playtested",
            "Soaked",
            "Release qualified",
        ):
            self.assertIn(stage, task)
        self.assertNotRegex(task, r"(?i)PRs? #\d+[^\n]*(open|merged)")
        self.assertIn("Not release qualified", task)
        self.assertIn("17 KeplerOps and 456 ARWC findings", task)
        pack_readme = (ROOT / "README.md").read_text()
        self.assertIn("not release qualified", pack_readme.lower())
        self.assertIn("known-solution implementation partial", pack_readme)
        qa_readme = (TESTS / "README.md").read_text()
        self.assertIn("17 unresolved KeplerOps findings", qa_readme)
        self.assertIn("`--require-complete` currently passes", qa_readme)

    def test_known_solution_suites_remain_operator_only(self) -> None:
        participant_runner = (ROOT / "build" / "participant-runner" / "run.py").read_text()
        self.assertIn("input=source", participant_runner)
        for phase in ("training", "keplerops", "arwc"):
            tests = ROOT / "build" / phase / "tests"
            source = (tests / "test_known_solution_live.py").read_text()
            self.assertIn("Known-solution acceptance", source)
            runner = (ROOT / "build" / phase / "test-local.sh").read_text()
            known_solution_line = next(line for line in runner.splitlines() if "participant-runner/run.py" in line)
            self.assertNotIn("run_test", known_solution_line)


if __name__ == "__main__":
    unittest.main()
