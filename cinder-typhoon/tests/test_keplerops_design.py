"""Focused negative tests for the static KeplerOps design gate."""
import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from raes.parser import parse_sdl_file

PACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK / "docs/design"))

from validate_challenges import DesignError  # noqa: E402
from validate_keplerops import (  # noqa: E402
    FORBIDDEN_IN_WORLD, check_actions_and_evidence, check_client_reference_graph,
    check_fixture_contracts, check_keplerops, check_native_semantics,
    check_opening_assets, check_opening_interface_contract, check_world, matrix_rows,
    validate_exact_archive, validate_k28_manifest, validate_opening_interface_contract,
)


def write_exact_archive(path, payload=b"reviewed artifact", mode=0o640,
                        owner="fieldkest", group="fieldkest"):
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
        member = tarfile.TarInfo("state/reviewed.bin")
        member.size = len(payload)
        member.mode = mode
        member.mtime = 1789729200
        member.uid = member.gid = 1000
        member.uname = owner
        member.gname = group
        archive.addfile(member, io.BytesIO(payload))
    archive_bytes = path.read_bytes()
    return {
        "archive": path.name,
        "sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "size": len(archive_bytes),
        "owner": owner,
        "group": group,
        "files": [{
            "path": "state/reviewed.bin",
            "mode": f"{mode:04o}",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
        }],
    }


class KeplerOpsDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = parse_sdl_file(
            PACK / "sdl/cinder-typhoon.sdl.yaml", skip_semantic_validation=True
        )
        cls.rows = matrix_rows()

    def expect(self, message, function, scenario):
        with self.assertRaisesRegex(DesignError, message):
            function(scenario, self.rows)

    def test_authored_hand_build_gate(self):
        self.assertEqual(check_keplerops(self.scenario), 104)

    def test_exact_archive_mutations_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "baseline.tar"

            baseline = write_exact_archive(path)
            validate_exact_archive(root, baseline, "Test")

            cases = []
            path = root / "member.tar"
            baseline = write_exact_archive(path)
            mutated = write_exact_archive(path, payload=b"tampered artifact")
            record = deepcopy(baseline)
            record.update({key: mutated[key] for key in ("sha256", "size")})
            cases.append(("member bytes", record, "member drift"))

            path = root / "mode.tar"
            baseline = write_exact_archive(path)
            mutated = write_exact_archive(path, mode=0o600)
            record = deepcopy(baseline)
            record.update({key: mutated[key] for key in ("sha256", "size")})
            cases.append(("member mode", record, "member drift"))

            path = root / "digest.tar"
            baseline = write_exact_archive(path)
            record = deepcopy(baseline)
            record["files"][0]["sha256"] = "0" * 64
            cases.append(("member digest", record, "member drift"))

            path = root / "ownership.tar"
            baseline = write_exact_archive(path)
            mutated = write_exact_archive(path, owner="other")
            record = deepcopy(baseline)
            record.update({key: mutated[key] for key in ("sha256", "size")})
            cases.append(("member ownership", record, "ownership drift"))

            for name, record, error in cases:
                with self.subTest(name=name), self.assertRaisesRegex(DesignError, error):
                    validate_exact_archive(root, record, "Test")

    def test_exact_archive_source_revision_mutation_is_rejected(self):
        scenario = self.scenario.model_copy(deep=True)
        content = scenario.content["keplerops-opening-k-dev.opening-k-dev-home"]
        content.source.artifact_requirement.exact_artifact.version = "2026-09-19"
        with self.assertRaisesRegex(DesignError, "source revision drift"):
            check_opening_assets(scenario)

    def test_k28_manifest_required_field_mutation_is_rejected(self):
        manifest = json.loads(
            (PACK / "assets/keplerops/connector-archive/artifact-manifest.json").read_text()
        )
        manifest.pop("binary")
        with self.assertRaisesRegex(DesignError, "required fields drift"):
            validate_k28_manifest(manifest)

    def test_missing_fixture_is_rejected(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.content.pop("keplerops-k-indexer.k04-1-a-bundle-with-consequences")
        self.expect("fixture inventory drift", check_fixture_contracts, scenario)

    def test_fixture_cannot_move_to_another_node(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.content["keplerops-k-indexer.k04-1-a-bundle-with-consequences"].target = "k-corporate.k-dev"
        self.expect("fixture ownership drift", check_fixture_contracts, scenario)

    def test_generation_input_digest_is_checked(self):
        scenario = self.scenario.model_copy(deep=True)
        item = scenario.content["keplerops-k-data.k30-2-the-database-you-cannot-reach"]
        item.text = item.text.replace("BAK-2026-021", "BAK-2026-099", 1)
        self.expect("fixture text drift", check_fixture_contracts, scenario)

    def test_exploit_critical_profile_cannot_be_generic(self):
        scenario = self.scenario.model_copy(deep=True)
        item = scenario.content["keplerops-k-source.k28-2-what-the-loader-changes"]
        item.text = item.text.replace("AES-256-GCM", "unspecified cipher", 1)
        self.expect("fixture text drift", check_fixture_contracts, scenario)

    def test_action_must_reference_its_fixture(self):
        scenario = self.scenario.model_copy(deep=True)
        condition = next(
            value for value in scenario.action_contracts["k11.c2"].preconditions
            if value.precondition_id == "normal-surface"
        )
        condition.support_refs = [ref for ref in condition.support_refs if not ref.startswith("content.")]
        self.expect("not bound to its owned fixture", check_actions_and_evidence, scenario)

    def test_completion_must_remain_observed(self):
        scenario = self.scenario.model_copy(deep=True)
        proposition = scenario.propositions["k22.c3"]
        proposition.basis = type(proposition.basis).DECLARED_STATE
        self.expect("not independently observed", check_actions_and_evidence, scenario)

    def test_evidence_selector_must_keep_exact_sources(self):
        scenario = self.scenario.model_copy(deep=True)
        selector = scenario.evidence_requirements["k26.c2"].observation_demand.selector
        selector.component_refs = tuple()
        self.expect("not bound to its native source", check_actions_and_evidence, scenario)

    def test_private_relationship_semantics_are_rejected(self):
        scenario = self.scenario.model_copy(deep=True)
        relation = scenario.relationships["keplerops-integrations.source-build"]
        relation.properties["cinder_kind"] = "flow"
        with self.assertRaisesRegex(DesignError, "private semantic properties"):
            check_native_semantics(scenario)

    def test_address_plan_is_exact(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.nodes["k-cloud.k-data"].runtime.network.endpoints[0].ip_address = "10.77.52.99"
        with self.assertRaisesRegex(DesignError, "Address-plan drift"):
            check_world(scenario)

    def test_supplied_developer_identity_is_exercisable(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.agents["participant.operator"].interactive_access.pop("developer")
        with self.assertRaisesRegex(DesignError, "developer session is not exercisable"):
            check_world(scenario)

    def test_customer_boundary_cannot_expand_silently(self):
        scenario = self.scenario.model_copy(deep=True)
        route = deepcopy(scenario.nodes["a-corporate.a-connector"].runtime.applications[0].routes[0])
        route.route_id = "general-customer-admin"
        scenario.nodes["a-corporate.a-connector"].runtime.applications[0].routes.append(route)
        with self.assertRaisesRegex(DesignError, "boundary route drift"):
            check_world(scenario)

    def test_fourth_wall_vocabulary_is_denied_for_in_world_text(self):
        for text in ("submit the flag", "open the next hint", "the score increases", "CTF task"):
            with self.subTest(text=text):
                self.assertIsNotNone(FORBIDDEN_IN_WORLD.search(text))

    def test_client_reference_graph_passes(self):
        check_client_reference_graph(self.scenario)

    def test_opening_interface_contract_passes(self):
        check_opening_interface_contract()

    def test_opening_interface_contract_rejects_an_exercise_route(self):
        design = PACK / "docs/design"
        contract = json.loads((design / "keplerops-k01-k12-interfaces.json").read_text())
        inventory = json.loads(
            (PACK / "build/keplerops/authoring/client_documents.json").read_text()
        )
        known_solution = (
            PACK / "build/keplerops/tests/test_known_solution_live.py"
        ).read_text()
        source = deepcopy(inventory)
        route = next(
            route
            for route in source["documents"]["source.keplerops.test"]["routes"]
            if route["key"] == "source.policy-evaluate"
        )
        route["template"] = "https://source.keplerops.test/api/exercises/policy-compiler/evaluate"
        with self.assertRaisesRegex(DesignError, "challenge-only route"):
            validate_opening_interface_contract(contract, source, known_solution)

    def test_opening_interface_contract_rejects_unpromised_reproducer(self):
        design = PACK / "docs/design"
        contract = json.loads((design / "keplerops-k01-k12-interfaces.json").read_text())
        inventory = json.loads(
            (PACK / "build/keplerops/authoring/client_documents.json").read_text()
        )
        known_solution = (
            PACK / "build/keplerops/tests/test_known_solution_live.py"
        ).read_text()
        mutant = deepcopy(contract)
        operation = next(item for item in mutant["operations"] if item["operation"] == "K08")
        operation["supplied_source_or_reproducer"] = {
            "kind": "source",
            "path": "answers/checker.py",
            "design_promise": "not promised",
        }
        with self.assertRaisesRegex(DesignError, "interface invariants drift"):
            validate_opening_interface_contract(mutant, inventory, known_solution)

    def test_service_catalog_absent_from_opening_assets_raises(self):
        from validate_keplerops import OPENING_ASSETS
        manifest_path = OPENING_ASSETS / "archive-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for archive_record in manifest["archives"]:
            for file_entry in archive_record.get("files", []):
                self.assertNotIn(
                    "service-catalog", file_entry["path"],
                    f"service-catalog.md found in archive: {archive_record['archive']}",
                )


if __name__ == "__main__":
    unittest.main()
