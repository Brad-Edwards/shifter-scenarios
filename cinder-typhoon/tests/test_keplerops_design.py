"""Focused negative tests for the static KeplerOps design gate."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

from raes.parser import parse_sdl_file

PACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK / "docs/design"))

from validate_challenges import DesignError  # noqa: E402
from validate_keplerops import (  # noqa: E402
    FORBIDDEN_IN_WORLD, check_actions_and_evidence, check_fixture_contracts,
    check_keplerops, check_native_semantics, check_world, matrix_rows,
)


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


if __name__ == "__main__":
    unittest.main()
