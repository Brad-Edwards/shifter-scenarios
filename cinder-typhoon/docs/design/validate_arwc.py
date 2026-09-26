#!/usr/bin/env python3
"""Focused legal-native hand-build gate for the ARWC design tranche."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import sys

import yaml
from raes.parser import parse_sdl_file

DESIGN = Path(__file__).resolve().parent
PACK = DESIGN.parents[1]
sys.path.insert(0, str(DESIGN))

from generate_arwc_design import (  # noqa: E402
    ADDRESS, APPLICATION, AUTH, BASE_PATH, INITIAL, MATRIX, MECHANIC_KIND,
    NAMESPACE, NARRATIVE_REUSE, NODE_FOR_CARD, PROCESS_REFS, WORLD_NODES,
    card_targets, content_ref, difficulty, fixture_text, node_ref,
    surface_bindings, target_nodes, title_and_path,
)
from validate_challenges import DesignError, Graph, canonical, load_briefs, read_json, require  # noqa: E402

EXPECTED_TIERS = Counter({"Medium": 45, "Hard": 31, "Easy": 23, "Expert": 18, "Elite": 3})
TECHNICAL_SECTIONS = (
    "Surface and normal behavior", "Vulnerability and intended solution",
    "Evidence and completion", "Boundaries and persistence", "Author checks",
)
FORBIDDEN_PRIVATE_KEYS = {"cinder_kind", "flow_kind", "context_kind", "modes", "guard"}
FORBIDDEN_VISIBLE = re.compile(r"\b(?:ctf|flags?|hints?|scores?|scoring|player|challenge)\b", re.I)
FORBIDDEN_SERVICE_META = re.compile(
    r"\b(?:ctf|flags?|hints?|scores?|scoring|player|challenge|difficulty|hand[- ]build|fictional)\b", re.I
)
EXPECTED_INTEGRATIONS = {
    "connector-workplace", "workplace-planning", "workplace-identity", "workplace-archive",
    "planning-archive", "planning-integration", "contractor-field-gateway", "approval-renderer",
    "renderer-control-issuer", "integration-historian", "contractor-historian", "control-broker-hmi",
    "hmi-reservoir", "hmi-distribution", "reservoir-instruments", "instruments-historian",
    "historian-hmi", "engineering-historian", "engineering-diagnostics",
    "engineering-control-issuer", "diagnostics-estimate-publication",
}
NARRATIVE_PACKAGE = PACK / "assets/narrative/generated/packages/arwc-documents.json"


def enum(value):
    return getattr(value, "value", value)


def card_key(card: str) -> str:
    operation, number = card.lower().split(".")
    return f"{operation}.c{number}"


def matrix_rows() -> dict[str, list[str]]:
    rows = {}
    pattern = re.compile(r"^\| (W\d{2}\.\d) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|$", re.M)
    for match in pattern.finditer(MATRIX.read_text()):
        rows[match.group(1)] = list(match.groups()[1:])
    require(set(rows) == set(NODE_FOR_CARD), "ARWC ownership matrix/card inventory drift")
    return rows


def _fact(scenario, assertion_ref: str) -> str:
    assertion = scenario.assertions[assertion_ref]
    proposition = scenario.propositions[assertion.proposition]
    prefix = "urn:cinder-typhoon:fact:"
    require(proposition.predicate.semantic_ref.startswith(prefix), f"Unknown prerequisite fact: {assertion_ref}")
    return proposition.predicate.semantic_ref.removeprefix(prefix)


def workflow_groups(scenario, key: str) -> list[list[str]]:
    workflow = scenario.workflows[key]
    branch = workflow.steps.get("requirements")
    if branch is None:
        return [[]]
    require(enum(branch.type) == "switch" and branch.default_step == "unavailable",
            f"ARWC workflow can bypass requirements: {key}")
    groups = []
    for case in branch.cases:
        require(case.when.assertions and not case.when.objectives and not case.when.steps,
                f"Unsupported ARWC prerequisite predicate: {key}")
        groups.append([_fact(scenario, ref) for ref in case.when.assertions])
    return groups


def check_portfolio(scenario) -> None:
    briefs = load_briefs()
    cards = {ident: brief for ident, brief in briefs.items() if ident.startswith("W")}
    require(set(cards) == set(NODE_FOR_CARD), "ARWC brief/generator inventory drift")
    require(all(brief["status"] == "Technical draft" for brief in cards.values()),
            "Every ARWC card must be a technical draft")
    require(Counter(brief["tier_name"] for brief in cards.values()) == EXPECTED_TIERS,
            "ARWC difficulty distribution drift")
    expected_graph = Graph(read_json(DESIGN / "challenge-dependencies.json"), briefs)
    for card, brief in cards.items():
        key = card_key(card)
        require(key in scenario.objectives and key in scenario.workflows, f"Missing ARWC objective/workflow: {card}")
        require(canonical(workflow_groups(scenario, key)) == canonical(expected_graph.edges[card]),
                f"ARWC prerequisite drift: {card}")
        text = brief["text"]
        for heading in TECHNICAL_SECTIONS:
            matches = re.findall(rf"^### {re.escape(heading)}\n(.*?)(?=^### |^## |\Z)", text, re.M | re.S)
            require(len(matches) == 1 and matches[0].strip(), f"Missing ARWC technical section: {card}/{heading}")
        visible = re.search(r"^## Challenge description — player-facing\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        require(visible and not FORBIDDEN_VISIBLE.search(visible.group(1)),
                f"Fourth-wall vocabulary in ARWC visible brief: {card}")
        if brief["tier_name"] in {"Hard", "Expert", "Elite"}:
            require(card in MECHANIC_KIND, f"Complex ARWC card lacks an exact mechanic: {card}")


def check_fixture_contracts(scenario) -> None:
    rows = matrix_rows()
    fixtures = {name for name, item in scenario.content.items()
                if "service-contract" in item.tags and "arwc" in item.tags}
    expected = {content_ref(card).removeprefix("content.") for card in NODE_FOR_CARD}
    require(fixtures == expected, f"ARWC fixture inventory drift: expected {len(expected)}, got {len(fixtures)}")
    paths = set()
    for card in NODE_FOR_CARD:
        ref = content_ref(card).removeprefix("content.")
        item = scenario.content[ref]
        title, _ = title_and_path(card)
        node = NODE_FOR_CARD[card]
        expected_path = f"{BASE_PATH[node]}/contracts/{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:72].rstrip('-')}.yaml"
        require(enum(item.type) == "file" and item.target == node_ref(node) and item.path == expected_path
                and item.sensitive, f"ARWC fixture ownership drift: {card}")
        require(item.path not in paths, f"Duplicate ARWC fixture path: {item.path}")
        paths.add(item.path)
        require(item.text == fixture_text(card), f"ARWC fixture text drift: {card}")
        payload = yaml.safe_load(item.text)
        required = {
            "schema", "record_key", "owner", "surface_bindings", "starting_state", "narrative_reuse",
            "process_contract_refs", "mechanic_profile", "request_contract", "denial_contract",
            "transition_contract", "evidence_contract", "state_rules", "generation_input",
        }
        require(set(payload) == required, f"Incomplete ARWC fixture schema: {card}")
        generation = payload.pop("generation_input")
        canonical_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        require(generation["digest"] == hashlib.sha256(canonical_payload).hexdigest(),
                f"ARWC fixture digest drift: {card}")
        require(payload["surface_bindings"] == surface_bindings(card), f"ARWC surface binding drift: {card}")
        require(payload["process_contract_refs"] == PROCESS_REFS.get(card, []), f"Process reference drift: {card}")
        require(payload["narrative_reuse"] == NARRATIVE_REUSE.get(card, []), f"Narrative reference drift: {card}")
        require(not FORBIDDEN_SERVICE_META.search(item.text),
                f"Fourth-wall vocabulary in ARWC service content: {card}")
        if difficulty(card) in {"Hard", "Expert", "Elite"}:
            require(payload["mechanic_profile"]["kind"] == MECHANIC_KIND[card]
                    and payload["mechanic_profile"]["behavior_contract"],
                    f"Complex mechanic profile drift: {card}")
        for binding in payload["surface_bindings"]:
            owner, surface = binding.split("/", 1)
            require(owner in scenario.nodes, f"Unknown ARWC surface node: {card}/{binding}")
            runtime = scenario.nodes[owner].runtime
            if surface.startswith("filesystem:"):
                path = surface.removeprefix("filesystem:")
                roots = [entry.path.rstrip("/") for entry in runtime.filesystem_inventory]
                require(any(path == root or path.startswith(root + "/") for root in roots),
                        f"Uninventoried ARWC filesystem surface: {card}/{binding}")
            else:
                application_id, route_id = surface.split("/", 1)
                apps = {application.application_id: application for application in runtime.applications}
                require(application_id in apps and route_id in {route.route_id for route in apps[application_id].routes},
                        f"Unknown ARWC route binding: {card}/{binding}")
    require(len(rows) == 120, "ARWC ownership matrix is incomplete")


def check_narrative_reuse() -> None:
    package = json.loads(NARRATIVE_PACKAGE.read_text())
    names = {document["name"] for document in package["documents"]}
    for card, refs in NARRATIVE_REUSE.items():
        for ref in refs:
            package_name, name = ref.split(":", 1)
            require(package_name == "arwc-documents" and name in names,
                    f"Unknown exact narrative reuse: {card}/{ref}")


def check_world(scenario) -> None:
    for node, address in ADDRESS.items():
        ref = node_ref(node)
        require(ref in scenario.nodes, f"Missing ARWC system: {ref}")
        runtime = scenario.nodes[ref].runtime
        require(runtime and runtime.network and runtime.filesystem_inventory and runtime.local_identity
                and runtime.service_listeners and runtime.applications and runtime.app_authorizations
                and runtime.software_components, f"Incomplete ARWC runtime: {ref}")
        endpoints = runtime.network.endpoints
        require(len(endpoints) == 1 and endpoints[0].ip_address == address
                and endpoints[0].network == f"{NAMESPACE[node]}.subnet",
                f"ARWC address-plan drift: {ref}")
        apps = {app.application_id: app for app in runtime.applications}
        require(APPLICATION[node] in apps and apps[APPLICATION[node]].routes,
                f"Missing ARWC application routes: {ref}")
        routes = apps[APPLICATION[node]].routes
        require(len({route.path for route in routes}) == len(routes)
                and all(route.path == f"/api/{route.route_id}" for route in routes),
                f"ARWC route binding drift: {ref}")
        require(all(route.responses and route.auth_required and route.session_required
                    for route in routes), f"Incomplete ARWC route contract: {ref}")
    data = scenario.nodes["a-corporate.a-data"].runtime
    require(len(data.database_services) == 1 and data.database_services[0].engine == "postgresql"
            and data.database_services[0].version == "16.4", "Planning database contract drift")
    require(scenario.nodes["a-corporate.a-identity"].runtime.identity_authorities,
            "Corporate identity authority missing")
    require(scenario.nodes["a-dmz.a-control-broker"].runtime.identity_authorities,
            "Control-client issuer missing")


def check_actions_and_evidence(scenario) -> None:
    for card in NODE_FOR_CARD:
        key = card_key(card)
        targets = list(card_targets(card))
        action = scenario.action_contracts[key]
        preconditions = {item.precondition_id: item for item in action.preconditions}
        require({"eligibility", "normal-surface", "scope-and-persistence"} <= set(preconditions),
                f"Incomplete ARWC action preconditions: {card}")
        require(content_ref(card) in preconditions["normal-surface"].support_refs,
                f"ARWC action is not bound to its fixture: {card}")
        require("persist" in preconditions["scope-and-persistence"].description.lower(),
                f"ARWC persistence contract missing: {card}")
        require(action.procedure_basis.strip() and "exact initial state" in action.fidelity_claim.lower(),
                f"ARWC procedure/fidelity contract incomplete: {card}")
        outcome = [effect for effect in action.effects if enum(effect.effect_class) == "intended_effect"]
        evidence_effect = [effect for effect in action.effects if enum(effect.effect_class) == "evidence_effect"]
        require(len(outcome) == 1 and len(evidence_effect) == 1
                and outcome[0].target_refs == targets and evidence_effect[0].target_refs == targets,
                f"ARWC effect ownership drift: {card}")
        evidence = scenario.evidence_requirements[key]
        proposition = scenario.propositions[key]
        require(evidence.source_refs == targets
                and list(evidence.observation_demand.selector.component_refs) == targets,
                f"ARWC evidence source drift: {card}")
        require(proposition.subjects == targets and enum(proposition.basis) == "observed_state"
                and enum(proposition.quantifier) == "all", f"ARWC completion is not independently observed: {card}")


def check_native_semantics(scenario) -> None:
    for key, relationship in scenario.relationships.items():
        forbidden = FORBIDDEN_PRIVATE_KEYS & set(relationship.properties)
        require(not forbidden, f"Private semantic properties remain on relationship {key}: {sorted(forbidden)}")
    arwc_integrations = {
        key.removeprefix("arwc-integrations.") for key in scenario.relationships
        if key.startswith("arwc-integrations.")
    }
    require(arwc_integrations == EXPECTED_INTEGRATIONS, "ARWC native integration inventory drift")
    for key in scenario.relationships:
        if key.startswith("arwc-integrations."):
            relationship = scenario.relationships[key]
            require(enum(relationship.type) == "connects_to" and not relationship.properties,
                    f"ARWC integration is not an ordinary native relationship: {key}")
    for obsolete in (
        "flows-a-corporate.yaml", "flows-a-maintenance.yaml", "flows-a-engineering.yaml",
        "flows-a-dmz.yaml", "flows-a-control.yaml", "contexts.yaml", "relays.yaml",
    ):
        require(not (PACK / "sdl/modules/routes" / obsolete).exists(), f"Obsolete private route module remains: {obsolete}")


def check_process_model(scenario) -> None:
    # Corporate and live consequence arithmetic.
    published, actual, committed = 13.40, 12.40, 12.00
    require(round(published - actual, 2) == 1.00 and round(actual - committed, 2) == 0.40,
            "Corporate reserve reconciliation is inconsistent")
    # Each release profile is a linear ramp, plateau, and linear ramp.  Use
    # trapezoid areas rather than treating the ramp duration as full flow.
    volume = (0.5 * 1.00 * 100 + 1.00 * 900 + 0.5 * 1.00 * 100) / 1000
    after = actual - volume
    shortfall = committed - after
    require((volume, round(after, 2), round(shortfall, 2), round(shortfall * 2400)) == (1.0, 11.4, 0.6, 1440),
            "Live release arithmetic is inconsistent")
    practice_volume = (0.5 * 0.30 * 30 + 0.30 * 70 + 0.5 * 0.30 * 30) / 1000
    commissioning_volume = (0.5 * 0.20 * 20 + 0.20 * 40 + 0.5 * 0.20 * 20) / 1000
    require(round(practice_volume, 3) == 0.030, "Practice movement arithmetic is inconsistent")
    require(round(commissioning_volume, 3) == 0.012,
            "Commissioning-trace arithmetic is inconsistent")

    demand = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45]
    release = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10]
    alternate = [d - r for d, r in zip(demand, release)]
    buffer = 180.0
    states = [buffer]
    for d, r, supply in zip(demand, release, alternate):
        buffer += 300 * (r + supply - d)
        states.append(buffer)
    rehearsal_volume = sum(300 * value for value in release) / 1000
    require(all(120 <= state <= 240 for state in states) and 160 <= states[-1] <= 200,
            "W33 reference buffer violates bounds")
    require(all(abs(release[n] - release[n - 1]) <= 0.10 + 1e-9 for n in range(1, len(release))),
            "W33 reference release violates ramp")
    require(all(0 <= value <= 0.50 for value in alternate) and round(rehearsal_volume, 2) == 0.81,
            "W33 reference schedule is inconsistent")
    require(round((committed - (actual - rehearsal_volume)) * 2400) == 984,
            "W33 rehearsal liability is inconsistent")
    require(round(actual - rehearsal_volume, 2) == 11.59, "W34 independent reserve is inconsistent")

    # ARWC-POL1 is one observation-driven policy evaluated against the full
    # Cartesian product.  This calculation freezes the evaluator semantics and
    # prevents a hand builder from inventing 27 precomputed schedules.
    trajectory_count = 0
    for offset in (-0.05, 0.00, 0.05):
        for gain in (0.98, 1.00, 1.02):
            for delay in (20, 40, 60):
                buffer = 180.0
                states = [buffer]
                alternate_actions = []
                previous = None
                for index, (base_demand, reservoir_action) in enumerate(zip(demand, release)):
                    case_demand = base_demand + offset
                    if index == 0:
                        delayed_buffer = 180.0
                    else:
                        previous_release, previous_alternate, previous_demand = previous
                        delayed_buffer = buffer - delay * (
                            gain * previous_release + previous_alternate - previous_demand
                        )
                    alternate_action = min(0.50, max(
                        0.00,
                        case_demand - reservoir_action + (180.0 - delayed_buffer) / 300,
                    ))
                    buffer += 300 * (gain * reservoir_action + alternate_action - case_demand)
                    states.append(buffer)
                    alternate_actions.append(alternate_action)
                    previous = reservoir_action, alternate_action, case_demand
                actual_volume = sum(300 * gain * value for value in release) / 1000
                require(all(120 <= state <= 240 for state in states)
                        and 160 <= states[-1] <= 200,
                        "ARWC-POL1 trajectory violates buffer bounds")
                require(all(0 <= value <= 0.50 for value in alternate_actions),
                        "ARWC-POL1 trajectory violates alternate-supply bounds")
                require(all(abs(alternate_actions[n] - alternate_actions[n - 1]) <= 0.10 + 1e-9
                            for n in range(1, len(alternate_actions))),
                        "ARWC-POL1 trajectory violates alternate-supply ramp")
                require(0.78 <= actual_volume <= 0.84,
                        "ARWC-POL1 trajectory violates reservoir-volume bounds")
                trajectory_count += 1
    require(trajectory_count == 27, "ARWC-POL1 case inventory is incomplete")

    process_text = (DESIGN / "arwc-process-model.md").read_text()
    for term in (
        "PLAN-CRR-LOSS-1000", "1.00 ML", "11.40 ML", "USD 1,440", "PRACTICE-OG2-07",
        "0.03 ML", "0.012 ML", "REH-SCHED-33", "0.81 ML", "27 Cartesian combinations",
        "USD 984", "REH-REPORT-34", "11.59 ML",
    ):
        require(term in process_text, f"Process-model term missing: {term}")
    w30 = scenario.injects["consequences.reservoir-release"].description
    require(all(term in w30 for term in ("1.00 ML", "11.40 ML", "USD 1,440", "Stage A")),
            "Live consequence contract drift")
    w33_fixed = scenario.injects["consequences.costly-release-rehearsal"].description
    require(all(term in w33_fixed for term in ("REH-SCHED-33", "0.81 ML", "180 m3", "USD 984")),
            "Fixed-schedule rehearsal consequence drift")
    w33_feedback = scenario.injects["consequences.feedback-rehearsal"].description
    require(all(term in w33_feedback for term in ("REH-SCHED-33", "all 27", "No rehearsal value")),
            "Feedback rehearsal consequence drift")
    w34 = scenario.injects["consequences.covered-release-rehearsal"].description
    require(all(term in w34 for term in ("REH-REPORT-34", "13.40 ML", "0.81 ML", "11.59 ML")),
            "Reporting rehearsal consequence drift")
    require(scenario.injects["consequences.reservoir-release"].environment == [
                "nodes.a-control.a-reservoir", "nodes.a-control.a-instruments", "nodes.a-corporate.a-data"],
            "Live consequence ownership drift")
    require("nodes.a-control.a-distribution" in
            scenario.injects["consequences.feedback-rehearsal"].environment,
            "Feedback rehearsal lost distribution-buffer ownership")


def check_arwc(scenario=None) -> int:
    if scenario is None:
        scenario = parse_sdl_file(PACK / "sdl/cinder-typhoon.sdl.yaml")
    check_portfolio(scenario)
    check_fixture_contracts(scenario)
    check_narrative_reuse()
    check_world(scenario)
    check_actions_and_evidence(scenario)
    check_native_semantics(scenario)
    check_process_model(scenario)
    return len(NODE_FOR_CARD)


def main() -> None:
    cards = check_arwc()
    print(f"PASS: ARWC native hand-build design gate ({cards} cards); no materialization was performed")


if __name__ == "__main__":
    try:
        main()
    except DesignError as error:
        raise SystemExit(f"FAIL: {error}")
