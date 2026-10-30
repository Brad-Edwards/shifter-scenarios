from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
sys.path.insert(0, str(TESTS))

from report_qa_status import LAYER_IDS, QAStatusError, load_status  # noqa: E402


class QALayerContractTests(unittest.TestCase):
    def test_status_has_four_separate_non_qualified_layers(self) -> None:
        status = load_status()
        self.assertEqual(tuple(status["layers"]), LAYER_IDS)
        self.assertEqual(status["overall_status"], "not_release_qualified")
        self.assertNotEqual(
            status["layers"]["blind_human_agent_playtest"]["candidate_status"],
            "passed",
        )
        known_solution = status["layers"]["known_solution_acceptance"]
        self.assertEqual(known_solution["candidate_status"], "failed")
        self.assertIn("build/card-coverage/registry.json", known_solution["evidence"])
        self.assertIn(226, known_solution["blocking_issues"])

    def test_schema_is_machine_readable(self) -> None:
        schema = json.loads((TESTS / "qa-status.schema.json").read_text())
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertIn("$id", schema)

    def test_known_solution_suites_have_unambiguous_names(self) -> None:
        for phase in ("training", "keplerops", "arwc"):
            tests = ROOT / "build" / phase / "tests"
            self.assertTrue((tests / "test_known_solution_live.py").is_file())
            self.assertFalse((tests / "test_participant_journey_live.py").exists())
            source = (tests / "test_known_solution_live.py").read_text()
            self.assertIn("Known-solution acceptance", source)
            self.assertIn("does not prove", source)

    def test_phase_runners_name_known_solution_acceptance(self) -> None:
        for phase in ("training", "keplerops", "arwc"):
            runner = (ROOT / "build" / phase / "test-local.sh").read_text()
            self.assertIn("participant-runner/run.py", runner)
            self.assertNotIn("test_participant_journey_live.py", runner)

    def test_known_solution_runs_without_mounting_test_source(self) -> None:
        participant_runner = (ROOT / "build" / "participant-runner" / "run.py").read_text()
        self.assertIn("input=source", participant_runner)
        for phase in ("training", "keplerops", "arwc"):
            runner = (ROOT / "build" / phase / "test-local.sh").read_text()
            known_solution_line = next(
                line for line in runner.splitlines() if "participant-runner/run.py" in line
            )
            self.assertNotIn("run_test", known_solution_line)

    def test_solution_suites_are_not_copied_into_images(self) -> None:
        for dockerfile in (ROOT / "build").glob("**/*.Dockerfile"):
            source = dockerfile.read_text()
            self.assertNotIn("test_known_solution_live.py", source)
            self.assertNotRegex(source, r"(?m)^COPY\s+build/(training|keplerops|arwc)/tests(?:/|\s)")

    def test_release_gate_rejects_incomplete_layers(self) -> None:
        result = subprocess.run(
            [sys.executable, str(TESTS / "report_qa_status.py"), "--require-release-qualified"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("release gate: FAIL", result.stdout)
        for layer_id in LAYER_IDS:
            self.assertIn(f"{layer_id}:", result.stdout)

    def test_status_cannot_claim_qualification_from_incomplete_layers(self) -> None:
        value = json.loads((TESTS / "qa-status.json").read_text())
        value["overall_status"] = "release_qualified"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qa-status.json"
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(QAStatusError, "disagrees with layer evidence"):
                load_status(path)


if __name__ == "__main__":
    unittest.main()
