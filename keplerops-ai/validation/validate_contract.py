#!/usr/bin/env python3
"""Validate the KeplerOps AI Systems draft pack and build-source contract."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from raes import parse_sdl_file

PACK_ID = "keplerops-ai"
TITLE = "KeplerOps AI Systems"
VERSION = "0.16.0"
REQUIREMENT = "KEP-0001"
README_PATH = "README.md"
PACK_YAML_PATH = "pack.yaml"
COMPATIBILITY_PATH = "pack.compatibility.yaml"
CONCEPTS_PATH = "docs/concepts.md"
ATTACK_PATH_PATH = "docs/attack-path.md"
ATLAS_DOC_PATH = "docs/atlas-coverage-plan.md"
TOPOLOGY_DOC_PATH = "docs/topology-reference-triangle.md"
FLEET_CAPACITY_DOC_PATH = "docs/fleet-capacity-model.md"
LINEAGE_PATH = "docs/lineage.md"
PROVENANCE_PATH = "docs/provenance-ledger.yaml"
GOLDEN_CHECKLIST_PATH = "docs/golden-readiness-checklist.md"
SDL_README_PATH = "docs/aces-sdl.md"
ORACLE_README_PATH = "oracle/README.md"
DESIGN_README_PATH = "design/README.md"
ACES_SDL_PATH = "sdl/keplerops-ai.sdl.yaml"
CORE_NAMESPACE_PREFIX = "core."
ACES_REQUIREMENTS_PATH = "validation/requirements.txt"
ACES_CI_REQUIREMENTS_PATH = "validation/requirements-ci.txt"
ACES_VALIDATOR_PATH = "validation/validate_aces_sdl.py"
ACES_TEST_PATH = "validation/tests/test_validate_aces_sdl.py"
EXPERIMENT_TASK_PATH = "experiments/ctf-evaluation-task.yaml"
REMOVED_PROJECTION_PATHS = (
    "design/topology.yaml",
    "design/software-inventory.yaml",
    "design/implementation-tracking.yaml",
    "assets/planned-assets.yaml",
    "assets/affordances.yaml",
    "assets/oracle/baseline.yaml",
    "build/gcp/build-contract.yaml",
    "build/gcp/runtime-images.yaml",
    "challenges/challenges.yaml",
    "flags/placement.yaml",
    "oracle/objectives.yaml",
    "oracle/atlas-technique-projection.yaml",
    "oracle/scoring.yaml",
    "oracle/telemetry.yaml",
    "telemetry/research-telemetry.yaml",
)
ACES_CONTRACT_PATH = "aces_contract.py"
ORACLE_VALIDATOR_PATH = "validation/validate_oracle.py"
CTFD_README_PATH = "ctfd/README.md"
CTFD_MANIFEST_PATH = "ctfd/keplerops_flag_manifest.py"
CTFD_RECONCILE_PATH = "ctfd/ctfd_reconcile.py"
CTFD_SYNC_PATH = "ctfd/sync_keplerops_ctfd.py"
CTFD_TEST_PATH = "ctfd/tests/test_sync_keplerops_ctfd.py"
BUILD_VALIDATOR_PATH = "build/gcp/validate_build.py"
SDL_REALIZATION_PATH = "build/gcp/render_sdl_realization.py"
FLEET_CAPACITY_PATH = "build/gcp/fleet_capacity.py"
FLEET_CAPACITY_PROFILE_PATH = "build/gcp/fleet-capacity-profile.json"
FLEET_CAPACITY_TEST_PATH = "build/tests/test_fleet_capacity.py"
BUILD_TEST_PATH = "build/tests/test_gcp_build_contract.py"
REHEARSAL_PATH = "tests/live_rehearsal.py"
REHEARSAL_ENTRYPOINT_PATH = "tests/run-golden-rehearsal.sh"
REHEARSAL_TEST_PATH = "tests/test_live_rehearsal.py"
DOC_PATHS = (
    README_PATH,
    CONCEPTS_PATH,
    ATTACK_PATH_PATH,
    ATLAS_DOC_PATH,
    TOPOLOGY_DOC_PATH,
    FLEET_CAPACITY_DOC_PATH,
    LINEAGE_PATH,
)
REQUIRED_PATHS = (
    README_PATH,
    PACK_YAML_PATH,
    COMPATIBILITY_PATH,
    CONCEPTS_PATH,
    ATTACK_PATH_PATH,
    TOPOLOGY_DOC_PATH,
    LINEAGE_PATH,
    PROVENANCE_PATH,
    GOLDEN_CHECKLIST_PATH,
    SDL_README_PATH,
    ORACLE_README_PATH,
    DESIGN_README_PATH,
    ACES_SDL_PATH,
    ACES_CONTRACT_PATH,
    ACES_REQUIREMENTS_PATH,
    ACES_CI_REQUIREMENTS_PATH,
    ACES_VALIDATOR_PATH,
    ACES_TEST_PATH,
    EXPERIMENT_TASK_PATH,
    ORACLE_VALIDATOR_PATH,
    CTFD_README_PATH,
    CTFD_MANIFEST_PATH,
    CTFD_RECONCILE_PATH,
    CTFD_SYNC_PATH,
    CTFD_TEST_PATH,
    BUILD_VALIDATOR_PATH,
    SDL_REALIZATION_PATH,
    FLEET_CAPACITY_PATH,
    FLEET_CAPACITY_PROFILE_PATH,
    FLEET_CAPACITY_TEST_PATH,
    BUILD_TEST_PATH,
    REHEARSAL_PATH,
    REHEARSAL_ENTRYPOINT_PATH,
    REHEARSAL_TEST_PATH,
)
SOURCE_IDS = {"aisf-vegas-2026", "mitre-atlas-data", "original-design"}
REQUIRED_FEATURE_IDS = {
    "atlas-coverage-map",
    "distillation-workflow",
    "enterprise-fabric",
    "open-model-hosting",
}
REQUIRED_BUNDLE_IDS = {
    "core-red-team",
    "executive-sampler",
    "full-red-team",
}
REQUIRED_ACCOUNT_IDS = {
    "core.admin-guardrail",
    "core.domain-administrator",
    "core.participant-operator",
    "core.range-operator",
    "core.svc-distillation",
    "core.svc-inference",
    "core.svc-keycloak-federation",
    "core.svc-registry",
    "core.user-ml-engineer",
    "core.user-qa-intern",
    "core.user-release-manager",
}
REQUIRED_CONTENT_IDS = {
    "core.__private.model-extraction-population-gateway",
    "core.__private.model-extraction-population-workflow",
    "core.__private.model-secrets-population",
    "core.agent-action-package",
    "core.agent-control-tool-state",
    "core.airflow-synthetic-credentials",
    "core.artifact-hash-ledger",
    "core.atlas-challenge-design",
    "core.atlas-technique-catalog",
    "core.bounded-client-results",
    "core.bounded-scan-content",
    "core.bounded-worker-engine-state",
    "core.briefing-pack",
    "core.clean-python-runtime-package",
    "core.context-embedding-model",
    "core.corruption-proof-bundle",
    "core.deployment-manifest",
    "core.distillation-captures",
    "core.distillation-job-output",
    "core.edge-registry-state",
    "core.enterprise-context",
    "core.exfil-proof-bundle",
    "core.image-generation-model-manifest",
    "core.image-generation-schema",
    "core.inference-envoy-config",
    "core.kasmvnc-config",
    "core.keycloak-realm-config",
    "core.lab-readme",
    "core.mail-server-seed",
    "core.masquerading-python-runtime-package",
    "core.model-registry-metadata",
    "core.otel-collector-config",
    "core.participant-synthetic-defaults",
    "core.platform-agent-state",
    "core.platform-context-config",
    "core.platform-deployment-policy",
    "core.platform-isolation-state",
    "core.platform-ml-corpus",
    "core.policy-bundle",
    "core.policy-lab-config",
    "core.portfolio-policy",
    "core.proof-policy",
    "core.public-range-site-content",
    "core.python-runtime-publisher",
    "core.range-dns-config",
    "core.rehearsal-contract",
    "core.research-index-corpus",
    "core.research-index-template",
    "core.research-telemetry-contract",
    "core.retrieval-knowledge-base",
    "core.student-adapter",
    "core.synthetic-eval-set",
    "core.teacher-model",
    "core.teacher-model-artifact-object",
    "core.teacher-model-capstone-manifest",
    "core.telemetry-events",
    "core.text-generation-model-manifest",
    "core.webmail-config",
    "core.workhub-envoy-config",
    "core.workhub-package-credentials",
    "core.company-artifact-state",
    "core.company-data-state",
    "core.company-directory-state",
    "core.company-file-state",
    "core.company-identity-facade-state",
    "core.company-mail-state",
    "core.company-ml-endpoint-state",
    "core.company-model-registry-state",
    "core.company-notebook-state",
    "core.company-operational-telemetry",
    "core.company-policy-state",
    "core.company-research-index-state",
    "core.company-workflow-state",
    "core.company-workforce-endpoint-state",
    "core.company-workhub-state",
}
DOC_ANCHORS = {
    README_PATH: (
        "all 173",
        "34 independent roots",
        "choose",
        "model distillation is mandatory",
        "480-minute event window",
        "gcp",
        "open models",
        "commercial model endpoints",
        "polaris remains a construction reference",
    ),
    CONCEPTS_PATH: (
        "mitre atlas",
        "15 minutes",
        "choose",
        "480-minute event window",
        "commercial model endpoints",
        "enterprise fabric",
    ),
    ATTACK_PATH_PATH: (
        "organizer requirement",
        "gcp-hosted open models",
        "up to 8 hours",
        "34 independent roots",
        "obj-distillation-abuse",
    ),
    TOPOLOGY_DOC_PATH: (
        "participant execution surface",
        "gcp_full",
        "local_reduced",
        "reference triangle",
        "supplied existing",
    ),
}
REQUIRED_ASSET_IDS = {
    "ad-dc-01",
    "participant-workstation",
    "lab-portal",
    "idp-01",
    "repo-ticket-01",
    "inference-gateway",
    "guardrail-policy",
    "model-host-01",
    "ml-workstation-01",
    "model-registry-01",
    "artifact-store-01",
    "dataset-store-01",
    "distillation-runner-01",
    "notebook-runner-01",
    "telemetry-proof-01",
    "exfil-sink",
    "range-ops-controller",
    "range-linux-carrier-01",
    "range-control-carrier-01",
    "range-worker-carrier-01",
    "research-index-01",
    "range-dns-01",
    "public-sites-01",
    "scan-services-01",
    "workforce-workstation-01",
    "platform-impact-01",
}
TEMPLATE_MARKERS = (
    "Copy this directory",
    "One-paragraph pitch",
    "Human-readable title",
    "Name <email>",
    "**Required.**",
    "**Optional.**",
)


def pack_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_yaml(path: str, failures: list[str]) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        failures.append(f"{os.path.relpath(path, pack_root())}: invalid YAML: {exc}")
        return None


def _read_text(root: str, rel_path: str, failures: list[str]) -> str:
    path = os.path.join(root, rel_path)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        failures.append(f"{rel_path}: cannot read: {exc}")
        return ""


def _normalized_text(body: str) -> str:
    return " ".join(body.lower().split())


def _check_required_paths(root: str, failures: list[str]) -> None:
    for rel_path in REQUIRED_PATHS:
        if not os.path.exists(os.path.join(root, rel_path)):
            failures.append(f"{rel_path}: required path missing")


def _check_pack_yaml(root: str, failures: list[str]) -> None:
    pack = _load_yaml(os.path.join(root, PACK_YAML_PATH), failures)
    if not isinstance(pack, dict):
        failures.append("pack.yaml: expected object")
        return
    expected = {
        "name": PACK_ID,
        "title": TITLE,
        "version": VERSION,
        "status": "draft",
        "requirement": REQUIREMENT,
        "compatibility_manifest": COMPATIBILITY_PATH,
        "provenance_ledger": PROVENANCE_PATH,
    }
    for key, value in expected.items():
        if pack.get(key) != value:
            failures.append(f"pack.yaml.{key}: expected {value!r}")
    contents = pack.get("contents")
    if not isinstance(contents, dict):
        failures.append("pack.yaml.contents: expected object")
        return
    expected_contents = {
        "flag_layer": True,
        "reference_triangle": False,
        "profile_bundles": False,
    }
    for key, value in expected_contents.items():
        if contents.get(key) is not value:
            failures.append(f"pack.yaml.contents.{key}: expected {str(value).lower()}")
    flag_paths = (
        ACES_CONTRACT_PATH,
        CTFD_README_PATH,
        CTFD_MANIFEST_PATH,
        CTFD_RECONCILE_PATH,
        CTFD_SYNC_PATH,
        CTFD_TEST_PATH,
    )
    if contents.get("flag_layer") is True:
        missing = [
            path for path in flag_paths if not os.path.isfile(os.path.join(root, path))
        ]
        if missing:
            failures.append(f"flag layer requires all coupled paths; missing {missing}")


def _check_compatibility(root: str, failures: list[str]) -> None:
    manifest = _load_yaml(os.path.join(root, COMPATIBILITY_PATH), failures)
    if not isinstance(manifest, dict):
        failures.append("pack.compatibility.yaml: expected object")
        return
    source = manifest.get("pack", {}).get("source", {})
    if source.get("requirement") != REQUIREMENT:
        failures.append(
            f"pack.compatibility.yaml: source.requirement must be {REQUIREMENT}"
        )
    validation_ids = {
        row.get("id")
        for row in manifest.get("validation", {}).get("commands", [])
        if isinstance(row, dict)
    }
    if "keplerops-ai-contract" not in validation_ids:
        failures.append(
            "pack.compatibility.yaml: missing keplerops-ai-contract validation command"
        )
    profile_ids = {
        row.get("profile_id")
        for row in manifest.get("runtime_profiles", [])
        if isinstance(row, dict)
    }
    if "gcp_full" not in profile_ids:
        failures.append("pack.compatibility.yaml: missing gcp_full runtime profile")
    if "aws_full" in profile_ids:
        failures.append(
            "pack.compatibility.yaml: aws_full must not be the KeplerOps AI Systems golden profile"
        )
    feature_ids = {
        row.get("feature_id")
        for row in manifest.get("platform_features", [])
        if isinstance(row, dict)
    }
    for feature_id in sorted(REQUIRED_FEATURE_IDS - feature_ids):
        failures.append(
            f"pack.compatibility.yaml: missing platform feature {feature_id}"
        )
    bundle_ids = {
        row.get("bundle_id")
        for row in manifest.get("delivery_bundles", [])
        if isinstance(row, dict)
    }
    for bundle_id in sorted(REQUIRED_BUNDLE_IDS - bundle_ids):
        failures.append(f"pack.compatibility.yaml: missing delivery bundle {bundle_id}")


def _check_provenance(root: str, failures: list[str]) -> None:
    ledger = _load_yaml(os.path.join(root, PROVENANCE_PATH), failures)
    if not isinstance(ledger, dict):
        failures.append("docs/provenance-ledger.yaml: expected object")
        return
    if ledger.get("pack", {}).get("name") != PACK_ID:
        failures.append("docs/provenance-ledger.yaml: pack.name must be keplerops-ai")
    if ledger.get("pack", {}).get("version") != VERSION:
        failures.append(f"docs/provenance-ledger.yaml: pack.version must be {VERSION}")
    present = {
        row.get("source_id")
        for row in ledger.get("sources", [])
        if isinstance(row, dict)
    }
    missing = sorted(SOURCE_IDS - present)
    if missing:
        failures.append(f"docs/provenance-ledger.yaml: missing source rows {missing}")
    safety = ledger.get("content_safety", {})
    for key in (
        "no_real_malware",
        "no_real_third_party_targets",
        "no_real_credentials",
        "no_sensitive_data",
        "offensive_tooling_boundary",
    ):
        if safety.get(key) is not True:
            failures.append(
                f"docs/provenance-ledger.yaml: content_safety.{key} must be true"
            )


def _check_removed_projections(root: str, failures: list[str]) -> None:
    for relative in REMOVED_PROJECTION_PATHS:
        if os.path.exists(os.path.join(root, relative)):
            failures.append(f"{relative}: redundant projection must not exist")


def _core_environment(scenario: Any) -> tuple[set[str], set[str], set[str]]:
    core_nodes = {
        name: node
        for name, node in scenario.nodes.items()
        if name.startswith(CORE_NAMESPACE_PREFIX)
    }
    assets = {
        name.removeprefix(CORE_NAMESPACE_PREFIX)
        for name, node in core_nodes.items()
        if node.type.value.lower() == "vm"
    }
    networks = {
        name.removeprefix(CORE_NAMESPACE_PREFIX)
        for name, node in core_nodes.items()
        if node.type.value.lower() == "switch"
    }
    components = {
        name.removeprefix(CORE_NAMESPACE_PREFIX)
        for name in scenario.features
        if name.startswith(CORE_NAMESPACE_PREFIX)
    }
    return assets, networks, components


def _valid_feature_graph(scenario: Any) -> bool:
    backend_realized_hosts = {
        f"{CORE_NAMESPACE_PREFIX}range-linux-carrier-01",
        f"{CORE_NAMESPACE_PREFIX}range-worker-carrier-01",
        f"{CORE_NAMESPACE_PREFIX}range-control-carrier-01",
        f"{CORE_NAMESPACE_PREFIX}ad-dc-01",
        f"{CORE_NAMESPACE_PREFIX}workforce-workstation-01",
        f"{CORE_NAMESPACE_PREFIX}ml-workstation-01",
    }
    for name, node in scenario.nodes.items():
        if (
            not name.startswith(CORE_NAMESPACE_PREFIX)
            or node.type.value.lower() != "vm"
        ):
            continue
        if not node.features:
            if name in backend_realized_hosts:
                continue
            return False
        bound = set(node.features)
        dependencies = {
            dependency
            for feature_id in bound
            for dependency in scenario.features[feature_id].dependencies
        }
        if len(bound - dependencies) != 1 or not dependencies <= bound:
            return False
    return True


def _check_environment_counts(
    scenario: Any,
    assets: set[str],
    networks: set[str],
    components: set[str],
    failures: list[str],
) -> None:
    missing_assets = sorted(REQUIRED_ASSET_IDS - assets)
    if missing_assets:
        failures.append(f"{ACES_SDL_PATH}: missing VM nodes {missing_assets}")
    if len(assets) < 34 or len(networks) != 10 or len(components) < 29:
        failures.append(f"{ACES_SDL_PATH}: incomplete environment module")
    if set(
        scenario.accounts
    ) != REQUIRED_ACCOUNT_IDS or not REQUIRED_CONTENT_IDS <= set(scenario.content):
        failures.append(f"{ACES_SDL_PATH}: incomplete identity or content declarations")
    native_counts = (
        len(scenario.conditions),
        len(scenario.propositions),
        len(scenario.assertions),
        len(scenario.evidence_requirements),
        len(scenario.objectives),
    )
    if native_counts != (134, 135, 135, 135, 134):
        failures.append(
            f"{ACES_SDL_PATH}: incomplete native challenge and operational declarations"
        )


def _check_contract_design(root: str, failures: list[str]) -> None:
    _check_removed_projections(root, failures)
    try:
        scenario = parse_sdl_file(Path(root) / ACES_SDL_PATH)
    except Exception as error:
        failures.append(
            f"{ACES_SDL_PATH}: cannot expand canonical modular SDL: {error}"
        )
        return
    assets, networks, components = _core_environment(scenario)
    _check_environment_counts(scenario, assets, networks, components, failures)
    if not _valid_feature_graph(scenario):
        failures.append(
            f"{ACES_SDL_PATH}: every logical workload VM must bind one root SDL feature and all dependencies"
        )
    participant = scenario.agents.get("core.participant")
    if participant is None or participant.entity != "core.participant-team":
        failures.append(f"{ACES_SDL_PATH}: participant agent binding is missing")


def _check_fleet_capacity(root: str, failures: list[str]) -> None:
    module_path = Path(root) / FLEET_CAPACITY_PATH
    profile_path = Path(root) / FLEET_CAPACITY_PROFILE_PATH
    try:
        spec = importlib.util.spec_from_file_location(
            "keplerops_fleet_capacity_contract", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("module loader unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report = module.calculate(module.load_profile(profile_path))
    except (OSError, RuntimeError, ValueError) as error:
        failures.append(f"{FLEET_CAPACITY_PROFILE_PATH}: invalid capacity contract: {error}")
        return
    ranges = report["ranges"]
    if ranges["total"] != 200:
        failures.append(f"{FLEET_CAPACITY_PROFILE_PATH}: total ranges must remain 200")
    if report["evidence_status"] == "planning_bound" and report["readiness"]["capacity_proven"]:
        failures.append(
            f"{FLEET_CAPACITY_PROFILE_PATH}: planning bounds cannot prove capacity"
        )


def _check_template_markers(docs: dict[str, str], failures: list[str]) -> None:
    for rel_path, body in docs.items():
        for marker in TEMPLATE_MARKERS:
            if marker in body:
                failures.append(f"{rel_path}: template marker remains: {marker}")


def _check_doc_anchors(docs: dict[str, str], failures: list[str]) -> None:
    for rel_path, anchors in DOC_ANCHORS.items():
        body = _normalized_text(docs[rel_path])
        for anchor in anchors:
            if anchor not in body:
                failures.append(f"{rel_path}: missing design anchor {anchor}")


def _check_readme(body: str, failures: list[str]) -> None:
    readme = _normalized_text(body)
    if "participant is the adversary" not in readme:
        failures.append("README.md: must state that the participant is the adversary")
    if "status` remains" not in body and "status: draft" not in readme:
        failures.append("README.md: must preserve the draft status boundary")


def _check_attack_path(body: str, failures: list[str]) -> None:
    if "operator/validator only" not in body.lower():
        failures.append("docs/attack-path.md: must mark the hidden path operator-only")


def _check_lineage(body: str, failures: list[str]) -> None:
    lineage = body.lower()
    for source_id in SOURCE_IDS:
        if source_id not in lineage:
            failures.append(f"docs/lineage.md: missing source id {source_id}")
    for term in ("used:", "excluded:", "local design decisions"):
        if term not in lineage:
            failures.append(f"docs/lineage.md: missing adaptation section {term}")


def _check_docs(root: str, failures: list[str]) -> None:
    docs = {rel_path: _read_text(root, rel_path, failures) for rel_path in DOC_PATHS}
    _check_template_markers(docs, failures)
    _check_doc_anchors(docs, failures)
    _check_readme(docs[README_PATH], failures)
    _check_attack_path(docs[ATTACK_PATH_PATH], failures)
    _check_lineage(docs[LINEAGE_PATH], failures)


def validate_pack(root: str | None = None) -> list[str]:
    root = os.path.abspath(root or pack_root())
    failures: list[str] = []
    _check_required_paths(root, failures)
    _check_pack_yaml(root, failures)
    _check_compatibility(root, failures)
    _check_provenance(root, failures)
    _check_contract_design(root, failures)
    _check_fleet_capacity(root, failures)
    _check_docs(root, failures)
    return failures


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if args != ["validate"]:
        print("usage: validate_contract.py validate", file=sys.stderr)
        return 2
    failures = validate_pack()
    if failures:
        print("KeplerOps AI Systems contract validation failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1
    print("KeplerOps AI Systems contract validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
