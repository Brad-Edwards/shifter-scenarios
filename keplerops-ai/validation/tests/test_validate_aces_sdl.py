"""Mutation tests for the KeplerOps ACES SDL binding."""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = PACK_ROOT / "validation" / "validate_aces_sdl.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "keplerops_ai_validate_aces_sdl_undertest", VALIDATOR_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


class KeplerOpsAcesSDLTest(unittest.TestCase):
    def _copy_pack(self) -> Path:
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        target = temp / "keplerops-ai"
        shutil.copytree(
            PACK_ROOT,
            target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        return target

    def _mutate_sdl(self, root: Path, relative: str, mutate) -> list[str]:
        path = root / "sdl" / relative
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        mutate(data)
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, sort_keys=False)
        return VALIDATOR.validate_pack(root)

    def assertFailureContains(self, failures: list[str], needle: str) -> None:
        self.assertTrue(any(needle in failure for failure in failures), failures)

    def test_pinned_pypi_package_accepts_canonical_aces_sdl(self) -> None:
        self.assertEqual(VALIDATOR.validate_pack(PACK_ROOT), [])

    def test_live_activity_is_green_non_evaluated_raes_v3(self) -> None:
        scenario = VALIDATOR.parse_sdl_file(PACK_ROOT / "sdl" / "keplerops-ai.sdl.yaml")
        self.assertEqual(len(scenario.behavior_specifications), 145)
        behavior = scenario.behavior_specifications["activity.green-company-live-activity"]
        agent = scenario.agents["activity.green-company-activity"]
        self.assertEqual(scenario.entities[agent.entity].role, "green")
        self.assertEqual(behavior.behavior_mode, "autonomous")
        self.assertEqual(behavior.participant_role_refs, ["green"])
        self.assertEqual(behavior.autonomous_execution.profile, "participant-autonomous-execution/v3")
        self.assertEqual(behavior.autonomous_execution.evaluation_authority.mode, "none")
        self.assertEqual(
            behavior.autonomous_execution.observation_boundary_ref,
            "activity.green-activity-view",
        )
        dimensions = behavior.autonomous_execution.resource_budget.dimensions.values()
        self.assertEqual(
            {dimension.resource_kind.value for dimension in dimensions},
            {
                "action_rate",
                "concurrent_actions",
                "storage_growth",
                "inference_tokens",
                "image_generations",
                "accelerator",
            },
        )
        participant_concurrency = [
            dimension
            for dimension in behavior.autonomous_execution.resource_budget.dimensions.values()
            if dimension.resource_kind.value == "concurrent_actions"
        ]
        self.assertEqual(len(participant_concurrency), 1)
        self.assertEqual(
            participant_concurrency[0].limit,
            behavior.autonomous_execution.max_in_flight,
        )

    def test_rejects_tactic_binding_drift(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_sdl(
            root,
            "modules/module-01-agent-control.sdl.yaml",
            lambda data: data["behavior_specifications"]["module-01-agent-control"].update(
                {"ai_offensive_behavior_refs": ["not-an-atlas-tactic"]}
            ),
        )
        self.assertFailureContains(failures, "not-an-atlas-tactic")

    def test_accepts_conformant_governed_extension(self) -> None:
        root = self._copy_pack()

        def mutate(data) -> None:
            behavior = data["behavior_specifications"]["module-08-model-extraction"]
            behavior["extension_policy"] = "governed-extension"
            behavior["extensions"]["x-keplerops:projection-ref"] = "content.core.atlas-technique-catalog"

        failures = self._mutate_sdl(
            root, "modules/module-08-model-extraction.sdl.yaml", mutate
        )
        self.assertEqual(failures, [])

    def test_rejects_unpinned_requirement(self) -> None:
        root = self._copy_pack()
        (root / "validation" / "requirements.txt").write_text(
            "raes>=2.0.0\n", encoding="utf-8"
        )
        failures = VALIDATOR.validate_pack(root)
        self.assertFailureContains(failures, "expected exactly raes==2.0.0")

    def test_rejects_non_aces_source_in_sdl_directory(self) -> None:
        root = self._copy_pack()
        (root / "sdl" / "local-projection.yaml").write_text(
            "kind: pack-local-projection\n", encoding="utf-8"
        )
        failures = VALIDATOR.validate_pack(root)
        self.assertFailureContains(failures, "only ACES *.sdl.yaml source files")

    def test_rejects_reintroduced_pack_local_software_inventory(self) -> None:
        root = self._copy_pack()
        (root / "build" / "gcp" / "runtime-images.yaml").write_text(
            "images: []\n", encoding="utf-8"
        )
        failures = VALIDATOR.validate_pack(root)
        self.assertFailureContains(
            failures, "redundant non-ACES semantic source must not exist"
        )

    def test_rejects_unimported_aces_module(self) -> None:
        root = self._copy_pack()
        (root / "sdl" / "shared-tools.sdl.yaml").write_text(
            """name: shared-tools
version: 1.0.0
module:
  id: keplerops/shared-tools
  version: 1.0.0
  exports: {}
""",
            encoding="utf-8",
        )
        failures = VALIDATOR.validate_pack(root)
        self.assertFailureContains(failures, "unimported ACES modules")

    def test_rejects_atlas_catalog_with_missing_path_step(self) -> None:
        root = self._copy_pack()
        path = root / "sdl" / "modules" / "environment.sdl.yaml"
        with path.open(encoding="utf-8") as handle:
            environment = yaml.safe_load(handle)
        content = yaml.safe_load(environment["content"]["atlas-technique-catalog"]["text"])
        content["technique_catalog"][0]["challenge_step"] = "99"
        environment["content"]["atlas-technique-catalog"]["text"] = yaml.safe_dump(
            content, sort_keys=False
        )
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(environment, handle, sort_keys=False)
        failures = VALIDATOR.validate_pack(root)
        self.assertFailureContains(failures, "technique references missing step 99")

    def test_rejects_ad_authority_drift(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_sdl(
            root,
            "modules/environment.sdl.yaml",
            lambda data: data["identity_domains"]["keplerops"].update(
                {"dns_name": "example.test"}
            ),
        )
        self.assertFailureContains(failures, "authoritative AD contract is incomplete")

    def test_rejects_domain_join_without_declared_controller(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_sdl(
            root,
            "modules/environment.sdl.yaml",
            lambda data: data["relationships"]["workforce-domain-join"][
                "domain_join"
            ].update({"controller_refs": []}),
        )
        self.assertFailureContains(failures, "controller_refs")

    def test_rejects_duplicate_human_identity_authority(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_sdl(
            root,
            "modules/environment.sdl.yaml",
            lambda data: data["accounts"]["user-release-manager"].pop("domain_ref"),
        )
        self.assertFailureContains(
            failures, "AD authority must cover exactly the declared human workforce identities"
        )

    def test_rejects_packed_workload_outside_shared_carrier_contract(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_sdl(
            root,
            "modules/environment.sdl.yaml",
            lambda data: data["relationships"]["place-policy-lab"][
                "carrier_placement"
            ].update({"kernel_boundary": "separate_kernel"}),
        )
        self.assertFailureContains(failures, "packed Linux estate")

    def test_rejects_unscoped_shared_model_authentication(self) -> None:
        root = self._copy_pack()
        failures = self._mutate_sdl(
            root,
            "modules/environment.sdl.yaml",
            lambda data: data["relationships"]["shared-inference-service"][
                "shared_service"
            ].update({"workload_authentication": "workload_identity"}),
        )
        self.assertFailureContains(
            failures, "requires tenant-scoped workload authentication"
        )


if __name__ == "__main__":
    unittest.main()
