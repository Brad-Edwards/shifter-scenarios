from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


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
        self.assertEqual(expected, 391)
        self.assertEqual(self.report["summary"]["request_count"], expected)
        self.assertEqual(len(self.report["requests"]), expected)
        self.assertEqual(
            len({entry["request_id"] for entry in self.report["requests"]}), expected,
        )

    def test_every_fixed_runtime_comparison_is_in_the_ratcheted_inventory(self) -> None:
        inventory = provenance.runtime_comparison_inventory()
        expected = sum(item["comparison_count"] for item in inventory.values())
        self.assertEqual(expected, 1156)
        self.assertEqual(self.report["summary"]["runtime_comparison_count"], expected)
        self.assertEqual(len(self.report["runtime_comparisons"]), expected)

    def test_non_python_runtime_sources_are_ratcheted_too(self) -> None:
        inventory = provenance.runtime_source_inventory()
        self.assertEqual(len(inventory), 38)
        self.assertEqual(self.report["summary"]["runtime_source_count"], 38)
        self.assertEqual(len(self.report["runtime_sources"]), 38)

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

    def test_known_author_only_inputs_are_explicit_failures(self) -> None:
        cases = {
            ("arwc", "test_w33_forecast_scheduling"): {223},
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

    def test_release_form_fails_while_inputs_are_unresolved(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(PROVENANCE_PATH), "--require-complete"],
            text=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(self.report["overall_status"], "unresolved")

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
        self.assertEqual(status["status"], "unresolved")
        self.assertEqual(events[0]["provenance"]["status"], "unresolved")
        self.assertTrue(events[0]["provenance"]["sources"])

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
