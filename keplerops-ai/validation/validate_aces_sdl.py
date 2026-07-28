#!/usr/bin/env python3
"""Validate KeplerOps with the pinned published RAES package."""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aces_contract import atlas_technique_catalog, module_contracts  # noqa: E402

try:
    from raes import parse_sdl_file
    from raes.validator import SemanticValidator
    from raes_contracts.controlled_vocabularies import load_controlled_vocabulary_catalog
except ImportError as exc:  # pragma: no cover - exercised when the dependency is absent.
    print(
        "raes is required: install `validation/requirements.txt` from PyPI.",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


PACK_ROOT = Path(__file__).resolve().parents[1]
SDL_NAME = "keplerops-ai.sdl.yaml"
REQUIREMENTS_REL_PATH = Path("validation/requirements.txt")
EXPECTED_VERSION = "2.0.0"
EXPECTED_REQUIREMENT = f"raes=={EXPECTED_VERSION}"
ATLAS_VOCABULARY_ID = "participant-ai-offensive-behavior-activities"
FORBIDDEN_SEMANTIC_PATHS = (
    "assets/affordances.yaml",
    "assets/oracle/baseline.yaml",
    "build/gcp/runtime-images.yaml",
    "challenges/challenges.yaml",
    "design/implementation-tracking.yaml",
    "flags/placement.yaml",
    "oracle/atlas-technique-projection.yaml",
    "oracle/objectives.yaml",
    "oracle/scoring.yaml",
    "oracle/telemetry.yaml",
    "telemetry/research-telemetry.yaml",
)
CORE_PREFIX = "core."
AD_DOMAIN = f"{CORE_PREFIX}keplerops"
AD_FOREST = f"{CORE_PREFIX}keplerops-enterprise"
OIDC_FACADE = f"{CORE_PREFIX}workforce-oidc"
AD_CONTROLLER = f"{CORE_PREFIX}ad-dc-01"
DOMAIN_ENDPOINTS = {
    f"{CORE_PREFIX}workforce-workstation-01": "workforce",
    f"{CORE_PREFIX}ml-workstation-01": "engineering",
}
DOMAIN_ACCOUNTS = {
    f"{CORE_PREFIX}user-qa-intern",
    f"{CORE_PREFIX}user-ml-engineer",
    f"{CORE_PREFIX}user-release-manager",
    f"{CORE_PREFIX}admin-guardrail",
    f"{CORE_PREFIX}domain-administrator",
    f"{CORE_PREFIX}svc-keycloak-federation",
}
PACKED_LINUX_NODES = {
    f"{CORE_PREFIX}{name}"
    for name in (
        "lab-portal",
        "idp-01",
        "repo-ticket-01",
        "inference-gateway",
        "guardrail-policy",
        "model-registry-01",
        "artifact-store-01",
        "dataset-store-01",
        "distillation-runner-01",
        "notebook-runner-01",
        "telemetry-proof-01",
        "exfil-sink",
        "research-index-01",
        "range-dns-01",
        "public-sites-01",
        "scan-services-01",
        "platform-impact-01",
        "platform-ml-01",
        "mail-server-01",
        "webmail-01",
        "text-generation-01",
        "image-generation-01",
        "platform-camera-01",
        "platform-agent-01",
        "policy-lab-01",
        "range-ops-controller",
    )
}
WORKER_BOUNDARY_NODES = {
    f"{CORE_PREFIX}platform-agent-01",
    f"{CORE_PREFIX}policy-lab-01",
}
CONTROL_BOUNDARY_NODES = {
    f"{CORE_PREFIX}telemetry-proof-01",
    f"{CORE_PREFIX}range-ops-controller",
}
WORKFORCE_FACADE_CONSUMERS = {
    f"{CORE_PREFIX}workhub-workforce-oidc": "nodes.core.repo-ticket-01.services.workhub-https",
    f"{CORE_PREFIX}mail-workforce-oidc": "nodes.core.mail-server-01.services.mail-submission",
    f"{CORE_PREFIX}webmail-workforce-oidc": "nodes.core.webmail-01.services.webmail-http",
    f"{CORE_PREFIX}notebook-workforce-oidc": "nodes.core.notebook-runner-01.services.notebook-jupyter",
    f"{CORE_PREFIX}workflow-workforce-oidc": "nodes.core.distillation-runner-01.services.distillation-jobs",
    f"{CORE_PREFIX}registry-workforce-oidc": "nodes.core.model-registry-01.services.registry-api",
    f"{CORE_PREFIX}artifacts-workforce-oidc": "nodes.core.artifact-store-01.services.artifact-object-store",
    f"{CORE_PREFIX}portal-workforce-oidc": "nodes.core.lab-portal.services.lab-portal-https",
}


def _installed_version(failures: list[str]) -> str | None:
    try:
        return version("raes")
    except PackageNotFoundError:
        failures.append("raes: package is not installed")
        return None


def _check_requirement_pin(path: Path, failures: list[str]) -> None:
    try:
        requirement = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        failures.append(f"{REQUIREMENTS_REL_PATH}: cannot read: {exc}")
        return
    if requirement != EXPECTED_REQUIREMENT:
        failures.append(
            f"{REQUIREMENTS_REL_PATH}: expected exactly {EXPECTED_REQUIREMENT}"
        )


def _sdl_sources(path: Path, failures: list[str]) -> list[Path]:
    files = sorted(
        item for item in path.rglob("*")
        if item.is_file() and not _is_python_cache(item, path)
    )
    invalid = [
        str(item.relative_to(path)) for item in files
        if not item.name.endswith(".sdl.yaml")
    ]
    if invalid:
        failures.append(
            "sdl/: only ACES *.sdl.yaml source files are allowed; "
            f"found {invalid}"
        )
    sources = [item for item in files if item.name.endswith(".sdl.yaml")]
    if path / SDL_NAME not in sources:
        failures.append(f"sdl/: missing root ACES scenario {SDL_NAME}")
    return sources


def _is_python_cache(item: Path, root: Path) -> bool:
    rel = item.relative_to(root)
    return "__pycache__" in rel.parts or item.suffix in {".pyc", ".pyo"}


def _check_root_import_coverage(
    root_source: Path,
    sources: list[Path],
    failures: list[str],
) -> None:
    try:
        value = yaml.safe_load(root_source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return
    if not isinstance(value, dict):
        return
    allowed = {"name", "version", "description", "imports"}
    extra = sorted(set(value) - allowed)
    if extra:
        failures.append(
            f"sdl/{SDL_NAME}: root must compose modules only; found sections {extra}"
        )
    imported: set[Path] = set()
    for row in value.get("imports", []):
        if not isinstance(row, dict) or not isinstance(row.get("source"), str):
            continue
        source = row["source"]
        if source.startswith("local:"):
            imported.add((root_source.parent / source.removeprefix("local:")).resolve())
    expected = {source.resolve() for source in sources if source != root_source}
    missing = sorted(str(path.relative_to(root_source.parent.resolve())) for path in expected - imported)
    unknown = sorted(str(path) for path in imported - expected)
    if missing:
        failures.append(f"sdl/{SDL_NAME}: unimported ACES modules {missing}")
    if unknown:
        failures.append(f"sdl/{SDL_NAME}: imports unknown ACES modules {unknown}")


def _atlas_term_by_tactic_id() -> dict[str, str]:
    catalog = load_controlled_vocabulary_catalog()
    vocabulary = catalog.vocabularies[ATLAS_VOCABULARY_ID]
    return {
        str(term.source_id): term_id
        for term_id, term in vocabulary.terms.items()
        if term.source_id
    }


def _expected_tactics_by_step(
    atlas: dict[str, Any],
    failures: list[str],
) -> dict[str, set[str]]:
    term_by_id = _atlas_term_by_tactic_id()
    expected: dict[str, set[str]] = {str(number): set() for number in range(1, 11)}
    for technique in atlas.get("technique_catalog", []):
        step_id = str(technique.get("challenge_step", ""))
        if step_id not in expected:
            failures.append(
                f"content.core.atlas-technique-catalog: technique references missing step {step_id}"
            )
            continue
        for tactic_id in technique.get("tactics", []):
            term = term_by_id.get(str(tactic_id))
            if term is None:
                failures.append(
                    f"content.core.atlas-technique-catalog: tactic {tactic_id} is not governed by "
                    f"raes=={EXPECTED_VERSION}"
                )
                continue
            expected[step_id].add(term)
    return expected


def _check_behavior_bindings(
    scenario: Any,
    atlas: dict[str, Any],
    modules: dict[str, dict[str, Any]],
    failures: list[str],
) -> None:
    expected = _expected_tactics_by_step(atlas, failures)
    governed_terms = set(_atlas_term_by_tactic_id().values())
    seen: set[str] = set()
    for name, behavior in scenario.behavior_specifications.items():
        extensions = behavior.extensions if isinstance(behavior.extensions, dict) else {}
        row = extensions.get("x-keplerops:portfolio-module")
        if not isinstance(row, dict):
            continue
        module_id = row.get("module_id")
        step = str(row.get("path_step", {}).get("path_step", ""))
        if module_id not in modules or module_id in seen:
            failures.append(f"behavior_specifications.{name}: invalid portfolio module binding")
            continue
        seen.add(module_id)
        actual = set(behavior.ai_offensive_behavior_refs)
        if step not in expected or not actual or not actual <= governed_terms:
            failures.append(f"behavior_specifications.{name}: invalid governed ATLAS tactic binding")


def _check_directory_runtime_intent(scenario: Any, failures: list[str]) -> None:
    domain = scenario.identity_domains.get(AD_DOMAIN)
    if (
        domain is None
        or domain.profile.value != "active_directory"
        or domain.dns_name != "keplerops.test"
        or domain.netbios_name != "KEPLEROPS"
        or domain.authority_account_ref != f"{CORE_PREFIX}domain-administrator"
    ):
        failures.append("identity_domains.core.keplerops: authoritative AD contract is incomplete")

    forest = scenario.identity_forests.get(AD_FOREST)
    if (
        forest is None
        or forest.root_domain_ref != AD_DOMAIN
        or forest.domain_refs != [AD_DOMAIN]
    ):
        failures.append("identity_forests.core.keplerops-enterprise: single-domain forest contract is incomplete")

    facade = scenario.identity_facades.get(OIDC_FACADE)
    if (
        facade is None
        or facade.service_ref != "nodes.core.idp-01.services.keycloak-oidc"
        or facade.protocol.value != "oidc"
    ):
        failures.append("identity_facades.core.workforce-oidc: Keycloak facade contract is incomplete")

    controller = scenario.relationships.get(f"{CORE_PREFIX}ad-domain-controller")
    if (
        controller is None
        or controller.source != AD_CONTROLLER
        or controller.target != AD_DOMAIN
        or controller.domain_controller is None
    ):
        failures.append("relationships.core.ad-domain-controller: AD authority binding is incomplete")


def _check_domain_endpoint_intent(scenario: Any, failures: list[str]) -> None:
    for endpoint_ref, persona in DOMAIN_ENDPOINTS.items():
        node = scenario.nodes.get(endpoint_ref)
        local = endpoint_ref.removeprefix(CORE_PREFIX)
        relationship = scenario.relationships.get(f"{CORE_PREFIX}{'ml' if local.startswith('ml-') else 'workforce'}-domain-join")
        if (
            node is None
            or node.os != "windows"
            or node.endpoint_persona.value != persona
            or relationship is None
            or relationship.source != endpoint_ref
            or relationship.target != AD_DOMAIN
            or relationship.domain_join is None
            or relationship.domain_join.controller_refs != [AD_CONTROLLER]
        ):
            failures.append(f"nodes.{endpoint_ref}: domain-joined {persona} endpoint contract is incomplete")


def _check_federation_runtime_intent(scenario: Any, failures: list[str]) -> None:
    federation = scenario.relationships.get(f"{CORE_PREFIX}workforce-directory-federation")
    intent = federation.identity_federation if federation is not None else None
    if (
        federation is None
        or federation.source != AD_FOREST
        or federation.target != OIDC_FACADE
        or intent is None
        or intent.direction.value != "authority_to_facade"
        or intent.protocol.value != "ldap_tls"
        or intent.mapping_intent.value != "groups_to_roles"
        or intent.tenant_claim_name != "range_instance"
        or intent.tenant_claim_owner.value != "facade"
    ):
        failures.append("relationships.core.workforce-directory-federation: AD-to-Keycloak authority contract is incomplete")

    facade_consumers = {
        name: relationship.source
        for name, relationship in scenario.relationships.items()
        if name in WORKFORCE_FACADE_CONSUMERS
        and relationship.type.value == "authenticates_with"
        and relationship.target == OIDC_FACADE
    }
    if facade_consumers != WORKFORCE_FACADE_CONSUMERS:
        failures.append("relationships: enterprise applications must consume the declared workforce identity facade")


def _check_authority_runtime_intent(scenario: Any, failures: list[str]) -> None:
    controller_node = scenario.nodes.get(AD_CONTROLLER)
    controller_services = {
        service.name for service in controller_node.services
    } if controller_node is not None else set()
    if "enterprise-files-smb" not in controller_services:
        failures.append("nodes.core.ad-dc-01: ordinary enterprise file service is missing")

    actual_domain_accounts = {
        name for name, account in scenario.accounts.items() if account.domain_ref == AD_DOMAIN
    }
    if actual_domain_accounts != DOMAIN_ACCOUNTS:
        failures.append("accounts: AD authority must cover exactly the declared human workforce identities")


def _check_carrier_runtime_intent(scenario: Any, failures: list[str]) -> None:
    carrier = scenario.nodes.get(f"{CORE_PREFIX}range-linux-carrier-01")
    worker_carrier = scenario.nodes.get(f"{CORE_PREFIX}range-worker-carrier-01")
    control_carrier = scenario.nodes.get(f"{CORE_PREFIX}range-control-carrier-01")
    placements = {
        relationship.source: relationship
        for relationship in scenario.relationships.values()
        if relationship.type.value == "placed_on_carrier"
    }
    if (
        carrier is None
        or carrier.os != "linux"
        or carrier.endpoint_persona.value != "carrier"
        or worker_carrier is None
        or worker_carrier.os != "linux"
        or worker_carrier.endpoint_persona.value != "carrier"
        or control_carrier is None
        or control_carrier.os != "linux"
        or control_carrier.endpoint_persona.value != "carrier"
        or set(placements) != PACKED_LINUX_NODES
        or any(
            row.target
            != (
                f"{CORE_PREFIX}range-worker-carrier-01"
                if source in WORKER_BOUNDARY_NODES
                else (
                    f"{CORE_PREFIX}range-control-carrier-01"
                    if source in CONTROL_BOUNDARY_NODES
                    else f"{CORE_PREFIX}range-linux-carrier-01"
                )
            )
            or row.carrier_placement is None
            or row.carrier_placement.kernel_boundary.value != "shared_kernel"
            for source, row in placements.items()
        )
    ):
        failures.append("relationships: packed Linux estate must preserve its declared carrier trust boundaries")


def _check_deployment_runtime_intent(scenario: Any, failures: list[str]) -> None:
    range_cell = scenario.deployment_cells.get(f"{CORE_PREFIX}range-cell")
    shared_cell = scenario.deployment_cells.get(f"{CORE_PREFIX}shared-model-cell")
    range_nodes = (
        set(range_cell.node_refs) if range_cell is not None else set()
    )
    expected_range_nodes = (
        PACKED_LINUX_NODES
        | set(DOMAIN_ENDPOINTS)
        | {
            f"{CORE_PREFIX}participant-workstation",
            f"{CORE_PREFIX}range-linux-carrier-01",
            f"{CORE_PREFIX}range-worker-carrier-01",
            f"{CORE_PREFIX}range-control-carrier-01",
            AD_CONTROLLER,
        }
    )
    if (
        range_cell is None
        or range_cell.tenant_ref != f"{CORE_PREFIX}range-tenant"
        or range_cell.cross_tenant_isolation.value != "default_deny"
        or range_nodes != expected_range_nodes
        or shared_cell is None
        or shared_cell.tenant_ref != f"{CORE_PREFIX}shared-model-platform"
        or shared_cell.cross_tenant_isolation.value != "default_deny"
        or shared_cell.node_refs != [f"{CORE_PREFIX}model-host-01"]
    ):
        failures.append("deployment_cells: range and shared-model trust boundaries are incomplete")

    shared = scenario.relationships.get(f"{CORE_PREFIX}shared-inference-service")
    policy = shared.shared_service if shared is not None else None
    if (
        shared is None
        or shared.source != f"{CORE_PREFIX}range-tenant"
        or shared.target != "nodes.core.model-host-01.services.open-model-api"
        or policy is None
        or policy.tenant_isolation.value != "stateless"
        or policy.workload_authentication.value != "tenant_scoped_workload_identity"
        or policy.mutable_state_refs
        or policy.mutable_state_owner.value != "none"
        or policy.reset_generation_owner.value != "none"
    ):
        failures.append("relationships.core.shared-inference-service: tenant-safe shared-model contract is incomplete")
    model_host = scenario.nodes.get(f"{CORE_PREFIX}model-host-01")
    if (
        model_host is None
        or model_host.resources is not None
        or "shared inference pool" not in model_host.description
    ):
        failures.append("nodes.core.model-host-01: shared pool endpoint must not declare per-range capacity")


def _check_enterprise_runtime_intent(scenario: Any, failures: list[str]) -> None:
    _check_directory_runtime_intent(scenario, failures)
    _check_domain_endpoint_intent(scenario, failures)
    _check_federation_runtime_intent(scenario, failures)
    _check_authority_runtime_intent(scenario, failures)
    _check_carrier_runtime_intent(scenario, failures)
    _check_deployment_runtime_intent(scenario, failures)


def validate_pack(root: Path = PACK_ROOT) -> list[str]:
    failures: list[str] = []
    for relative in FORBIDDEN_SEMANTIC_PATHS:
        if (root / relative).exists():
            failures.append(f"{relative}: redundant non-ACES semantic source must not exist")
    sdl_root = root / "sdl"
    sdl_path = sdl_root / SDL_NAME
    sources = _sdl_sources(sdl_root, failures)
    _check_root_import_coverage(sdl_path, sources, failures)
    _check_requirement_pin(root / REQUIREMENTS_REL_PATH, failures)
    installed = _installed_version(failures)
    if installed is not None and installed != EXPECTED_VERSION:
        failures.append(
            f"raes: expected PyPI version {EXPECTED_VERSION}, found {installed}"
        )
    scenario = None
    for source in sources:
        try:
            if source == sdl_path:
                parsed = parse_sdl_file(source)
                SemanticValidator(parsed).validate()
                scenario = parsed
            else:
                # Imported modules may intentionally reference exported symbols
                # from sibling namespaces. The composed root owns cross-module
                # semantic validation; modules still receive full typed parsing.
                parse_sdl_file(source, skip_semantic_validation=True)
        except Exception as exc:  # RAES exposes parse and semantic errors.
            relative = source.relative_to(root)
            failures.append(f"{relative}: {type(exc).__name__}: {exc}")
    if scenario is None:
        return failures
    if (
        len(scenario.nodes) < 29
        or len(scenario.infrastructure) != len(scenario.nodes)
        or len(scenario.features) < 29
        or len(scenario.behavior_specifications) != 145
        or len(scenario.conditions) != 134
        or len(scenario.propositions) < 135
        or len(scenario.assertions) < 135
        or len(scenario.evidence_requirements) < 135
        or len(scenario.objectives) != 134
        or len(scenario.content) < 46
    ):
        failures.append("expanded ACES SDL does not declare the complete KeplerOps world")
    try:
        atlas = atlas_technique_catalog(root)
        modules = module_contracts(root)
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        failures.append(f"ACES contract extraction failed: {exc}")
        return failures
    _check_behavior_bindings(scenario, atlas, modules, failures)
    _check_enterprise_runtime_intent(scenario, failures)
    return failures


def main(argv: list[str]) -> int:
    if argv != ["validate"]:
        print("usage: validate_aces_sdl.py validate", file=sys.stderr)
        return 2
    failures = validate_pack()
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    print(
        f"[ok] sdl/{SDL_NAME} (raes=={EXPECTED_VERSION}; "
        "10 module, 134 realized challenge, and 1 green live-activity behavior specification; "
        "1 remaining planned challenge design; governed ATLAS tactics)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
