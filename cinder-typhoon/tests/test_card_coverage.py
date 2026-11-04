from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVERAGE_PATH = ROOT / "build" / "card-coverage" / "coverage.py"
SPEC = importlib.util.spec_from_file_location("cinder_card_coverage", COVERAGE_PATH)
assert SPEC and SPEC.loader
coverage = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = coverage
SPEC.loader.exec_module(coverage)

RELEASE_PATH = ROOT / "build" / "release" / "manifest.py"
RELEASE_SPEC = importlib.util.spec_from_file_location(
    "coverage_test_release_manifest", RELEASE_PATH,
)
assert RELEASE_SPEC and RELEASE_SPEC.loader
release_manifest = importlib.util.module_from_spec(RELEASE_SPEC)
sys.modules[RELEASE_SPEC.name] = release_manifest
RELEASE_SPEC.loader.exec_module(release_manifest)


class CardCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = coverage.load_registry()
        cls.report = coverage.build_report(cls.registry)

    def test_registry_exactly_matches_all_three_authored_card_sources(self) -> None:
        sdl = set(coverage.authored_sdl_cards())
        briefs = set(coverage.authored_brief_cards())
        dependencies = set(coverage.dependency_cards())
        registered = set(self.registry["cards"])
        self.assertEqual(sdl, briefs)
        self.assertEqual(sdl, dependencies)
        self.assertEqual(sdl, registered)
        self.assertEqual(len(registered), 240)
        self.assertEqual(
            {prefix: sum(card.startswith(prefix) for card in registered) for prefix in "TKW"},
            {"T": 16, "K": 104, "W": 120},
        )

    def test_committed_registry_is_the_reviewed_generated_form(self) -> None:
        self.assertEqual(coverage.build_registry(), self.registry)

    def test_every_card_has_one_unique_named_black_box_assertion(self) -> None:
        assertions = []
        for card_id, entry in self.registry["cards"].items():
            with self.subTest(card_id=card_id):
                black_box = entry["black_box_assertion"]
                self.assertEqual(black_box["status"], "complete")
                self.assertEqual(len(black_box["matches"]), 1)
                self.assertEqual(black_box["matches"][0]["combined_card_ids"], [card_id])
                self.assertTrue(black_box["matches"][0]["assertions"])
                assertions.append(black_box["assertion_name"])
        self.assertEqual(len(assertions), len(set(assertions)))
        self.assertEqual(self.report["summary"]["complete_black_box_card_count"], 240)

    def test_k20_has_three_separate_actions_and_evidence_assertions(self) -> None:
        expected = {
            "K20.1": "a delegation that reaches further",
            "K20.2": "the managed identity",
            "K20.3": "the service wears a person",
        }
        methods = set()
        lines = set()
        for card_id, label in expected.items():
            entry = self.registry["cards"][card_id]["black_box_assertion"]
            match = entry["matches"][0]
            self.assertIn(label, match["subtest"].lower())
            self.assertTrue(match["assertions"])
            methods.add(match["test_method"])
            lines.add(match["line"])
        self.assertEqual(methods, {"test_k19_archive_delegation"})
        self.assertEqual(len(lines), 3)

    def test_accepting_components_do_not_masquerade_as_independent_evidence_owners(self) -> None:
        for card_id, entry in self.registry["cards"].items():
            with self.subTest(card_id=card_id):
                self.assertEqual(
                    entry["evidence_ownership_status"],
                    "independent_range_evaluator",
                )
                evaluator = entry["completion_evaluator"]
                self.assertEqual(evaluator["owner"], coverage.SCORER_OWNER)
                self.assertNotIn(evaluator["owner"], entry["accepting_components"])
                self.assertEqual(
                    evaluator["scorer_path"],
                    f"/v1/objectives/{card_id.lower()}/verify",
                )
                self.assertEqual(
                    evaluator["catalog_revision"],
                    self.registry["delivery_catalog"]["revision"],
                )
                self.assertTrue(entry["evidence_sources"])
                self.assertTrue(evaluator["assertions"])
                self.assertFalse(entry["evidence_contract"]["participant_can_mark_complete"])
                self.assertFalse(entry["evidence_contract"]["accepting_component_can_mark_complete"])
                expected_rule = f"fact-{card_id.lower().replace('.', '-')}"
                self.assertEqual(evaluator["observation_rule"], expected_rule)
        self.assertEqual(self.report["summary"]["independent_evidence_card_count"], 240)
        self.assertGreater(self.report["summary"]["state_change_card_count"], 0)
        self.assertEqual(
            self.report["summary"]["state_change_card_count"],
            self.report["summary"]["independently_evaluated_state_change_card_count"],
        )
        findings = [
            item for item in self.report["findings"]
            if item["kind"] == "evidence_owner_not_independent"
        ]
        self.assertEqual(findings, [])
        self.assertEqual(len(self.report["operations"]), 70)
        self.assertTrue(all(row["status"] == "complete" for row in self.report["operations"]))

    def test_every_syntax_simple_read_has_a_reviewed_interpretive_achievement(self) -> None:
        candidates = {
            card_id for card_id, matches in coverage.subtest_inventory().items()
            if len(matches) == 1 and matches[0]["simple_read_candidate"]
        }
        self.assertEqual(candidates, set(coverage.read_only_reviews()))
        for card_id in candidates:
            with self.subTest(card_id=card_id):
                review = self.registry["cards"][card_id]["read_only_review"]
                self.assertEqual(review["status"], "substantive_interpretation")
                self.assertGreaterEqual(len(review["rationale"].split()), 12)
        self.assertEqual(
            self.registry["cards"]["T04.1"]["read_only_review"]["status"],
            "not_simple_read",
        )
        findings = {
            item["card_id"]
            for item in self.report["findings"]
            if item["kind"] == "simple_read_without_substantive_interpretation"
        }
        self.assertEqual(findings, set())
        self.assertEqual(self.report["summary"]["unresolved_simple_read_card_count"], 0)

    def test_every_card_documents_the_architecture_deletion_test(self) -> None:
        for card_id, entry in self.registry["cards"].items():
            with self.subTest(card_id=card_id):
                deletion = entry["deletion_test"]
                self.assertEqual(deletion["status"], "documented")
                self.assertTrue(deletion["removed_capability"])
                self.assertTrue(deletion["removed_outcome"])
        self.assertEqual(self.report["summary"]["documented_deletion_test_count"], 240)

    def test_delivery_catalog_has_exact_registry_coverage(self) -> None:
        self.assertEqual(coverage.delivered_cards(), set(self.registry["cards"]))
        self.assertFalse(any(
            item["kind"] == "delivery_catalog_mismatch"
            for item in self.report["findings"]
        ))
        self.assertEqual(self.report["summary"]["delivered_card_count"], 240)
        self.assertEqual(self.report["summary"]["missing_delivery_card_count"], 0)
        self.assertEqual(self.report["summary"]["extra_delivery_card_count"], 0)
        self.assertEqual(self.report["overall_status"], "complete")

    def test_delivery_catalog_rejects_duplicate_and_invalid_card_ids(self) -> None:
        import yaml

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "challenges.yaml"
            value = copy.deepcopy(coverage.delivery_catalog())
            value["phases"]["training"]["operations"][0]["cards"].append(
                copy.deepcopy(value["phases"]["training"]["operations"][0]["cards"][0])
            )
            path.write_text(yaml.safe_dump(value, sort_keys=False))
            with self.assertRaisesRegex(coverage.CoverageError, "duplicate|allocation"):
                coverage.delivered_cards(path)
            value = copy.deepcopy(coverage.delivery_catalog())
            value["phases"]["training"]["operations"][0]["cards"][0]["id"] = "X01.1"
            path.write_text(yaml.safe_dump(value, sort_keys=False))
            with self.assertRaisesRegex(coverage.CoverageError, "invalid"):
                coverage.delivered_cards(path)

    def test_score_hint_and_allocation_drift_is_rejected(self) -> None:
        base = coverage.delivery_catalog()
        mutations = []
        changed = copy.deepcopy(base)
        changed["phases"]["training"]["operations"][0]["cards"][0]["points"] += 1
        mutations.append(changed)
        changed = copy.deepcopy(base)
        changed["scoring"]["hint_policy"]["penalty"] = 1
        mutations.append(changed)
        changed = copy.deepcopy(base)
        changed["phases"]["training"]["operations"][0]["allocation"]["easy"] -= 1
        mutations.append(changed)
        for value in mutations:
            with self.subTest(mutation=value):
                with self.assertRaises(ValueError):
                    coverage.catalog_module.validate_catalog(value)

    def test_prerequisite_source_change_changes_catalog_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "challenge-dependencies.json"
            path.write_text('{"value": 1}\n')
            before = coverage.catalog_module.source_revision([path])
            path.write_text('{"value": 2}\n')
            after = coverage.catalog_module.source_revision([path])
        self.assertNotEqual(before, after)

    def test_missing_extra_or_changed_registry_entries_fail_validation(self) -> None:
        missing = copy.deepcopy(self.registry)
        missing["cards"].pop("K20.3")
        with self.assertRaisesRegex(coverage.CoverageError, "registry card IDs changed"):
            coverage.validate_registry(missing)

        changed = copy.deepcopy(self.registry)
        changed["cards"]["K20.3"]["black_box_assertion"]["status"] = "missing"
        with self.assertRaisesRegex(coverage.CoverageError, "black-box assertion inventory changed"):
            coverage.validate_registry(changed)

        drifted = copy.deepcopy(self.registry)
        drifted["cards"]["K20.3"]["sources"]["operation_sha256"] = "0" * 64
        with self.assertRaisesRegex(coverage.CoverageError, "contract changed"):
            coverage.validate_registry(drifted)

        delivery_drift = copy.deepcopy(self.registry)
        delivery_drift["delivery_catalog"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(coverage.CoverageError, "delivery catalog changed"):
            coverage.validate_registry(delivery_drift)

    def test_registry_contains_references_not_request_values(self) -> None:
        prohibited = {"request_body", "response_body", "headers", "cookie", "bearer", "secret_value"}

        def keys(value: object) -> set[str]:
            if isinstance(value, dict):
                nested = set().union(*(keys(item) for item in value.values()), set())
                return set(value) | nested
            if isinstance(value, list):
                return set().union(*(keys(item) for item in value), set())
            return set()

        self.assertFalse(prohibited & keys(self.registry))

    def test_operator_registry_is_not_copied_or_mounted_into_scenario_images(self) -> None:
        image_inputs = list((ROOT / "build").glob("**/*.Dockerfile"))
        image_inputs.extend((ROOT / "build").glob("**/compose.y*ml"))
        self.assertTrue(image_inputs)
        for path in image_inputs:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn("card-coverage", path.read_text(encoding="utf-8"))

    def test_machine_readable_schemas_are_present(self) -> None:
        root = ROOT / "build" / "card-coverage"
        for name in (
            "registry.schema.json", "report.schema.json", "read-only-reviews.schema.json",
        ):
            value = json.loads((root / name).read_text())
            self.assertEqual(value["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertIn("$id", value)

    def test_release_form_passes_only_when_coverage_is_complete(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(COVERAGE_PATH), "--require-complete"],
            text=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_phase_deployment_file_sets_pass_selected_coverage(self) -> None:
        for phase in coverage.ALL_PHASES:
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                isolated_root = Path(directory)
                for relative in release_manifest.phase_files(phase):
                    source = ROOT / relative
                    destination = isolated_root / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                for absent in set(coverage.ALL_PHASES) - {phase}:
                    self.assertFalse((isolated_root / "build" / absent / "runtime").exists())
                report = isolated_root / "coverage.json"
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(isolated_root / "build/card-coverage/coverage.py"),
                        "--phase", phase, "--require-complete", "--output", str(report),
                    ],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                value = json.loads(report.read_text())
                self.assertEqual({card["phase"] for card in value["cards"]}, {phase})

    def test_phase_validation_detects_selected_mutation_only(self) -> None:
        selected = copy.deepcopy(self.registry)
        selected["cards"]["T01.1"]["title"] += " changed"
        with self.assertRaisesRegex(coverage.CoverageError, "reviewed generated form"):
            coverage.validate_registry(selected, ("training",))

        absent = copy.deepcopy(self.registry)
        absent["cards"]["W01.1"]["title"] += " changed"
        coverage.validate_registry(absent, ("training",))
        with self.assertRaisesRegex(coverage.CoverageError, "reviewed generated form"):
            coverage.validate_registry(absent)

    def test_every_authoritative_source_class_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "cinder-typhoon"
            shutil.copytree(ROOT, copied, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            gate = copied / "build" / "card-coverage" / "coverage.py"
            mutations = {
                "sdl": copied / "sdl" / "modules" / "operations" / "t01.yaml",
                "brief": copied / "docs" / "design" / "challenges" / "T01" / "T01.1.md",
                "dependencies": copied / "docs" / "design" / "challenge-dependencies.json",
                "known_solution": copied / "build" / "training" / "tests" / "test_known_solution_live.py",
                "delivery_catalog": copied / "challenges" / "challenges.yaml",
                "native_projection": copied / "ctfd" / "import_catalog.py",
                "read_only_review": copied / "build" / "card-coverage" / "read-only-reviews.json",
            }
            for source_kind, path in mutations.items():
                with self.subTest(source_kind=source_kind):
                    original = path.read_text(encoding="utf-8")
                    if source_kind == "known_solution":
                        changed = original.replace('challenge="T01.1"', 'challenge="T01.9"', 1)
                        self.assertNotEqual(changed, original)
                    elif source_kind == "native_projection":
                        changed = original.replace('"method": "POST"', '"method": "GET"', 1)
                        self.assertNotEqual(changed, original)
                    else:
                        changed = original + "\n"
                    path.write_text(changed, encoding="utf-8")
                    try:
                        completed = subprocess.run(
                            [sys.executable, str(gate), "--require-complete"],
                            cwd=copied, text=True, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, check=False,
                        )
                        self.assertNotEqual(completed.returncode, 0, source_kind)
                    finally:
                        path.write_text(original, encoding="utf-8")

    def test_complete_gate_is_required_by_pack_and_candidate_checks(self) -> None:
        compatibility = (ROOT / "pack.compatibility.yaml").read_text(encoding="utf-8")
        self.assertIn("python3 build/card-coverage/coverage.py --require-complete", compatibility)
        candidate = (ROOT / "build" / "participant-runner" / "check-candidate.sh").read_text(
            encoding="utf-8",
        )
        self.assertIn(
            "card-coverage/coverage.py --phase '$phase' --require-complete",
            candidate,
        )


if __name__ == "__main__":
    unittest.main()
