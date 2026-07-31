"""Mutation tests for ACES-derived KeplerOps proof and telemetry contracts."""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = PACK_ROOT / "validation" / "validate_oracle.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("keplerops_validate_oracle_test", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


class OracleValidationTests(unittest.TestCase):
    def _copy_pack(self) -> Path:
        temporary = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temporary)
        target = temporary / "keplerops-ai"
        shutil.copytree(PACK_ROOT, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        return target

    def _mutate_module(self, root: Path, module: str, mutate) -> list[str]:
        path = root / "sdl" / "modules" / module
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return VALIDATOR.validate_pack(root)

    def _mutate_content(self, root: Path, content_id: str, mutate) -> list[str]:
        path = root / "sdl" / "modules" / "environment.sdl.yaml"
        environment = yaml.safe_load(path.read_text(encoding="utf-8"))
        content = yaml.safe_load(environment["content"][content_id]["text"])
        mutate(content)
        environment["content"][content_id]["text"] = yaml.safe_dump(content, sort_keys=False)
        path.write_text(yaml.safe_dump(environment, sort_keys=False), encoding="utf-8")
        return VALIDATOR.validate_pack(root)

    def assertFailureContains(self, failures: list[str], needle: str) -> None:
        self.assertTrue(any(needle in failure for failure in failures), failures)

    def test_canonical_aces_contracts_pass(self) -> None:
        self.assertEqual(VALIDATOR.validate_pack(PACK_ROOT), [])

    def test_rejects_invalid_proof_freshness(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_module(
            root,
            "module-01-agent-control.sdl.yaml",
            lambda data: data["behavior_specifications"]["kep-m01-a"]["extensions"]
            ["x-keplerops:challenge"]["proof"]["event"].update({"freshness_seconds": 0}),
        )
        self.assertFailureContains(failures, "invalid freshness window")

    def test_rejects_participant_copy_with_hidden_atlas_id(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_module(
            root,
            "module-01-agent-control.sdl.yaml",
            lambda data: data["behavior_specifications"]["kep-m01-a"]["extensions"]
            ["x-keplerops:challenge"]["participant_copy"].update(
                {"question": "Execute AML.T0051.000."}
            ),
        )
        self.assertFailureContains(failures, "exposes oracle vocabulary")

    def test_rejects_flag_evidence_drift(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_module(
            root,
            "module-01-agent-control.sdl.yaml",
            lambda data: data["behavior_specifications"]["kep-m01-a"]["extensions"]
            ["x-keplerops:challenge"]["flag_delivery"].update(
                {"evidence_id": "ev-does-not-exist"}
            ),
        )
        self.assertFailureContains(failures, "ACES proof binding drift")

    def test_rejects_research_operational_content_overlap(self) -> None:
        root = self._copy_pack()

        def mutate(contract) -> None:
            contract["field_policy"]["operational_fields"].append("prompt")

        failures = self._mutate_content(root, "research-telemetry-contract", mutate)
        self.assertFailureContains(failures, "must be disjoint")

    def test_rejects_atlas_catalog_digest_drift(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_content(
            root,
            "atlas-technique-catalog",
            lambda catalog: catalog["technique_catalog"][0].update({"name": "Changed technique"}),
        )
        self.assertFailureContains(failures, "catalog digest drift")

    def test_rejects_unassigned_planned_atlas_technique(self) -> None:
        root = self._copy_pack()

        def remove_planned_assignment(design) -> None:
            row = next(
                item for item in design["challenge_designs"]
                if item.get("implementation_status", "planned") == "planned"
            )
            row["techniques"].pop()

        failures = self._mutate_content(
            root,
            "atlas-challenge-design",
            remove_planned_assignment,
        )
        self.assertFailureContains(failures, "exactly one design binding")

    def test_rejects_overloaded_challenge_without_parent_variant_exception(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_content(
            root,
            "atlas-challenge-design",
            lambda design: design["challenge_designs"][0].update(
                {
                    "techniques": [
                        "AML.T0011",
                        "AML.T0011.000",
                        "AML.T0011.001",
                        "AML.T0011.003",
                    ]
                }
            ),
        )
        self.assertFailureContains(failures, "parent-plus-three exception")

    def test_rejects_pragmatic_verification_policy_drift(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_content(
            root,
            "atlas-challenge-design",
            lambda design: design["design_rules"].update(
                {"repeated_trials": "ten_rounds_for_every_challenge"}
            ),
        )
        self.assertFailureContains(failures, "pragmatic verification policy drift")

    def test_rejects_missing_aces_event_source_service(self) -> None:
        root = self._copy_pack()

        def mutate(policy) -> None:
            policy["supporting_events"][0]["source_service"] = "missing-service"

        failures = self._mutate_content(root, "proof-policy", mutate)
        self.assertFailureContains(failures, "missing ACES source service")

    def test_rejects_implementation_technique_drift(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_module(
            root,
            "module-01-agent-control.sdl.yaml",
            lambda data: data["behavior_specifications"]["kep-m01-a"]["extensions"]
            ["x-keplerops:challenge"]["implementation_evidence"].update(
                {"primary_atlas_techniques": ["AML.T9999"]}
            ),
        )
        self.assertFailureContains(failures, "implementation references missing techniques")


if __name__ == "__main__":
    unittest.main()
