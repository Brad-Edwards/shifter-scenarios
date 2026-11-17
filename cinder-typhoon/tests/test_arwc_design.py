"""Focused negative tests for the static ARWC design gate."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

from raes.parser import parse_sdl_file

PACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK / "docs/design"))

from validate_arwc import (  # noqa: E402
    check_actions_and_evidence, check_arwc, check_fixture_contracts,
    check_native_semantics, check_process_model, check_world,
)
from validate_challenges import DesignError  # noqa: E402


class ArwcDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = parse_sdl_file(
            PACK / "sdl/cinder-typhoon.sdl.yaml", skip_semantic_validation=True
        )

    def expect(self, message, function, scenario):
        with self.assertRaisesRegex(DesignError, message):
            function(scenario)

    def test_authored_hand_build_gate(self):
        self.assertEqual(check_arwc(self.scenario), 120)

    def test_missing_fixture_is_rejected(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.content.pop("arwc-a-diagnostics.w24-4-signed-by-someone-who-never-approved-it")
        self.expect("fixture inventory drift", check_fixture_contracts, scenario)

    def test_fixture_cannot_move_to_another_node(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.content["arwc-a-engineering.w28-2-control-with-very-little-room"].target = "a-corporate.a-business"
        self.expect("fixture ownership drift", check_fixture_contracts, scenario)

    def test_fixture_digest_and_exact_mechanic_are_checked(self):
        scenario = self.scenario.model_copy(deep=True)
        item = scenario.content["arwc-a-archive.w16-4-what-the-instrument-remembers"]
        item.text = item.text.replace("32-byte calibration", "unspecified calibration", 1)
        self.expect("fixture text drift", check_fixture_contracts, scenario)

    def test_native_route_binding_must_resolve(self):
        scenario = self.scenario.model_copy(deep=True)
        app = next(
            value for value in scenario.nodes["a-engineering.a-diagnostics"].runtime.applications
            if value.application_id == "diagnostic-services"
        )
        app.routes = [route for route in app.routes if route.route_id != "signed-by-someone-who-never-approved-it"]
        self.expect("Unknown ARWC route binding", check_fixture_contracts, scenario)

    def test_action_must_reference_its_fixture(self):
        scenario = self.scenario.model_copy(deep=True)
        condition = next(
            value for value in scenario.action_contracts["w23.c3"].preconditions
            if value.precondition_id == "normal-surface"
        )
        condition.support_refs = [ref for ref in condition.support_refs if not ref.startswith("content.")]
        self.expect("not bound to its fixture", check_actions_and_evidence, scenario)

    def test_completion_must_remain_observed(self):
        scenario = self.scenario.model_copy(deep=True)
        proposition = scenario.propositions["w30.c2"]
        proposition.basis = type(proposition.basis).DECLARED_STATE
        self.expect("not independently observed", check_actions_and_evidence, scenario)

    def test_live_result_needs_command_and_instrument_sources(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.evidence_requirements["w30.c2"].source_refs = ["features.a-control.a-reservoir"]
        self.expect("evidence source drift", check_actions_and_evidence, scenario)

    def test_private_relationship_semantics_are_rejected(self):
        scenario = self.scenario.model_copy(deep=True)
        relationship = scenario.relationships["arwc-integrations.hmi-reservoir"]
        relationship.properties["cinder_kind"] = "flow"
        self.expect("Private semantic properties", check_native_semantics, scenario)

    def test_address_plan_is_exact(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.nodes["a-control.a-instruments"].runtime.network.endpoints[0].ip_address = "10.77.64.99"
        self.expect("address-plan drift", check_world, scenario)

    def test_planning_database_version_is_exact(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.nodes["a-corporate.a-data"].runtime.database_services[0].version = "latest"
        self.expect("database contract drift", check_world, scenario)

    def test_bounded_operation_quantities_are_exact(self):
        scenario = self.scenario.model_copy(deep=True)
        inject = scenario.injects["consequences.reservoir-release"]
        inject.description = inject.description.replace("0.30 m3/s", "0.40 m3/s")
        self.expect("Bounded operation contract drift", check_process_model, scenario)

    def test_w33_has_no_synthetic_distribution_asset_or_route(self):
        self.assertNotIn("a-control.a-distribution", self.scenario.nodes)
        route_ids = {
            route.route_id
            for node in self.scenario.nodes.values()
            if node.runtime is not None
            for application in node.runtime.applications
            for route in application.routes
        }
        self.assertTrue({
            "a-forecast-you-can-defend", "the-schedule-the-service-accepts",
            "a-release-that-stays-in-the-room", "pressure-without-panic",
        }.isdisjoint(route_ids))

    def test_difficult_mechanics_have_reproducible_contracts(self):
        expected = {
            "arwc-a-engineering.w22-2-the-machine-inside-the-viewer": "Each six-byte instruction",
            "arwc-a-diagnostics.w24-4-signed-by-someone-who-never-approved-it": "inverse(h2-h1,L)",
            "arwc-a-engineering.w28-2-control-with-very-little-room": "rbp-0xd0",
            "arwc-a-diagnostics.w31-2-past-the-parser-s-boundary": "declared_length=0xfe08",
        }
        for content_id, exact_term in expected.items():
            self.assertIn(exact_term, self.scenario.content[content_id].text)

    def test_w33_consequence_separates_measurement_from_projection(self):
        description = self.scenario.injects["consequences.peak-operating-projection"].description
        for term in ("twelve settled", "one-hour", "projected", "separately labelled"):
            self.assertIn(term, description)
        self.assertNotIn("consequences.feedback-rehearsal", self.scenario.injects)
        check_process_model(self.scenario)

    def test_primary_validator_has_no_private_relationship_decoder(self):
        validator = (PACK / "tests/validate_sdl.py").read_text()
        self.assertNotIn("cinder_kind", validator)
        self.assertNotIn("def decode(", validator)


if __name__ == "__main__":
    unittest.main()
