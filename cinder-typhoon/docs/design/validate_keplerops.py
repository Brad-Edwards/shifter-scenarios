#!/usr/bin/env python3
"""Static KeplerOps hand-build readiness gate.

This checker validates authored design and native RAE bindings. It never
materializes a service, repository, package, binary, model, image or range.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile

import yaml

BASE = Path(__file__).resolve().parent
PACK = BASE.parents[1]
TESTS = PACK / "tests"
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(TESTS))

from generate_keplerops_design import (  # noqa: E402
    BASE_PATH, JOINED_FEATURES, MECHANIC_PROFILE, NAMESPACE, NODE_FOR_CARD,
    SURFACE_BINDINGS, content_ref, fixture_key, fixture_text, matrix_rows,
    title_and_path,
)
from validate_challenges import (  # noqa: E402
    DesignError, Graph, canonical, load_briefs, read_json, require,
)
from validate_k09_handoff import check_k09_assets  # noqa: E402


ENTRY = PACK / "sdl/cinder-typhoon.sdl.yaml"
OPERATIONS = PACK / "sdl/modules/operations"
KEPLER_CONTENT = PACK / "sdl/modules/content"
ASSETS = PACK / "assets/keplerops"
OPENING_ASSETS = ASSETS / "opening"
REGISTRY_ASSETS = ASSETS / "registry"
K09_ASSETS = ASSETS / "build-operations"
EXPECTED_PORTFOLIO_SHA256 = "d5e4456ab827252525459680b0ee0e238252de502f91298eeed503ad08be710f"
EXPECTED_TIERS = Counter({"Medium": 45, "Easy": 25, "Hard": 21, "Expert": 9, "Elite": 4})
EXPECTED_IPS = {
    "k-corporate.k-dev": ("k-corporate.subnet", "10.77.50.20", 24),
    "k-corporate.k-staff": ("k-corporate.subnet", "10.77.50.30", 24),
    "k-corporate.k-identity": ("k-corporate.subnet", "10.77.50.40", 24),
    "k-corporate.k-cert": ("k-corporate.subnet", "10.77.50.50", 24),
    "k-delivery.k-source": ("k-delivery.subnet", "10.77.51.20", 24),
    "k-delivery.k-registry": ("k-delivery.subnet", "10.77.51.30", 24),
    "k-delivery.k-ci": ("k-delivery.subnet", "10.77.51.40", 24),
    "k-delivery.k-preview": ("k-delivery.subnet", "10.77.51.50", 24),
    "k-delivery.k-support": ("k-delivery.subnet", "10.77.51.60", 24),
    "k-delivery.k-indexer": ("k-delivery.subnet", "10.77.51.70", 24),
    "k-cloud.k-cloud-api": ("k-cloud.subnet", "10.77.52.20", 24),
    "k-cloud.k-workload": ("k-cloud.subnet", "10.77.52.30", 24),
    "k-cloud.k-data": ("k-cloud.subnet", "10.77.52.40", 24),
    "k-cloud.k-assistant": ("k-cloud.subnet", "10.77.52.50", 24),
}
EXPECTED_CONNECTOR_ROUTES = {
    "package-poll", "package-activate", "package-receipt", "rollback-rehearsal",
    "diagnostic-intake", "diagnostic-receipt",
}
EXPECTED_SOFTWARE = {
    "k-delivery.k-source": {
        "fieldkest-policyc": "2.6.4",
        "fieldlink-connector-archive": "6.9.8",
    },
    "k-delivery.k-indexer": {"fieldkest-bundle-indexer": "1.8.0"},
    "k-cloud.k-assistant": {
        "qwen2-5-3b-instruct": "14d7620ba47cf51be0b176e14e27e38a34d4ff88",
    },
}
EXPECTED_INTEGRATIONS = {
    "source-build", "runner-source", "runner-registry", "registry-rehearsal",
    "preview-render", "package-delivery", "diagnostic-delivery", "staff-identity-admin",
    "scheduled-output", "maintenance-archive", "backup-source", "completion-handover",
    "assistant-review",
}
TECHNICAL_SECTIONS = (
    "Surface and normal behavior", "Vulnerability and intended solution",
    "Evidence and completion", "Boundaries and persistence", "Author checks",
)
FORBIDDEN_IN_WORLD = re.compile(
    r"\b(?:ctf|flags?|hints?|scores?|scoring|player|challenge|difficulty|hand[- ]build|fictional|unlock(?:ed|s|ing)?)\b",
    re.I,
)
FORBIDDEN_PRIVATE_KEYS = {"cinder_kind", "flow_kind", "context_kind", "modes", "guard"}
COMPLEX_PROFILE_TERMS = {
    "K04.1": ("C++17", "u16le", "u32le", "32", "48", "guard pages"),
    "K05.1": ("@keplerops/fieldlink-connector", "7.4.2", "fieldkest.connector/v3", "arwc-connector-consumer@19f43d2"),
    "K05.2": ("REL-FLK-6.9.8-ARCHIVE", "REL-FLK-7.4.2-09", "yanked"),
    "K05.3": ("REL-FLK-7.4.2-09", "TEN-ARWC-047", "7.4.1", "7.4.2"),
    "K05.4": ("7.4.1", "7.4.2", "short-lived"),
    "K06.1": ("fieldlink-importer-publisher", "arwc-stable", "unavailable"),
    "K06.2": ("@keplerops/support-rehearsal", "6708bbaafa1bf97c3f15d04afa0330a1ce2e914038b22b72ea21b194f32e08d7", "shared namespace"),
    "K06.3": ("Node", "networkless", "fieldkest.connector/v3"),
    "K07.2": ("FKI1", "e2 84 aa", "NFKC", "k42", "PAS-884"),
    "K08.2": ("AES-256-GCM", "HKDF-SHA256", "ikm_hex", "nonce_hex", "aad"),
    "K08.3": ("expiry_policy", "V1", "V2"),
    "K09.1": ("BLD-1842", "c37effd7cc86ae4d44f18e95f899b7557d65e0a9", "BLD-REL-742", "BLD-REC-021"),
    "K09.2": ("ART-BLD-1842-INTEGRATION-REVIEW", "integration-review-input-v3.json", "b631b38ea24ef0e847b9fb9419d32fe83c67d96a8290c62453db9dfe76fd72d4"),
    "K09.3": ("build-results/BLD-1842", "buildops://reviews/diagnostic-request-reference@3", "WS-ROWAN-2026-09-G1", "SIR-*"),
    "K09.4": ("runner-command", "svc-fieldlink-ci", "10.77.53.0/24", "180-second", "HMAC-SHA256", "/workspace"),
    "K10.2": ("SUP-K-2841", "sup-k-2841", "NFKC", "casefold"),
    "K11.2": ("0x00", "0x07", "SEMVER_GTE", "RETURN", "depth above 32"),
    "K11.3": ("tenant_state", "connector_api", "signer_lineage", "compatibility_exception"),
    "K12.2": ("postMessage", "event.origin", "event.source", "120"),
    "K12.3": ("Service-Worker-Allowed", "/review/", "application/javascript"),
    "K14.2": ("fieldkest-build-records", "fieldkest-cloud-policy", "audience"),
    "K14.3": ("exports%2fsupport%2fEXP-2841", "decodes", "double encoding"),
    "K18.2": ("%2e%2e%2fidentity", "percent-decode", "svc-staff-preview"),
    "K18.3": ("PATCH", "OIDC-CINDER-FIXTURE", "fixture-reviewer-047"),
    "K19.2": ("requested_upn", "evan.calderoux", "clientAuth"),
    "K19.3": ("HTTP/identity.keplerops.test", "service class", "hostname"),
    "K20.2": ("svc-release-admin", "five-minute", "requested managed identity"),
    "K20.3": ("human-presence=true", "one operator package"),
    "K21.3": ("Qwen/Qwen2.5-3B-Instruct", "14d7620ba47cf51be0b176e14e27e38a34d4ff88", "do_sample", "2841"),
    "K22.2": ("ATT-DIAG-698", "FLK-6.9.8", "untrusted data"),
    "K22.3": ("accept_duplicate_review", "DREV-2841-2", "human approval"),
    "K23.3": ("CONV-RILL-442-8", "TEN-RILL-022", "session.tenant_id"),
    "K24.2": ("support-examples/../credentials/cred-completion-handover", "five minutes"),
    "K24.3": ("svc-assistant-completion", "HANDOVER-COMP-2841", "caller-selected image"),
    "K28.2": ("GNU build-id", "AES-256-GCM", "0x01", "0xff", "4096"),
    "K28.3": ("/internal/fieldlink/legacy-diagnostics/CRR-OG2", "ENG-FLK-LEGACY-42"),
    "K29.2": ("Ed25519", "HKDF-SHA256", "scrypt", "AES-256-GCM", "reachable deleted commit"),
    "K29.4": ("2026-09-30T12:00:00Z", "expiry_at", "fk-release-2026-next"),
    "K30.2": ("BAK-2026-021", "caller-owned recovery namespace", "no caller-selected source"),
    "K31.2": ("fieldkest/maintenance-runner:2026.09", "workload.class", "svc-fieldlink-maintenance"),
    "K31.3": ("FIELD-CRR-2026-09", "signed scheduler attestation", "operator-editable job label"),
}


def enum(value):
    return getattr(value, "value", value)


def card_key(card: str) -> str:
    operation, number = card.lower().split(".")
    return f"{operation}.c{number}"


def _fact(scenario, assertion_ref: str) -> str:
    assertion = scenario.assertions[assertion_ref]
    proposition = scenario.propositions[assertion.proposition]
    prefix = "urn:cinder-typhoon:fact:"
    require(proposition.predicate.semantic_ref.startswith(prefix),
            f"Unknown prerequisite fact: {assertion_ref}")
    return proposition.predicate.semantic_ref.removeprefix(prefix)


def workflow_groups(scenario, key: str) -> list[list[str]]:
    workflow = scenario.workflows[key]
    branch = workflow.steps.get("requirements")
    if branch is None:
        return [[]]
    require(enum(branch.type) == "switch" and branch.default_step == "unavailable",
            f"KeplerOps workflow can bypass its requirements: {key}")
    groups = []
    for case in branch.cases:
        require(case.when.assertions and not case.when.objectives and not case.when.steps,
                f"Unsupported KeplerOps prerequisite predicate: {key}")
        groups.append([_fact(scenario, ref) for ref in case.when.assertions])
    return groups


def check_portfolio(scenario, rows):
    briefs = load_briefs()
    cards = {ident: brief for ident, brief in briefs.items() if ident.startswith("K")}
    require(set(cards) == set(rows), "KeplerOps brief/matrix inventory drift")
    require(all(brief["status"] == "Technical draft" for brief in cards.values()),
            "Every KeplerOps card must be a technical draft")
    require(Counter(brief["tier_name"] for brief in cards.values()) == EXPECTED_TIERS,
            "KeplerOps difficulty distribution drift")
    portfolio = [(ident, brief["tier_name"], brief["requires_any"])
                 for ident, brief in sorted(cards.items())]
    digest = hashlib.sha256(json.dumps(
        portfolio, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    require(digest == EXPECTED_PORTFOLIO_SHA256,
            "KeplerOps difficulty or prerequisite portfolio drift")

    expected_graph = Graph(read_json(BASE / "challenge-dependencies.json"), briefs)
    for card in cards:
        key = card_key(card)
        require(key in scenario.objectives and key in scenario.workflows,
                f"Missing native objective/workflow: {card}")
        require(canonical(workflow_groups(scenario, key)) == canonical(expected_graph.edges[card]),
                f"Native prerequisite drift: {card}")
        text = cards[card]["text"]
        for section in TECHNICAL_SECTIONS:
            matches = re.findall(
                rf"^### {re.escape(section)}\n(.*?)(?=^### |^## |\Z)", text, re.M | re.S
            )
            require(len(matches) == 1 and matches[0].strip(),
                    f"Missing or empty KeplerOps technical section: {card}/{section}")
        player = re.search(
            r"^## Challenge description — player-facing\n(.*?)(?=^## |\Z)", text, re.M | re.S
        )
        completion = re.search(
            r"^## Completion and downstream use\n(.*?)(?=^## |\Z)", text, re.M | re.S
        )
        require(player and completion and not FORBIDDEN_IN_WORLD.search(player[1] + completion[1]),
                f"Fourth-wall wording in participant-facing KeplerOps brief: {card}")
    return briefs, expected_graph


def check_fixture_contracts(scenario, rows):
    fixture_names = {name for name, item in scenario.content.items()
                     if "service-contract" in item.tags and "keplerops" in item.tags}
    expected_names = {content_ref(card).removeprefix("content.") for card in rows}
    require(fixture_names == expected_names,
            f"KeplerOps fixture inventory drift: expected {len(expected_names)}, got {len(fixture_names)}")
    paths = set()
    for card, row in rows.items():
        ref = content_ref(card).removeprefix("content.")
        content = scenario.content[ref]
        title, _ = title_and_path(card)
        node = NODE_FOR_CARD[card]
        expected_target = f"{NAMESPACE[node]}.{node}"
        expected_path = f"{BASE_PATH[node]}/{fixture_key(card).removeprefix(card.lower().replace('.', '-') + '-')}.yaml"
        # The filename uses the title slug, while the record key includes the card.
        expected_path = f"{BASE_PATH[node]}/{fixture_key(card).split('-', 2)[2]}.yaml"
        require(enum(content.type) == "file" and content.target == expected_target
                and content.path == expected_path and content.sensitive,
                f"KeplerOps fixture ownership drift: {card}")
        require(content.path not in paths, f"Duplicate KeplerOps fixture path: {content.path}")
        paths.add(content.path)
        expected_text = fixture_text(card, title, row)
        require(content.text == expected_text, f"KeplerOps fixture text drift: {card}")
        payload = yaml.safe_load(content.text)
        required = {
            "schema", "record_key", "owner", "surface_bindings", "starting_state", "mechanic_profile",
            "request_contract", "denial_contract", "transition_contract",
            "evidence_contract", "state_rules", "generation_input",
        }
        require(set(payload) == required, f"Incomplete fixture schema: {card}")
        generation = payload.pop("generation_input")
        canonical_payload = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        require(generation == {
            "algorithm": "sha256",
            "digest": hashlib.sha256(canonical_payload).hexdigest(),
            "canonicalization": "UTF-8 JSON, keys sorted, separators comma and colon, excluding generation_input",
        }, f"Fixture generation digest drift: {card}")
        require(not FORBIDDEN_IN_WORLD.search(content.text),
                f"Fourth-wall wording in KeplerOps service content: {card}")
        require(payload["surface_bindings"] == SURFACE_BINDINGS[card],
                f"Native surface binding drift: {card}")
        for binding in payload["surface_bindings"]:
            node_ref, surface = binding.split("/", 1)
            require(node_ref in scenario.nodes, f"Unknown surface node for {card}: {binding}")
            runtime = scenario.nodes[node_ref].runtime
            if surface.startswith("filesystem:"):
                bound_path = surface.removeprefix("filesystem:")
                inventory = [entry.path.rstrip("/") for entry in runtime.filesystem_inventory]
                require(any(bound_path == root or bound_path.startswith(root + "/") for root in inventory),
                        f"Filesystem surface is not inventoried for {card}: {binding}")
            else:
                application_id, route_id = surface.split("/", 1)
                applications = {app.application_id: app for app in runtime.applications}
                require(application_id in applications and
                        route_id in {route.route_id for route in applications[application_id].routes},
                        f"Unknown native application route for {card}: {binding}")
        if card in COMPLEX_PROFILE_TERMS:
            profile = json.dumps(payload["mechanic_profile"], ensure_ascii=False)
            require(all(term in profile for term in COMPLEX_PROFILE_TERMS[card]),
                    f"Exploit-critical mechanic profile incomplete: {card}")
    require(set(COMPLEX_PROFILE_TERMS) <= set(MECHANIC_PROFILE),
            "Complex profile gate references an unauthored mechanic")


def check_actions_and_evidence(scenario, rows):
    for card, row in rows.items():
        key = card_key(card)
        contract = scenario.action_contracts[key]
        preconditions = {item.precondition_id: item for item in contract.preconditions}
        require({"eligibility", "normal-surface", "scope-and-persistence"} <= set(preconditions),
                f"Incomplete native action preconditions: {card}")
        fixture = content_ref(card)
        require(fixture in preconditions["normal-surface"].support_refs,
                f"Action is not bound to its owned fixture: {card}")
        persistence = preconditions["scope-and-persistence"].description.lower()
        require("persist" in persistence and ("ordinary retries" in persistence or "job retry" in persistence),
                f"Persistence boundary is not explicit: {card}")
        require(contract.procedure_basis.strip() and "Pending" not in contract.procedure_basis,
                f"Missing exact procedure basis: {card}")
        require(contract.fidelity_claim.strip() and "exact starting state" in contract.fidelity_claim,
                f"Missing fidelity contract: {card}")
        outcomes = [effect for effect in contract.effects if enum(effect.effect_class) == "intended_effect"]
        require(len(outcomes) == 1 and outcomes[0].description.strip(),
                f"Missing native intended effect: {card}")
        evidence = scenario.evidence_requirements[key]
        proposition = scenario.propositions[key]
        require(evidence.source_refs and list(evidence.observation_demand.selector.component_refs) == evidence.source_refs,
                f"Evidence is not bound to its native source: {card}")
        require(proposition.subjects == evidence.source_refs and enum(proposition.basis) == "observed_state"
                and enum(proposition.quantifier) == "all",
                f"Completion is not independently observed: {card}")
        if card in JOINED_FEATURES:
            require(scenario.objectives[key].targets == JOINED_FEATURES[card]
                    and evidence.source_refs == JOINED_FEATURES[card],
                    f"Multi-service objective/evidence join drift: {card}")
        require(row["result"].split(";")[0].lower()[:24] in outcomes[0].description.lower()
                or outcomes[0].description.strip(), f"Outcome contract is empty: {card}")


def check_world(scenario):
    seen = set()
    for node_ref, (network, address, prefix) in EXPECTED_IPS.items():
        require(node_ref in scenario.nodes, f"Missing KeplerOps system: {node_ref}")
        node = scenario.nodes[node_ref]
        runtime = node.runtime
        require(runtime is not None and runtime.network is not None
                and runtime.service_listeners and runtime.applications
                and runtime.local_identity is not None and runtime.filesystem_inventory,
                f"Incomplete native runtime contract: {node_ref}")
        endpoints = runtime.network.endpoints
        require(len(endpoints) == 1, f"KeplerOps system needs one exact primary endpoint: {node_ref}")
        endpoint = endpoints[0]
        actual = (endpoint.network, endpoint.ip_address, endpoint.ip_prefix_length)
        require(actual == (network, address, prefix), f"Address-plan drift: {node_ref}")
        require(address not in seen, f"Duplicate KeplerOps address: {address}")
        seen.add(address)
        require(all(listener.service and listener.port and listener.protocol
                    for listener in runtime.service_listeners),
                f"Incomplete listener contract: {node_ref}")
        require(all(application.routes for application in runtime.applications),
                f"Application has no route contract: {node_ref}")
        for application in runtime.applications:
            for route_contract in application.routes:
                require(route_contract.responses,
                        f"Route has no response contract: {node_ref}/{route_contract.route_id}")
                if route_contract.auth_required:
                    require(route_contract.auth_scheme,
                            f"Authenticated route lacks an identity scheme: {node_ref}/{route_contract.route_id}")

    for node_ref, expected in EXPECTED_SOFTWARE.items():
        node = scenario.nodes[node_ref]
        components = {item.component_id: str(item.version) for item in node.runtime.software_components}
        require(all(components.get(component) == version for component, version in expected.items()),
                f"Exploit-critical software version drift: {node_ref}")
    require(enum(scenario.nodes["k-delivery.k-source"].architecture) == "x86_64"
            and enum(scenario.nodes["k-delivery.k-indexer"].architecture) == "x86_64",
            "Native binary architecture is not exact")

    operator = scenario.agents["participant.operator"]
    require("k-corporate.rowan-workstation" in operator.starting_accounts
            and "k-corporate.k-dev" in operator.initial_knowledge.hosts
            and "k-corporate.subnet" in operator.initial_knowledge.subnets
            and "ssh" in operator.initial_knowledge.services,
            "Supplied KeplerOps developer position is not obtainable and recognizable")
    developer = operator.interactive_access.get("developer")
    require(developer is not None and developer.target_ref == "nodes.k-corporate.k-dev"
            and developer.account_ref == "accounts.k-corporate.rowan-workstation"
            and enum(developer.channel) == "ssh",
            "Supplied KeplerOps developer session is not exercisable")

    connector = scenario.nodes["a-corporate.a-connector"].runtime
    require(connector is not None and connector.network.endpoints[0].ip_address == "10.77.60.20",
            "Missing exact customer connector boundary")
    applications = {app.application_id: app for app in connector.applications}
    require("fieldlink-customer-consumer" in applications,
            "Customer connector boundary application is missing")
    routes = {route.route_id for route in applications["fieldlink-customer-consumer"].routes}
    require(routes == EXPECTED_CONNECTOR_ROUTES, "Customer connector boundary route drift")
    require(connector.app_authorizations, "Customer connector boundary lacks native authorization")


def check_native_semantics(scenario):
    legacy = tuple(PACK.glob("sdl/modules/routes/flows-k-*.yaml"))
    require(not legacy, "Legacy KeplerOps private flow module remains")
    integration = yaml.safe_load((PACK / "sdl/modules/routes/keplerops-integrations.yaml").read_text())
    require(set(integration["relationships"]) == EXPECTED_INTEGRATIONS,
            "Native KeplerOps integration inventory drift")
    for key, relationship in integration["relationships"].items():
        require(relationship.get("type") == "connects_to" and not relationship.get("properties"),
                f"KeplerOps integration uses private semantics: {key}")
    for path in list(OPERATIONS.glob("k*.yaml")) + [PACK / "sdl/modules/routes/keplerops-integrations.yaml"]:
        data = yaml.safe_load(path.read_text())
        serialized = json.dumps(data, sort_keys=True)
        require(not any(f'"{key}"' in serialized for key in FORBIDDEN_PRIVATE_KEYS),
                f"Meaning-bearing private property in KeplerOps module: {path.name}")
        require("starting-records" not in serialized and "Pending exact" not in serialized,
                f"Placeholder KeplerOps declaration remains: {path.name}")

    # a-connector is also an existing ARWC target. Its future-stage private W
    # surfaces are out of this gate; only the named native integration module
    # above carries KeplerOps meaning at that boundary.
    kepler_features = {
        "features." + feature
        for node_ref in EXPECTED_IPS
        for feature in scenario.nodes[node_ref].features
    }
    for key, relationship in scenario.relationships.items():
        if relationship.source in kepler_features or relationship.target in kepler_features:
            require(not relationship.properties,
                    f"Composed KeplerOps relationship has private semantic properties: {key}")


def check_prose_and_assets(scenario):
    scoped = list(OPERATIONS.glob("k*.yaml")) + list(KEPLER_CONTENT.glob("keplerops-*.yaml"))
    scoped += list(ASSETS.rglob("*"))
    for path in scoped:
        if not path.is_file():
            continue
        try:
            text = path.read_text(errors="strict")
        except UnicodeDecodeError:
            continue
        require(not re.search(r"\breset(?:s|ting)?\b", text, re.I),
                f"In-world reset contract remains in KeplerOps scope: {path.relative_to(PACK)}")
    check_k09_assets(scenario)


def check_opening_assets(scenario):
    manifest = json.loads((OPENING_ASSETS / "archive-manifest.json").read_text())
    require(manifest["schema"] == "fieldkest.opening-archives/v1",
            "Unknown KeplerOps opening archive manifest")
    expected = {
        "k-dev-home.tar": (
            "keplerops-opening-k-dev.opening-k-dev-home",
            "k-corporate.k-dev",
            "/home/rowan",
        ),
        "k-dev-workbench.tar": (
            "keplerops-opening-k-dev.opening-k-dev-workbench",
            "k-corporate.k-dev",
            "/opt/fieldkest-workbench",
        ),
        "k-source-state.tar": (
            "keplerops-opening-k-source.opening-k-source-state",
            "k-delivery.k-source",
            "/var/lib/gitea",
        ),
        "k-ci-state.tar": (
            "keplerops-opening-k-ci.opening-k-ci-state",
            "k-delivery.k-ci",
            "/var/lib/fieldkest-ci",
        ),
        "k-support-state.tar": (
            "keplerops-opening-k-support.opening-k-support-state",
            "k-delivery.k-support",
            "/var/lib/fieldkest-support",
        ),
    }
    records = {item["archive"]: item for item in manifest["archives"]}
    require(set(records) == set(expected), "KeplerOps opening archive inventory drift")
    for archive_name, (content_ref, target, destination) in expected.items():
        archive_path = OPENING_ASSETS / archive_name
        record = records[archive_name]
        archive_bytes = archive_path.read_bytes()
        require(hashlib.sha256(archive_bytes).hexdigest() == record["sha256"]
                and len(archive_bytes) == record["size"],
                f"Opening archive digest drift: {archive_name}")
        content = scenario.content[content_ref]
        requirement = content.source.artifact_requirement if content.source else None
        require(enum(content.type) == "directory" and content.target == target
                and content.destination == destination and requirement is not None
                and enum(requirement.explicitness) == "exact"
                and requirement.exact_artifact is not None
                and requirement.exact_artifact.digest == "sha256:" + record["sha256"],
                f"Opening archive is not exact native RAE content: {archive_name}")
        declared_files = {item["path"]: item for item in record["files"]}
        with tarfile.open(archive_path, "r") as archive:
            members = {item.name: item for item in archive.getmembers() if item.isfile()}
            require(set(members) == set(declared_files),
                    f"Opening archive member inventory drift: {archive_name}")
            for member_name, member in members.items():
                payload = archive.extractfile(member).read()
                declaration = declared_files[member_name]
                require(hashlib.sha256(payload).hexdigest() == declaration["sha256"]
                        and len(payload) == declaration["size"]
                        and f"{member.mode:04o}" == declaration["mode"],
                        f"Opening archive member drift: {archive_name}/{member_name}")

    generated = json.loads(
        (OPENING_ASSETS / "k-dev/generated-artifacts.json").read_text()
    )
    require(generated["schema"] == "fieldkest.generated-artifacts/v1",
            "Unknown generated opening-artifact manifest")
    for artifact in generated["artifacts"]:
        path = OPENING_ASSETS / "k-dev" / artifact["name"]
        payload = path.read_bytes()
        require(hashlib.sha256(payload).hexdigest() == artifact["sha256"]
                and len(payload) == artifact["size"],
                f"Generated opening artifact drift: {artifact['name']}")

    participant_sources = []
    for owner in ("k-dev", "k-source", "k-ci", "k-support"):
        participant_sources.extend((OPENING_ASSETS / owner).glob("*"))
    for path in participant_sources:
        if not path.is_file() or path.name in {
            "generated-artifacts.json", "repository-artifact.json", "repository-seed.json",
            "source-service.json", "ci-service.json", "support-service.json",
            "workbench-service.json",
        }:
            continue
        try:
            text = path.read_text(errors="strict")
        except UnicodeDecodeError:
            continue
        require(not FORBIDDEN_IN_WORLD.search(text),
                f"Fourth-wall wording in KeplerOps opening asset: {path.relative_to(PACK)}")


def check_registry_assets(scenario):
    manifest = json.loads((REGISTRY_ASSETS / "artifact-manifest.json").read_text())
    require(manifest["schema"] == "fieldkest.registry-foundation-artifacts/v1",
            "Unknown KeplerOps registry archive manifest")
    expected = {
        "k-registry-state.tar": (
            "keplerops-registry-foundation.registry-foundation-state",
            "k-delivery.k-registry",
            "/var/lib/fieldkest-registry",
        ),
        "k-dev-registry.tar": (
            "keplerops-registry-foundation.registry-foundation-workstation",
            "k-corporate.k-dev",
            "/home/rowan",
        ),
    }
    records = {item["archive"]: item for item in manifest["archives"]}
    require(set(records) == set(expected), "KeplerOps registry archive inventory drift")
    for archive_name, (content_ref, target, destination) in expected.items():
        archive_path = REGISTRY_ASSETS / archive_name
        record = records[archive_name]
        archive_bytes = archive_path.read_bytes()
        require(hashlib.sha256(archive_bytes).hexdigest() == record["sha256"]
                and len(archive_bytes) == record["size"],
                f"Registry archive digest drift: {archive_name}")
        content = scenario.content[content_ref]
        requirement = content.source.artifact_requirement if content.source else None
        require(enum(content.type) == "directory" and content.target == target
                and content.destination == destination and requirement is not None
                and enum(requirement.explicitness) == "exact"
                and requirement.exact_artifact is not None
                and requirement.exact_artifact.digest == "sha256:" + record["sha256"],
                f"Registry archive is not exact native RAE content: {archive_name}")
        declared_files = {item["path"]: item for item in record["files"]}
        with tarfile.open(archive_path, "r") as archive:
            members = {item.name: item for item in archive.getmembers() if item.isfile()}
            require(set(members) == set(declared_files),
                    f"Registry archive member inventory drift: {archive_name}")
            for member_name, member in members.items():
                payload = archive.extractfile(member).read()
                declaration = declared_files[member_name]
                require(hashlib.sha256(payload).hexdigest() == declaration["sha256"]
                        and len(payload) == declaration["size"]
                        and f"{member.mode:04o}" == declaration["mode"],
                        f"Registry archive member drift: {archive_name}/{member_name}")

    state_files = records["k-registry-state.tar"]["files"]
    state_by_path = {item["path"]: item for item in state_files}
    package = state_by_path["packages/support-rehearsal-1.3.1.tgz"]
    entitlement = state_by_path["records/entitlements/ENT-ARWC-DIAG-0698.json"]
    inspector = state_by_path["examples/inspection-compat.fki"]
    require(manifest["support_package"] == {
        "sha256": package["sha256"], "size": package["size"]
    } and package["sha256"] ==
            "6708bbaafa1bf97c3f15d04afa0330a1ce2e914038b22b72ea21b194f32e08d7",
            "Protected support package identity drift")
    require(manifest["entitlement"]["record_sha256"] == entitlement["sha256"],
            "Entitlement record identity drift")
    require(inspector["sha256"] ==
            "47430e0cf68733cda0bcb7515e5fefa4f263801761e8b4c1f899e8306ceec098"
            and inspector["size"] == 13,
            "Compatibility inspector fixture drift")

    participant_sources = (REGISTRY_ASSETS / "source/k-dev").rglob("*")
    for path in participant_sources:
        if not path.is_file():
            continue
        try:
            text = path.read_text(errors="strict")
        except UnicodeDecodeError:
            continue
        require(not FORBIDDEN_IN_WORLD.search(text),
                f"Fourth-wall wording in KeplerOps registry asset: {path.relative_to(PACK)}")


def check_k09_foundation_assets(scenario):
    manifest = json.loads((K09_ASSETS / "artifact-manifest.json").read_text())
    require(manifest["schema"] == "fieldkest.k09-foundation-artifacts/v1",
            "Unknown K09 foundation archive manifest")
    expected = {
        "k-ci-k09-state.tar": (
            "keplerops-k09-foundation.k09-ci-state", "k-delivery.k-ci", "/var/lib/fieldkest-ci"
        ),
        "k-cloud-api-k09-state.tar": (
            "keplerops-k09-foundation.k09-cloud-api-state", "k-cloud.k-cloud-api",
            "/var/lib/fieldkest-cloud-api",
        ),
    }
    records = {item["archive"]: item for item in manifest["archives"]}
    require(set(records) == set(expected), "K09 foundation archive inventory drift")
    for archive_name, (content_ref, target, destination) in expected.items():
        record = records[archive_name]
        archive_path = K09_ASSETS / archive_name
        archive_bytes = archive_path.read_bytes()
        require(hashlib.sha256(archive_bytes).hexdigest() == record["sha256"]
                and len(archive_bytes) == record["size"],
                f"K09 archive digest drift: {archive_name}")
        content = scenario.content[content_ref]
        requirement = content.source.artifact_requirement if content.source else None
        require(enum(content.type) == "directory" and content.target == target
                and content.destination == destination and requirement is not None
                and enum(requirement.explicitness) == "exact"
                and requirement.exact_artifact is not None
                and requirement.exact_artifact.digest == "sha256:" + record["sha256"],
                f"K09 archive is not exact native RAE content: {archive_name}")
        declared_files = {item["path"]: item for item in record["files"]}
        with tarfile.open(archive_path, "r") as archive:
            members = {item.name: item for item in archive.getmembers() if item.isfile()}
            require(set(members) == set(declared_files),
                    f"K09 archive member inventory drift: {archive_name}")
            for member_name, member in members.items():
                payload = archive.extractfile(member).read()
                declaration = declared_files[member_name]
                require(hashlib.sha256(payload).hexdigest() == declaration["sha256"]
                        and len(payload) == declaration["size"]
                        and f"{member.mode:04o}" == declaration["mode"],
                        f"K09 archive member drift: {archive_name}/{member_name}")

    ci_files = {item["path"]: item for item in records["k-ci-k09-state.tar"]["files"]}
    require(ci_files["artifacts/BLD-1842/integration-review-input-v3.json"]["sha256"] ==
            "b631b38ea24ef0e847b9fb9419d32fe83c67d96a8290c62453db9dfe76fd72d4",
            "K09 omitted-artifact digest drift")
    for path in (K09_ASSETS / "source").rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(errors="strict")
        except UnicodeDecodeError:
            continue
        require(not FORBIDDEN_IN_WORLD.search(text),
                f"Fourth-wall wording in K09 foundation asset: {path.relative_to(PACK)}")


def hand_build_gaps(scenario) -> list[str]:
    """Return all gate failures so authors can fix a complete tranche at once."""
    checks = (
        ("portfolio", check_portfolio),
        ("fixture contracts", check_fixture_contracts),
        ("actions/evidence", check_actions_and_evidence),
        ("world substrate", lambda current, rows: check_world(current)),
        ("native semantics", lambda current, rows: check_native_semantics(current)),
        ("opening assets", lambda current, rows: check_opening_assets(current)),
        ("registry assets", lambda current, rows: check_registry_assets(current)),
        ("K09 foundation assets", lambda current, rows: check_k09_foundation_assets(current)),
        ("prose/assets", lambda current, rows: check_prose_and_assets(current)),
    )
    rows = matrix_rows()
    gaps = []
    for label, check in checks:
        try:
            check(scenario, rows)
        except (DesignError, KeyError, TypeError, ValueError, yaml.YAMLError) as error:
            gaps.append(f"{label}: {error}")
    return gaps


def check_keplerops(scenario):
    gaps = hand_build_gaps(scenario)
    require(not gaps, "KeplerOps hand-build gate has gaps:\n- " + "\n- ".join(gaps))
    return len(matrix_rows())


if __name__ == "__main__":
    from raes.parser import parse_sdl_file

    try:
        parsed = parse_sdl_file(ENTRY)
        count = check_keplerops(parsed)
    except DesignError as error:
        raise SystemExit(f"FAIL: {error}")
    print(f"PASS: KeplerOps hand-build design gate ({count} cards); no materialization was performed")
