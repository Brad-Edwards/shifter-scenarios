from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import yaml
from raes import parse_sdl_file
from raes_processor.compiler import compile_scenario_runtime_model
from raes_processor.models import resource_payload

PACK_ROOT = Path(__file__).resolve().parents[2]
SDL_ROOT = PACK_ROOT / "sdl/keplerops-ai.sdl.yaml"
CORPUS = PACK_ROOT / "assets/content/company-state/company-state.yaml"
VALIDATOR = PACK_ROOT / "validation/validate_company_state.py"
RENDERER = PACK_ROOT / "build/gcp/render_sdl_realization.py"
EXPECTED_SERVICE_CONTENT = {
    "company-artifact-state",
    "company-data-state",
    "company-directory-state",
    "company-file-state",
    "company-identity-facade-state",
    "company-mail-state",
    "company-model-registry-state",
    "company-notebook-state",
    "company-operational-telemetry",
    "company-policy-state",
    "company-research-index-state",
    "company-workflow-state",
    "company-workhub-state",
}
EXPECTED_ENDPOINT_CONTENT = {
    "company-ml-endpoint-state",
    "company-workforce-endpoint-state",
}


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_company_state", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_renderer():
    spec = importlib.util.spec_from_file_location("render_sdl_realization", RENDERER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompanyStateContractTests(unittest.TestCase):
    def test_corpus_is_coherent_safe_and_deterministic(self) -> None:
        module = load_validator()
        corpus = module.load_corpus(CORPUS)
        report = module.validate_corpus(corpus)
        self.assertGreaterEqual(report["represented_days"], 28)
        self.assertGreaterEqual(report["object_count"], 40)
        self.assertEqual(report["errors"], [])
        canonical = module.canonical_corpus(corpus)
        self.assertEqual(canonical, module.canonical_corpus(corpus))
        self.assertEqual(
            report["canonical_digest"],
            "sha256:" + __import__("hashlib").sha256(canonical).hexdigest(),
        )

    def test_corpus_identities_bind_existing_raes_accounts_and_nodes(self) -> None:
        corpus = yaml.safe_load(CORPUS.read_text(encoding="utf-8"))
        scenario = parse_sdl_file(SDL_ROOT)
        for identity in [*corpus["people"], *corpus["service_identities"]]:
            account = scenario.accounts[identity["account_ref"]]
            self.assertEqual(account.username, identity["username"])
        for endpoint in corpus["endpoints"]:
            node = scenario.nodes[endpoint["node_ref"]]
            self.assertEqual(
                endpoint["hostname"],
                endpoint["node_ref"].removeprefix("core."),
            )
            self.assertEqual(node.os, "windows")

    def test_validator_rejects_broken_references_and_source_digests(self) -> None:
        module = load_validator()
        corpus = module.load_corpus(CORPUS)
        broken_reference = deepcopy(corpus)
        broken_reference["tickets"][0]["assignee_ref"] = "person-missing"
        self.assertTrue(
            any(
                "references missing person-missing" in error
                for error in module.validate_corpus(broken_reference)["errors"]
            )
        )
        broken_digest = deepcopy(corpus)
        broken_digest["datasets"][0]["digest"] = "sha256:" + ("0" * 64)
        self.assertTrue(
            any(
                "digest does not match source bytes" in error
                for error in module.validate_corpus(broken_digest)["errors"]
            )
        )

    def test_validator_rejects_future_references_and_unsafe_source_bytes(self) -> None:
        module = load_validator()
        corpus = module.load_corpus(CORPUS)
        future_reference = deepcopy(corpus)
        future_reference["messages"][0]["sent_at"] = "2026-04-06T09:00:00Z"
        self.assertTrue(
            any(
                "references future commit-eval-schema" in error
                for error in module.validate_corpus(future_reference)["errors"]
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            object_root = Path(directory)
            shutil.copytree(CORPUS.parent / "objects", object_root / "objects")
            unsafe = deepcopy(corpus)
            source = object_root / unsafe["datasets"][0]["source_path"]
            source.write_bytes(
                source.read_bytes()
                + b'{"flag":"FLAG{must-not-enter-company-state}"}\n'
            )
            unsafe["datasets"][0]["digest"] = (
                "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
            )
            self.assertTrue(
                any(
                    "source_path contains prohibited pattern" in error
                    for error in module.validate_corpus(unsafe, object_root)["errors"]
                )
            )

    def test_corpus_has_cross_system_causal_lineage(self) -> None:
        corpus = yaml.safe_load(CORPUS.read_text(encoding="utf-8"))
        self.assertEqual(corpus["schema_version"], 1)
        for section in (
            "people",
            "teams",
            "endpoints",
            "projects",
            "repositories",
            "commits",
            "tickets",
            "messages",
            "files",
            "datasets",
            "experiments",
            "models",
            "artifacts",
            "approvals",
            "releases",
            "operations",
        ):
            self.assertIsInstance(corpus[section], list)
            self.assertTrue(corpus[section], section)
        ticket_ids = {row["id"] for row in corpus["tickets"]}
        commit_ids = {row["id"] for row in corpus["commits"]}
        model_ids = {row["id"] for row in corpus["models"]}
        self.assertTrue(
            any(set(row["ticket_refs"]) & ticket_ids for row in corpus["commits"])
        )
        self.assertTrue(
            any(set(row["commit_refs"]) & commit_ids for row in corpus["messages"])
        )
        self.assertTrue(
            any(row["model_ref"] in model_ids for row in corpus["releases"])
        )

    def test_raes_owns_service_materialization_and_readback(self) -> None:
        scenario = parse_sdl_file(SDL_ROOT)
        report = load_validator().validate_corpus(load_validator().load_corpus(CORPUS))
        content = {
            name.removeprefix("core."): item
            for name, item in scenario.content.items()
            if name.startswith("core.")
        }
        self.assertTrue(EXPECTED_SERVICE_CONTENT.issubset(content))
        self.assertTrue(EXPECTED_ENDPOINT_CONTENT.issubset(content))
        for content_id in EXPECTED_SERVICE_CONTENT:
            self.assertEqual(
                content[content_id].source.version,
                report["canonical_digest"],
            )
            binding = content[content_id].service_materialization
            self.assertIsNotNone(binding, content_id)
            assert binding is not None
            self.assertEqual(binding.interface_profile, "service-content")
            self.assertEqual(binding.profile_version, "1")
            self.assertEqual(binding.requirements.operation, "ensure-owned-items")
            self.assertEqual(
                binding.requirements.conflict_policy,
                "reject-unowned-collision",
            )
            self.assertEqual(
                binding.requirements.readback,
                "canonical-content-digest",
            )
            self.assertEqual(
                binding.readback_assertion_refs,
                ["core.company-state-visible"],
            )
            self.assertEqual(
                binding.evidence_requirement_refs,
                ["core.company-state-readback"],
            )
            self.assertEqual(
                binding.observation_boundary_refs,
                ["core.company-state-view"],
            )
        for content_id in EXPECTED_ENDPOINT_CONTENT:
            self.assertEqual(
                content[content_id].source.version,
                report["canonical_digest"],
            )
            self.assertIsNone(content[content_id].service_materialization)

    def test_raes_compiler_carries_exact_materialization_plan(self) -> None:
        model = compile_scenario_runtime_model(parse_sdl_file(SDL_ROOT))
        placements = {
            address.removeprefix("provision.content.core."): placement
            for address, placement in model.content_placements.items()
            if address.startswith("provision.content.core.")
        }
        self.assertTrue(EXPECTED_SERVICE_CONTENT.issubset(placements))
        for content_id in EXPECTED_SERVICE_CONTENT:
            placement = placements[content_id]
            binding = placement.service_materialization
            self.assertIsNotNone(binding, content_id)
            assert binding is not None
            self.assertTrue(binding.canonical_content_digest.startswith("sha256:"))
            self.assertEqual(
                binding.readback_assertion_addresses,
                ("evaluation.assertion.core.company-state-visible",),
            )
            payload = resource_payload(placement)
            self.assertEqual(
                payload["service_materialization"]["operation"],
                "ensure-owned-items",
            )

    def test_gcp_projection_consumes_compiled_materialization_contract(self) -> None:
        realization = load_renderer().build_realization()
        materializations = realization["service_materializations"]
        self.assertEqual(set(materializations), EXPECTED_SERVICE_CONTENT)
        for content_id, operation in materializations.items():
            with self.subTest(content_id=content_id):
                self.assertEqual(operation["resource_type"], "content-placement")
                binding = operation["payload"]["service_materialization"]
                self.assertEqual(binding["interface_profile"], "service-content")
                self.assertEqual(binding["profile_version"], "1")
                self.assertTrue(
                    binding["canonical_content_digest"].startswith("sha256:")
                )
        self.assertEqual(realization["schema_version"], 3)
        encoded = json.dumps(realization, sort_keys=True)
        self.assertNotIn('"historical"', encoded)


if __name__ == "__main__":
    unittest.main()
