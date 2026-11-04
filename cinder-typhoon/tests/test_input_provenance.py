from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PROVENANCE_PATH = ROOT / "build" / "input-provenance" / "provenance.py"
SPEC = importlib.util.spec_from_file_location("cinder_input_provenance", PROVENANCE_PATH)
assert SPEC and SPEC.loader
provenance = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = provenance
SPEC.loader.exec_module(provenance)


class ProvenanceInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ledger = provenance.load_ledger()
        cls.report = provenance.build_report(cls.ledger)

    def test_every_authored_request_has_a_report_entry(self) -> None:
        inventory = provenance.request_inventory()
        expected = sum(
            method["request_count"]
            for methods in inventory.values()
            for method in methods.values()
        )
        self.assertEqual(expected, 399)
        self.assertEqual(self.report["summary"]["request_count"], expected)
        self.assertEqual(len(self.report["requests"]), expected)
        self.assertEqual(
            len({entry["request_id"] for entry in self.report["requests"]}), expected,
        )

    def test_every_fixed_runtime_comparison_is_in_the_ratcheted_inventory(self) -> None:
        inventory = provenance.runtime_comparison_inventory()
        expected = sum(item["comparison_count"] for item in inventory.values())
        self.assertEqual(expected, 1135)
        self.assertEqual(self.report["summary"]["runtime_comparison_count"], expected)
        self.assertEqual(len(self.report["runtime_comparisons"]), expected)

    def test_non_python_runtime_sources_are_ratcheted_too(self) -> None:
        inventory = provenance.runtime_source_inventory()
        self.assertEqual(len(inventory), 40)
        self.assertEqual(self.report["summary"]["runtime_source_count"], 40)
        self.assertEqual(len(self.report["runtime_sources"]), 40)

    def test_new_or_changed_request_inputs_fail_ledger_validation(self) -> None:
        changed = copy.deepcopy(self.ledger)
        entry = changed["methods"]["training"]["test_01_first_contact"]
        entry["inventory_sha256"] = "0" * 64
        with self.assertRaisesRegex(provenance.ProvenanceError, "request inputs changed"):
            provenance.validate_ledger(changed)

    def test_new_or_changed_runtime_comparison_fails_ledger_validation(self) -> None:
        changed = copy.deepcopy(self.ledger)
        first = next(iter(changed["runtime_comparisons"].values()))
        first["inventory_sha256"] = "0" * 64
        with self.assertRaisesRegex(provenance.ProvenanceError, "comparisons changed"):
            provenance.validate_ledger(changed)

    def test_changed_non_python_runtime_source_fails_ledger_validation(self) -> None:
        changed = copy.deepcopy(self.ledger)
        first = next(iter(changed["runtime_sources"].values()))
        first["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(provenance.ProvenanceError, "runtime source changed"):
            provenance.validate_ledger(changed)

    def test_all_inventory_drift_is_reported_in_one_validation(self) -> None:
        changed = copy.deepcopy(self.ledger)
        changed["methods"]["arwc"]["test_w27_integrity_collision"][
            "inventory_sha256"
        ] = "0" * 64
        comparison = "build/arwc/runtime/diagnostic_services.py"
        changed["runtime_comparisons"][comparison]["inventory_sha256"] = "0" * 64
        source = "build/keplerops/runtime/k-dev-entrypoint.sh"
        changed["runtime_sources"][source]["source_sha256"] = "0" * 64

        with self.assertRaises(provenance.ProvenanceError) as raised:
            provenance.validate_ledger(changed)

        message = str(raised.exception)
        self.assertIn("arwc.test_w27_integrity_collision", message)
        self.assertIn(comparison, message)
        self.assertIn(source, message)

    def test_known_author_only_inputs_are_explicit_failures(self) -> None:
        cases = {
        }
        for (phase, method), expected in cases.items():
            with self.subTest(phase=phase, method=method):
                issues = {
                    item["issue"]
                    for item in self.ledger["methods"][phase][method]["unresolved"]
                }
                self.assertLessEqual(expected, issues)

    def test_report_uses_locations_and_hashes_not_raw_inputs(self) -> None:
        for entry in self.report["requests"]:
            self.assertRegex(entry["callsite_sha256"], r"^[0-9a-f]{64}$")
            self.assertNotIn("value", entry)
            self.assertNotIn("body", entry)
            self.assertNotIn("headers", entry)
        for entry in self.report["runtime_comparisons"]:
            self.assertEqual(
                set(entry),
                {
                    "comparison_id", "source", "comparison_sha256",
                    "review_status", "citations", "unresolved",
                },
            )

    def test_release_form_passes_when_inputs_are_complete(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(PROVENANCE_PATH), "--require-complete"],
            text=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(self.report["overall_status"], "complete")

    def test_live_request_event_receives_method_provenance(self) -> None:
        event = {
            "kind": "http", "test_method": "test_01_first_contact",
            "method": "GET", "host": "workbench.training", "path_sha256": "b" * 64,
            "status": 200, "response_bytes": 10,
            "response_sha256": "a" * 64, "elapsed_ms": 1,
        }
        events, status = provenance.attach_runtime_provenance(
            "training", [event], ["test_01_first_contact"], self.ledger,
        )
        self.assertEqual(status["status"], "complete")
        self.assertEqual(events[0]["provenance"]["status"], "complete")
        self.assertTrue(events[0]["provenance"]["sources"])

    def test_runtime_attachment_validates_only_the_selected_phase(self) -> None:
        event = {
            "kind": "http", "test_method": "test_01_first_contact",
            "method": "GET", "host": "workbench.training", "path_sha256": "b" * 64,
            "status": 200, "response_bytes": 10,
            "response_sha256": "a" * 64, "elapsed_ms": 1,
        }
        with mock.patch.object(
            provenance, "load_ledger", return_value=self.ledger,
        ) as load:
            provenance.attach_runtime_provenance(
                "training", [event], ["test_01_first_contact"],
            )
        load.assert_called_once_with(phases=("training",))

    def test_phase_deployment_needs_only_its_suite_and_runtime(self) -> None:
        for phase in provenance.PHASES:
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                isolated_root = Path(directory)
                shutil.copytree(
                    ROOT / "build/input-provenance",
                    isolated_root / "build/input-provenance",
                )
                suite = provenance.SUITES[phase].relative_to(ROOT)
                (isolated_root / suite).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / suite, isolated_root / suite)
                shutil.copytree(
                    ROOT / "build" / phase / "runtime",
                    isolated_root / "build" / phase / "runtime",
                )
                report = isolated_root / "report.json"
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(isolated_root / "build/input-provenance/provenance.py"),
                        "--phase", phase, "--require-complete", "--output", str(report),
                    ],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                value = json.loads(report.read_text())
                self.assertEqual({entry["phase"] for entry in value["requests"]}, {phase})

    def test_phase_validation_detects_selected_mutation_without_other_phases(self) -> None:
        selected = copy.deepcopy(self.ledger)
        selected["methods"]["training"]["test_01_first_contact"][
            "inventory_sha256"
        ] = "0" * 64
        with self.assertRaisesRegex(provenance.ProvenanceError, "request inputs changed"):
            provenance.validate_ledger(selected, ("training",))

        absent = copy.deepcopy(self.ledger)
        absent["methods"]["arwc"]["test_w01_customer_copy"][
            "inventory_sha256"
        ] = "0" * 64
        provenance.validate_ledger(absent, ("training",))
        with self.assertRaisesRegex(provenance.ProvenanceError, "request inputs changed"):
            provenance.validate_ledger(absent)

    def test_machine_readable_schemas_are_present(self) -> None:
        root = ROOT / "build" / "input-provenance"
        for name in ("ledger.schema.json", "report.schema.json"):
            value = json.loads((root / name).read_text())
            self.assertEqual(value["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertIn("$id", value)

    def test_new_ledger_creation_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text("existing")
            completed = subprocess.run(
                [sys.executable, str(PROVENANCE_PATH), "--new-unresolved-ledger", str(path)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(path.read_text(), "existing")


if __name__ == "__main__":
    unittest.main()
