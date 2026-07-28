"""Tests for the KeplerOps AI draft-pack contract validator."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
_PACK = os.path.dirname(os.path.dirname(_HERE))
_VALIDATOR = os.path.join(os.path.dirname(_HERE), "validate_contract.py")


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "keplerops_ai_validate_contract_undertest", _VALIDATOR)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


VALIDATOR = _load_validator()


class KeplerOpsAIContractTest(unittest.TestCase):
    def _copy_pack(self) -> str:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        target = os.path.join(tmp, "keplerops-ai")
        shutil.copytree(
            _PACK,
            target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        return target

    def _load_yaml(self, root: str, rel_path: str):
        with open(os.path.join(root, rel_path), "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def _write_yaml(self, root: str, rel_path: str, body) -> None:
        with open(os.path.join(root, rel_path), "w", encoding="utf-8") as fh:
            yaml.safe_dump(body, fh, sort_keys=False)

    def _read_text(self, root: str, rel_path: str) -> str:
        with open(os.path.join(root, rel_path), "r", encoding="utf-8") as fh:
            return fh.read()

    def _write_text(self, root: str, rel_path: str, body: str) -> None:
        with open(os.path.join(root, rel_path), "w", encoding="utf-8") as fh:
            fh.write(body)

    def _load_json(self, root: str, rel_path: str):
        with open(os.path.join(root, rel_path), "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _write_json(self, root: str, rel_path: str, body) -> None:
        with open(os.path.join(root, rel_path), "w", encoding="utf-8") as fh:
            json.dump(body, fh)

    def _failures_after(self, mutate):
        root = self._copy_pack()
        mutate(root)
        return VALIDATOR.validate_pack(root)

    def assertFailureContains(self, failures, needle: str):
        self.assertTrue(any(needle in failure for failure in failures), failures)

    def test_contract_validator_accepts_pack_design(self):
        self.assertEqual(VALIDATOR.validate_pack(_PACK), [])

    def test_contract_requires_complete_flag_layer(self):
        root = self._copy_pack()
        os.remove(os.path.join(root, "ctfd", "README.md"))

        failures = VALIDATOR.validate_pack(root)

        self.assertFailureContains(failures, "flag layer requires")

    def test_contract_validator_rejects_missing_required_path(self):
        failures = self._failures_after(
            lambda root: os.remove(os.path.join(root, "docs", "concepts.md")))

        self.assertFailureContains(failures, "docs/concepts.md: required path missing")

    def test_contract_validator_rejects_missing_aces_accessor(self):
        failures = self._failures_after(
            lambda root: os.remove(os.path.join(root, "aces_contract.py")))

        self.assertFailureContains(failures, "aces_contract.py: required path missing")

    def test_contract_validator_rejects_wrong_pack_status(self):
        def mutate(root: str) -> None:
            pack = self._load_yaml(root, "pack.yaml")
            pack["status"] = "built"
            self._write_yaml(root, "pack.yaml", pack)

        failures = self._failures_after(mutate)

        self.assertFailureContains(failures, "pack.yaml.status")

    def test_contract_validator_rejects_stale_requirement_metadata(self):
        def mutate(root: str) -> None:
            manifest = self._load_yaml(root, "pack.compatibility.yaml")
            manifest["pack"]["source"]["requirement"] = "END-0001"
            self._write_yaml(root, "pack.compatibility.yaml", manifest)

        failures = self._failures_after(mutate)

        self.assertFailureContains(failures, "source.requirement must be KEP-0001")

    def test_contract_validator_rejects_missing_gcp_profile(self):
        def mutate(root: str) -> None:
            manifest = self._load_yaml(root, "pack.compatibility.yaml")
            manifest["runtime_profiles"] = [
                row for row in manifest["runtime_profiles"]
                if row.get("profile_id") != "gcp_full"
            ]
            self._write_yaml(root, "pack.compatibility.yaml", manifest)

        failures = self._failures_after(mutate)

        self.assertFailureContains(failures, "missing gcp_full runtime profile")

    def test_contract_validator_rejects_missing_required_feature(self):
        def mutate(root: str) -> None:
            manifest = self._load_yaml(root, "pack.compatibility.yaml")
            manifest["platform_features"] = [
                row for row in manifest["platform_features"]
                if row.get("feature_id") != "open-model-hosting"
            ]
            self._write_yaml(root, "pack.compatibility.yaml", manifest)

        failures = self._failures_after(mutate)

        self.assertFailureContains(failures, "missing platform feature open-model-hosting")

    def test_contract_validator_rejects_missing_source_row(self):
        def mutate(root: str) -> None:
            ledger = self._load_yaml(root, "docs/provenance-ledger.yaml")
            ledger["sources"] = [
                row for row in ledger["sources"]
                if row.get("source_id") != "mitre-atlas-data"
            ]
            self._write_yaml(root, "docs/provenance-ledger.yaml", ledger)

        failures = self._failures_after(mutate)

        self.assertFailureContains(failures, "missing source rows")

    def test_contract_validator_rejects_missing_design_anchor(self):
        def mutate(root: str) -> None:
            body = self._read_text(root, "docs/concepts.md")
            self._write_text(
                root,
                "docs/concepts.md",
                body.replace("Enterprise fabric", "Organizational context"),
            )

        failures = self._failures_after(mutate)

        self.assertFailureContains(
            failures, "docs/concepts.md: missing design anchor enterprise fabric")

    def test_contract_validator_rejects_missing_readme_participant_framing(self):
        def mutate(root: str) -> None:
            body = self._read_text(root, "README.md")
            self._write_text(
                root,
                "README.md",
                body.replace(
                    "The participant is the\nadversary:",
                    "The participant enters as the\nrange operator:",
                ),
            )

        failures = self._failures_after(mutate)

        self.assertFailureContains(
            failures, "README.md: must state that the participant is the adversary")

    def test_contract_validator_rejects_missing_attack_path_visibility_marker(self):
        def mutate(root: str) -> None:
            body = self._read_text(root, "docs/attack-path.md")
            self._write_text(
                root,
                "docs/attack-path.md",
                body.replace("Operator/validator only.", "Operator notes."),
            )

        failures = self._failures_after(mutate)

        self.assertFailureContains(
            failures, "docs/attack-path.md: must mark the hidden path operator-only")

    def test_contract_validator_rejects_missing_lineage_source_id(self):
        def mutate(root: str) -> None:
            body = self._read_text(root, "docs/lineage.md")
            self._write_text(
                root,
                "docs/lineage.md",
                body.replace("### `mitre-atlas-data`", "### `atlas-data`"),
            )

        failures = self._failures_after(mutate)

        self.assertFailureContains(
            failures, "docs/lineage.md: missing source id mitre-atlas-data")

    def test_contract_validator_rejects_template_marker_in_docs(self):
        def mutate(root: str) -> None:
            path = os.path.join(root, "docs", "concepts.md")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("\nCopy this directory before use.\n")

        failures = self._failures_after(mutate)

        self.assertFailureContains(failures, "template marker remains")

    def test_contract_validator_rejects_reintroduced_parallel_projection(self):
        def mutate(root: str) -> None:
            path = os.path.join(root, "design", "topology.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("assets: []\n")

        failures = self._failures_after(mutate)

        self.assertFailureContains(
            failures, "design/topology.yaml: redundant projection must not exist"
        )

    def test_contract_validator_rejects_per_range_vpc_capacity(self):
        def mutate(root: str) -> None:
            path = "build/gcp/fleet-capacity-profile.json"
            profile = self._load_json(root, path)
            vpcs = next(
                row for row in profile["resources"] if row["resource"] == "vpc_networks"
            )
            vpcs["basis"] = "total_range"
            self._write_json(root, path, profile)

        failures = self._failures_after(mutate)

        self.assertFailureContains(
            failures,
            "vpc_networks may not scale per range",
        )

    def test_contract_validator_rejects_capacity_model_below_200_ranges(self):
        def mutate(root: str) -> None:
            path = "build/gcp/fleet-capacity-profile.json"
            profile = self._load_json(root, path)
            profile["ranges"]["total"] = 199
            profile["ranges"]["active"] = 199
            profile["ranges"]["simultaneously_busy"] = 199
            self._write_json(root, path, profile)

        failures = self._failures_after(mutate)

        self.assertFailureContains(failures, "total ranges must remain 200")

    def test_contract_validator_rejects_reintroduced_oracle_ledger(self):
        def mutate(root: str) -> None:
            path = os.path.join(root, "oracle", "objectives.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("objectives: []\n")

        failures = self._failures_after(mutate)

        self.assertFailureContains(
            failures, "oracle/objectives.yaml: redundant projection must not exist"
        )

    def test_contract_validator_rejects_missing_sdl_vm(self):
        def mutate(root: str) -> None:
            environment = self._load_yaml(root, "sdl/modules/environment.sdl.yaml")
            environment["nodes"].pop("model-host-01")
            self._write_yaml(root, "sdl/modules/environment.sdl.yaml", environment)

        failures = self._failures_after(mutate)

        self.assertFailureContains(failures, "cannot expand canonical modular SDL")

    def test_contract_validator_rejects_missing_sdl_feature_binding(self):
        def mutate(root: str) -> None:
            environment = self._load_yaml(root, "sdl/modules/environment.sdl.yaml")
            environment["nodes"]["model-host-01"]["features"] = []
            self._write_yaml(root, "sdl/modules/environment.sdl.yaml", environment)

        failures = self._failures_after(mutate)

        self.assertFailureContains(
            failures,
            "every logical workload VM must bind one root SDL feature and all dependencies",
        )

    def test_contract_validator_rejects_reintroduced_software_inventory(self):
        def mutate(root: str) -> None:
            path = os.path.join(root, "build", "gcp", "runtime-images.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("images: []\n")

        failures = self._failures_after(mutate)

        self.assertFailureContains(
            failures, "build/gcp/runtime-images.yaml: redundant projection must not exist"
        )

    def test_contract_validator_rejects_missing_sdl_content(self):
        def mutate(root: str) -> None:
            environment = self._load_yaml(root, "sdl/modules/environment.sdl.yaml")
            environment["content"].pop("briefing-pack")
            environment["module"]["exports"]["content"].remove("briefing-pack")
            self._write_yaml(root, "sdl/modules/environment.sdl.yaml", environment)

        failures = self._failures_after(mutate)

        self.assertFailureContains(
            failures, "incomplete identity or content declarations"
        )


if __name__ == "__main__":
    unittest.main()
