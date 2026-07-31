#!/usr/bin/env python3
"""Render the GCP provider projection directly from the canonical ACES SDL."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import yaml
from raes import parse_sdl_file
from raes_processor.compiler import compile_scenario_runtime_model
from raes_processor.models import resource_payload


PACK_ROOT = Path(__file__).resolve().parents[2]
SDL_ROOT = PACK_ROOT / "sdl" / "keplerops-ai.sdl.yaml"
RAES_VERSION = "2.0.0"
CORE_PREFIX = "core."
CHALLENGE_EXTENSION = "x-keplerops:challenge"
MODULE_EXTENSION = "x-keplerops:portfolio-module"
MACHINE_TYPES = {
    (2, 2 * 1024**3): "e2-small",
    (2, 4 * 1024**3): "e2-medium",
    (2, 8 * 1024**3): "e2-standard-2",
    (4, 16 * 1024**3): "e2-standard-4",
    (8, 30 * 1024**3): "n1-standard-8",
    (4, 8 * 1024**3): "n2-custom-4-8192",
    (8, 16 * 1024**3): "n2-custom-8-16384",
    (4, 32 * 1024**3): "n2-highmem-4",
    (24, 96 * 1024**3): "n2-custom-24-98304",
}
DISK_GIB_BY_COMPONENT = {
    "keplerops-platform-agent": 50,
    "keplerops-platform-impact": 50,
    "keplerops-platform-ml": 50,
    "llamacpp-text-generation": 50,
    "openvino-image-generation": 100,
    "opensearch-research-index": 80,
    "stalwart-mail-server": 50,
    "vllm-open-model-hosting": 100,
}
WINDOWS_HOST_DISK_GIB = 50
LINUX_HOST_DISK_GIB = 30
PACKED_WORKLOAD_RESERVE_GIB = 5
SUPPORTED_PROTOCOLS = {"tcp", "udp"}
PORT_RANGE_SEPARATOR = "-"
EVIDENCE_PRODUCER_COMPONENTS = {
    "airflow-distillation-runner",
    "coredns-authoritative-dns",
    "envoy-fastapi-inference-gateway",
    "keplerops-platform-impact",
    "keplerops-platform-ml",
    "keplerops-platform-agent",
    "keplerops-lab-portal",
    "minio-exfil-sink",
    "mlflow-model-registry",
    "nginx-bounded-scan-targets",
    "nginx-public-range-sites",
    "opa-guardrail-policy",
    "opensearch-research-index",
    "opentelemetry-proof-store",
    "keplerops-policy-lab",
    "terraform-gcp-range-controller",
    "vllm-open-model-hosting",
}
SERVICE_TOKEN_COMPONENTS = {
    "envoy-fastapi-inference-gateway",
    "keplerops-lab-portal",
    "opa-guardrail-policy",
    "opentelemetry-proof-store",
    "terraform-gcp-range-controller",
}
MINIO_CREDENTIAL_COMPONENTS = {
    "minio-artifact-store",
    "minio-exfil-sink",
    "mlflow-model-registry",
    "vllm-open-model-hosting",
}
POSTGRES_CREDENTIAL_COMPONENTS = {
    "airflow-distillation-runner",
    "envoy-fastapi-inference-gateway",
    "jupyterlab-notebook-runner",
    "postgresql-dataset-store",
}


class RealizationError(ValueError):
    """Raised when the SDL cannot be projected without guessing."""


def _physical_host_disk_gib(
    operating_system: str, assigned_workloads: list[dict[str, Any]]
) -> int:
    if operating_system == "windows":
        return WINDOWS_HOST_DISK_GIB
    if not assigned_workloads:
        return LINUX_HOST_DISK_GIB
    return max(workload["disk_gib"] for workload in assigned_workloads) + (
        PACKED_WORKLOAD_RESERVE_GIB * (len(assigned_workloads) - 1)
    )


def _apply_workload_startup_order(
    scenario: Any, workloads: dict[str, dict[str, Any]]
) -> None:
    dependencies = {workload_id: set() for workload_id in workloads}
    for qualified, relationship in scenario.relationships.items():
        if (
            not qualified.startswith(CORE_PREFIX)
            or relationship.type.value != "depends_on"
        ):
            continue
        source = _local_name(relationship.source)
        target = _local_name(relationship.target)
        if source in workloads and target in workloads and source != target:
            dependencies[source].add(target)

    ranks: dict[str, int] = {}
    pending = set(workloads)
    while pending:
        ready = sorted(
            workload_id
            for workload_id in pending
            if not dependencies[workload_id].intersection(pending)
        )
        if not ready:
            raise RealizationError(
                "workload dependency cycle prevents deterministic startup: "
                + ", ".join(sorted(pending))
            )
        for workload_id in ready:
            ranks[workload_id] = max(
                (ranks[dependency] + 1 for dependency in dependencies[workload_id]),
                default=0,
            )
        pending.difference_update(ready)

    for workload_id, workload in workloads.items():
        workload["startup_dependencies"] = sorted(dependencies[workload_id])
        workload["startup_rank"] = ranks[workload_id]


def _require_pinned_aces() -> None:
    try:
        installed = version("raes")
    except PackageNotFoundError as error:
        raise RealizationError(
            f"raes=={RAES_VERSION} must be installed from PyPI"
        ) from error
    if installed != RAES_VERSION:
        raise RealizationError(
            f"raes=={RAES_VERSION} is required, found {installed}"
        )


def _local_name(value: str, *, prefix: str = CORE_PREFIX) -> str:
    if not value.startswith(prefix) or len(value) == len(prefix):
        raise RealizationError(f"unexpected expanded SDL identity: {value}")
    return value[len(prefix) :]


def _target_name(value: str, section: str) -> str:
    return _local_name(value, prefix=f"{section}.{CORE_PREFIX}")


def _valid_port_spec(value: str) -> bool:
    if value.isdigit():
        return 1 <= int(value) <= 65535
    if PORT_RANGE_SEPARATOR not in value:
        return False
    start, end = value.split(PORT_RANGE_SEPARATOR, 1)
    return (
        start.isdigit()
        and end.isdigit()
        and 1 <= int(start) <= int(end) <= 65535
    )


def _port_sort_key(value: str) -> tuple[int, int]:
    if PORT_RANGE_SEPARATOR in value:
        start, end = value.split(PORT_RANGE_SEPARATOR, 1)
        return int(start), int(end)
    return int(value), int(value)


def _machine_type(node: Any) -> str:
    resources = node.resources
    if resources is None or not isinstance(resources.cpu, int) or not isinstance(resources.ram, int):
        raise RealizationError("every realized VM requires concrete CPU and RAM")
    machine = MACHINE_TYPES.get((resources.cpu, resources.ram))
    if machine is None:
        raise RealizationError(
            f"no GCP realization for CPU/RAM tuple {resources.cpu}/{resources.ram}"
        )
    return machine


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _is_green_live_activity_behavior(behavior: Any) -> bool:
    policy = getattr(behavior, "autonomous_execution", None)
    authority = getattr(policy, "evaluation_authority", None)
    return (
        _value(getattr(behavior, "behavior_mode", None)) == "autonomous"
        and "green" in [str(_value(role)) for role in getattr(behavior, "participant_role_refs", [])]
        and _value(getattr(authority, "mode", None)) == "none"
        and getattr(policy, "profile", None) == "participant-autonomous-execution/v3"
    )


def _behavior_contract_counts(scenario: Any) -> tuple[int, int, int]:
    challenge_count = 0
    module_count = 0
    green_activity_count = 0
    for behavior in scenario.behavior_specifications.values():
        extensions = behavior.extensions if isinstance(behavior.extensions, dict) else {}
        challenge = extensions.get(CHALLENGE_EXTENSION)
        module = extensions.get(MODULE_EXTENSION)
        green_activity = _is_green_live_activity_behavior(behavior)
        if isinstance(challenge, dict):
            challenge_count += 1
        if isinstance(module, dict):
            module_count += 1
        if green_activity:
            green_activity_count += 1
        if sum((isinstance(challenge, dict), isinstance(module, dict), green_activity)) != 1:
            raise RealizationError(
                "every SDL behavior must declare exactly one KeplerOps module, challenge, or green live-activity contract"
            )
    return challenge_count, module_count, green_activity_count


def _research_source_components(
    scenario: Any, assets: dict[str, dict[str, Any]]
) -> set[str]:
    contract = scenario.content.get(f"{CORE_PREFIX}research-telemetry-contract")
    if contract is None or not isinstance(contract.text, str):
        raise RealizationError("SDL research telemetry contract is required")
    try:
        payload = yaml.safe_load(contract.text)
    except yaml.YAMLError as error:
        raise RealizationError("SDL research telemetry contract must be YAML") from error
    sources = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(sources, list) or not sources:
        raise RealizationError("SDL research telemetry contract requires sources")
    source_assets = []
    for source in sources:
        if not isinstance(source, dict):
            raise RealizationError("SDL research telemetry sources must be mappings")
        asset = source.get("asset")
        if asset is None:
            continue
        if not isinstance(asset, str):
            raise RealizationError("SDL research telemetry source assets must be strings")
        source_assets.append(asset)
    if not source_assets:
        raise RealizationError("SDL research telemetry sources must name assets")
    missing = set(source_assets) - set(assets)
    if missing:
        raise RealizationError(
            f"SDL research telemetry sources reference missing assets: {sorted(missing)}"
        )
    return {assets[asset]["component"] for asset in source_assets}


def _root_feature(node: Any, scenario: Any, asset: str) -> str:
    bound = set(node.features)
    dependencies = {
        dependency
        for feature_id in bound
        for dependency in scenario.features[feature_id].dependencies
        if dependency in bound
    }
    roots = bound - dependencies
    if len(roots) != 1:
        raise RealizationError(f"asset {asset} must have exactly one root SDL software feature")
    return _local_name(roots.pop())


def _source_reference(source: Any, feature_id: str) -> str:
    if source is None:
        raise RealizationError(f"feature {feature_id} requires an immutable ACES source")
    if source.build is not None:
        base = source.build.base_image
        digest = source.build.base_image_digest
        if not base or not digest:
            raise RealizationError(f"feature {feature_id} requires an immutable ACES base image")
        return f"{base}@{digest}"
    if not source.name or not source.version or source.version == "*":
        raise RealizationError(f"feature {feature_id} requires an immutable ACES source")
    return f"{source.name}:{source.version}"


def _image_plan(scenario: Any, components: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    images: list[dict[str, Any]] = []
    auxiliary: dict[str, dict[str, Any]] = {}
    for component in sorted(components):
        feature = scenario.features[f"{CORE_PREFIX}{component}"]
        source = feature.source
        row: dict[str, Any] = {
            "component_id": component,
            "source": _source_reference(source, component),
            "mirror": f"keplerops/{component}",
        }
        if source is not None and source.build is not None:
            if not source.version.isdigit() or not source.build.dockerfile_path:
                raise RealizationError(f"feature {component} has an incomplete ACES build recipe")
            row.update(
                context=".",
                dockerfile=source.build.dockerfile_path,
                build_revision=int(source.version),
            )
        sidecars: list[str] = []
        auxiliary_image_ids: list[str] = []
        for dependency_ref in feature.dependencies:
            dependency_id = _local_name(dependency_ref)
            dependency = scenario.features[dependency_ref]
            dependency_source = _source_reference(dependency.source, dependency_id)
            dependency_build = dependency.source.build if dependency.source else None
            root_build = feature.source.build if feature.source else None
            independently_built = (
                dependency_build is not None
                and (
                    root_build is None
                    or dependency_build.dockerfile_path != root_build.dockerfile_path
                )
            )
            if dependency.type.value == "artifact" or independently_built:
                dependency_row: dict[str, Any] = {
                    "image_id": dependency_id,
                    "source": dependency_source,
                    "mirror": f"keplerops/{dependency_id}",
                    "local_tag": dependency_source.split("@", 1)[0],
                }
                if dependency_build is not None:
                    dependency_version = dependency.source.version
                    if not dependency_version.isdigit() or not dependency_build.dockerfile_path:
                        raise RealizationError(
                            f"feature {dependency_id} has an incomplete ACES build recipe"
                        )
                    dependency_row.update(
                        context=".",
                        dockerfile=dependency_build.dockerfile_path,
                        build_revision=int(dependency_version),
                    )
                auxiliary[dependency_id] = dependency_row
                auxiliary_image_ids.append(dependency_id)
            else:
                sidecars.append(dependency_source)
        if auxiliary_image_ids:
            row["auxiliary_image_ids"] = sorted(auxiliary_image_ids)
        if sidecars:
            row["sidecars"] = sidecars
        images.append(row)
    return images, [auxiliary[key] for key in sorted(auxiliary)]


def _credential_plan(
    scenario: Any, assets: dict[str, dict[str, Any]]
) -> tuple[list[str], list[str], list[str], dict[str, dict[str, Any]]]:
    """Project workload-secret bindings from the expanded SDL world."""

    by_component = {row["component"]: asset_id for asset_id, row in assets.items()}
    if len(by_component) != len(assets):
        raise RealizationError("every realized component must have exactly one owning asset")
    range_assets = {
        asset_id: row
        for asset_id, row in assets.items()
        if row["deployment_cell"] == "range-cell"
    }
    range_components = {row["component"] for row in range_assets.values()}

    def owners(components: set[str], *, range_only: bool = False) -> set[str]:
        if range_only:
            components = components & range_components
        missing = components - set(by_component)
        if missing:
            raise RealizationError(
                f"credential plan references missing SDL components: {sorted(missing)}"
            )
        return {by_component[component] for component in components}

    research_producer_components = _research_source_components(scenario, assets)
    evidence_producers = owners(
        EVIDENCE_PRODUCER_COMPONENTS | research_producer_components,
        range_only=True,
    )
    runtime_secret_ids = {
        "jupyter-token",
        "minio-root-password",
        "minio-root-user",
        "participant-password",
        "postgres-password",
        "receipt-signing-key",
        "research-content-key",
        "research-pseudonym-key",
        "service-token",
        "platform-context-token",
        "keycloak-platform-context-secret",
        "platform-agent-admin-token",
        "platform-agent-seed-token",
        "platform-isolation-admin-token",
        "edge-registry-admin-token",
        "platform-deployment-token",
        "gitea-registry-credential",
        "reputation-signing-key",
        "ad-domain-admin-password",
        "ad-federation-bind-password",
        "ad-guardrail-admin-password",
        "ad-ml-engineer-password",
        "ad-qa-password",
        "ad-release-manager-password",
        "tls-ad-dc-01",
        *(f"producer-token-{asset_id}" for asset_id in evidence_producers),
        *(f"tls-{asset_id}" for asset_id in range_assets),
    }
    secret_access = {
        f"{asset_id}/tls-{asset_id}" for asset_id in range_assets
    }
    secret_access.update(
        f"{asset_id}/service-token" for asset_id in owners(SERVICE_TOKEN_COMPONENTS)
    )
    secret_access.update(
        f"{asset_id}/producer-token-{asset_id}" for asset_id in evidence_producers
    )
    proof_asset = by_component["opentelemetry-proof-store"]
    secret_access.update(
        f"{proof_asset}/producer-token-{asset_id}" for asset_id in evidence_producers
    )
    secret_access.update(
        {
            f"{proof_asset}/receipt-signing-key",
            f"{proof_asset}/research-content-key",
            f"{proof_asset}/research-pseudonym-key",
        }
    )
    for asset_id in owners(MINIO_CREDENTIAL_COMPONENTS, range_only=True):
        secret_access.update(
            {f"{asset_id}/minio-root-user", f"{asset_id}/minio-root-password"}
        )
    for asset_id in owners(POSTGRES_CREDENTIAL_COMPONENTS):
        secret_access.add(f"{asset_id}/postgres-password")
    secret_access.add(f'{by_component["jupyterlab-notebook-runner"]}/jupyter-token')
    secret_access.add(
        f'{by_component["terraform-gcp-range-controller"]}/jupyter-token'
    )
    secret_access.add(f'{by_component["kali-browser-terminal"]}/participant-password')
    secret_access.update(
        {
            "ad-dc-01/ad-domain-admin-password",
            "ad-dc-01/ad-federation-bind-password",
            "ad-dc-01/ad-guardrail-admin-password",
            "ad-dc-01/ad-ml-engineer-password",
            "ad-dc-01/ad-qa-password",
            "ad-dc-01/ad-release-manager-password",
            "ad-dc-01/tls-ad-dc-01",
            "workforce-workstation-01/ad-domain-admin-password",
            "workforce-workstation-01/ad-qa-password",
            "workforce-workstation-01/ad-release-manager-password",
            "ml-workstation-01/ad-domain-admin-password",
            "ml-workstation-01/ad-ml-engineer-password",
            f'{by_component["keycloak-identity"]}/ad-federation-bind-password',
        }
    )
    workhub_asset = by_component["gitea-redmine-workhub"]
    secret_access.update(
        {
            f"{workhub_asset}/platform-context-token",
            f"{workhub_asset}/keycloak-platform-context-secret",
        }
    )

    credential_dependencies: dict[str, dict[str, Any]] = {}
    for qualified, relationship in scenario.relationships.items():
        credentials_text = relationship.properties.get("credentials", "")
        if relationship.type.value != "depends_on" or not credentials_text:
            continue
        relationship_id = _local_name(qualified)
        source = _local_name(relationship.source)
        target = _local_name(relationship.target)
        credentials = sorted(set(credentials_text.split(",")))
        if source not in assets or target not in assets:
            raise RealizationError(
                f"credential dependency {relationship_id} must join realized SDL assets"
            )
        if not credentials or any(secret not in runtime_secret_ids for secret in credentials):
            raise RealizationError(
                f"credential dependency {relationship_id} references an unknown runtime secret"
            )
        capability = relationship.properties.get("capability", "")
        if not capability:
            raise RealizationError(
                f"credential dependency {relationship_id} requires an SDL capability"
            )
        secret_access.update(f"{source}/{secret}" for secret in credentials)
        credential_dependencies[relationship_id] = {
            "source": source,
            "target": target,
            "capability": capability,
            "credentials": credentials,
        }

    return (
        sorted(runtime_secret_ids),
        sorted(secret_access),
        sorted(evidence_producers),
        credential_dependencies,
    )


def _service_materialization_plan(scenario: Any) -> dict[str, dict[str, Any]]:
    """Compile portable service-owned content through the RAES processor."""
    runtime_model = compile_scenario_runtime_model(scenario)
    prefix = "provision.content.core."
    materializations: dict[str, dict[str, Any]] = {}
    for address, placement in runtime_model.content_placements.items():
        if placement.service_materialization is None:
            continue
        if not address.startswith(prefix):
            raise RealizationError(
                f"service materialization has unexpected address {address}"
            )
        content_id = address.removeprefix(prefix)
        materializations[content_id] = {
            "address": address,
            "resource_type": "content-placement",
            "dependencies": list(placement.ordering_dependencies),
            "payload": resource_payload(placement),
        }
    return materializations


def build_realization(sdl_root: Path = SDL_ROOT) -> dict[str, Any]:
    """Expand the modular SDL and build the complete GCP input projection."""

    _require_pinned_aces()
    scenario = parse_sdl_file(sdl_root)

    networks: dict[str, str] = {}
    for qualified, node in scenario.nodes.items():
        if not qualified.startswith(CORE_PREFIX) or node.type.value.lower() != "switch":
            continue
        local = _local_name(qualified)
        infrastructure = scenario.infrastructure.get(qualified)
        properties = infrastructure.properties if infrastructure is not None else None
        cidr = getattr(properties, "cidr", "")
        if not isinstance(cidr, str) or not cidr:
            raise RealizationError(f"network {local} requires an SDL CIDR")
        network = ipaddress.ip_network(cidr, strict=True)
        if not isinstance(network, ipaddress.IPv4Network) or network.prefixlen != 24:
            raise RealizationError(f"network {local} must use a private IPv4 /24")
        if not network.is_private:
            raise RealizationError(f"network {local} must be private")
        networks[local] = str(network)

    placement_relationships = {
        _local_name(relationship.source): relationship
        for qualified, relationship in scenario.relationships.items()
        if qualified.startswith(CORE_PREFIX)
        and relationship.type.value == "placed_on_carrier"
    }
    placements = {
        source: {
            "host": _local_name(relationship.target),
            "kernel_boundary": relationship.carrier_placement.kernel_boundary.value,
        }
        for source, relationship in placement_relationships.items()
    }
    deployment_cells = {
        _local_name(qualified): {
            "tenant": _local_name(cell.tenant_ref),
            "nodes": sorted(_local_name(node_ref) for node_ref in cell.node_refs),
            "cross_tenant_isolation": cell.cross_tenant_isolation.value,
        }
        for qualified, cell in scenario.deployment_cells.items()
        if qualified.startswith(CORE_PREFIX)
    }
    cell_by_node = {
        node: cell_id
        for cell_id, cell in deployment_cells.items()
        for node in cell["nodes"]
    }
    shared_target_nodes = {
        _target_name(relationship.target.rsplit(".services.", 1)[0], "nodes")
        for qualified, relationship in scenario.relationships.items()
        if qualified.startswith(CORE_PREFIX)
        and relationship.type.value == "uses_shared_service"
    }

    ordinals = {network: 10 for network in networks}
    workloads: dict[str, dict[str, Any]] = {}
    service_bindings: dict[str, str] = {}
    for qualified, node in scenario.nodes.items():
        if not qualified.startswith(CORE_PREFIX) or node.type.value.lower() != "vm":
            continue
        asset = _local_name(qualified)
        infrastructure = scenario.infrastructure.get(qualified)
        links = infrastructure.links if infrastructure is not None else []
        link_names = [_local_name(link) for link in links]
        if any(network_name not in networks for network_name in link_names):
            raise RealizationError(f"node {asset} links an unknown SDL network")
        tcp_ports: list[str] = []
        udp_ports: list[str] = []
        for service in node.services:
            if not isinstance(service.port, int):
                raise RealizationError(f"service on {asset} requires a concrete port")
            protocol = service.protocol.lower()
            if protocol not in SUPPORTED_PROTOCOLS:
                raise RealizationError(
                    f"service on {asset} uses unsupported protocol {protocol}"
                )
            (tcp_ports if protocol == "tcp" else udp_ports).append(str(service.port))
        if node.features:
            if len(link_names) != 1:
                raise RealizationError(
                    f"logical workload {asset} must link exactly one SDL network"
                )
            network_name = link_names[0]
            component = _root_feature(node, scenario, asset)
            subnet = ipaddress.ip_network(networks[network_name])
            ordinal = ordinals[network_name]
            address = ipaddress.ip_address(int(subnet.network_address) + ordinal)
            if address not in subnet or address in {subnet.network_address, subnet.broadcast_address}:
                raise RealizationError(f"workload {asset} has no available deterministic address")
            ordinals[network_name] += 1
            workloads[asset] = {
                "network": network_name,
                "component": component,
                "ip": str(address),
                "disk_gib": DISK_GIB_BY_COMPONENT.get(component, 30),
                "tcp_ports": sorted(set(tcp_ports), key=int),
                "udp_ports": sorted(set(udp_ports), key=int),
                "host": placements.get(asset, {}).get("host", asset),
                "deployment_cell": cell_by_node.get(asset),
            }
        for service in node.services:
            if not service.name or service.name in service_bindings:
                raise RealizationError("SDL service names must be present and globally unique")
            service_bindings[service.name] = asset

    _apply_workload_startup_order(scenario, workloads)

    physical_hosts: dict[str, dict[str, Any]] = {}
    for qualified, node in scenario.nodes.items():
        if not qualified.startswith(CORE_PREFIX) or node.type.value.lower() != "vm":
            continue
        host = _local_name(qualified)
        if host in placements or host in shared_target_nodes:
            continue
        infrastructure = scenario.infrastructure.get(qualified)
        links = infrastructure.links if infrastructure is not None else []
        link_names = [_local_name(link) for link in links]
        if not link_names:
            raise RealizationError(f"physical host {host} requires an SDL network")
        assigned_workloads = [
            workload for workload in workloads.values() if workload["host"] == host
        ]
        physical_hosts[host] = {
            "machine": _machine_type(node),
            "os": node.os,
            "os_version": node.os_version,
            "endpoint_persona": node.endpoint_persona.value if node.endpoint_persona else None,
            "logical_networks": link_names,
            "deployment_cell": cell_by_node.get(host),
            "disk_gib": _physical_host_disk_gib(node.os, assigned_workloads),
        }

    routes: dict[str, dict[str, Any]] = {}
    for qualified, relationship in scenario.relationships.items():
        if not qualified.startswith(CORE_PREFIX):
            continue
        route = _local_name(qualified)
        ports_text = relationship.properties.get("ports", "")
        protocols_text = relationship.properties.get("protocols", "tcp")
        destination_asset: str | None = None
        if relationship.type.value == "connects_to":
            source = _target_name(relationship.source, "infrastructure")
            destination = _target_name(relationship.target, "infrastructure")
        elif relationship.type.value == "depends_on" and ports_text:
            source_asset = _local_name(relationship.source)
            destination_asset = _local_name(relationship.target)
            if source_asset not in workloads or destination_asset not in workloads:
                raise RealizationError(
                    f"route {route} must join realized SDL assets"
                )
            source = workloads[source_asset]["network"]
            destination = workloads[destination_asset]["network"]
        else:
            continue
        ports = ports_text.split(",") if ports_text else []
        if source not in networks or destination not in networks or not ports:
            raise RealizationError(f"route {route} is not a complete SDL network route")
        if any(not _valid_port_spec(port) for port in ports):
            raise RealizationError(f"route {route} contains an invalid port")
        protocols = protocols_text.split(",") if protocols_text else []
        if not protocols or any(protocol not in SUPPORTED_PROTOCOLS for protocol in protocols):
            raise RealizationError(f"route {route} contains an invalid protocol")
        if destination_asset is not None and "udp" in protocols:
            target_udp = set(workloads[destination_asset]["udp_ports"])
            target_udp.update(ports)
            workloads[destination_asset]["udp_ports"] = sorted(
                target_udp, key=_port_sort_key
            )
        routes[route] = {
            "source": source,
            "destination": destination,
            "ports": ports,
            "protocols": sorted(set(protocols)),
        }

    account_bindings = {
        _local_name(qualified): _local_name(account.node)
        for qualified, account in scenario.accounts.items()
        if qualified.startswith(CORE_PREFIX)
    }
    content_bindings: dict[str, dict[str, Any]] = {}
    for qualified, content in scenario.content.items():
        if not qualified.startswith(CORE_PREFIX):
            continue
        binding = content.model_dump(mode="json", exclude_none=True)
        binding["target"] = _local_name(content.target)
        content_bindings[_local_name(qualified)] = binding
    behaviors = sorted(scenario.behavior_specifications)
    runtime_images, auxiliary_images = _image_plan(
        scenario,
        {row["component"] for row in workloads.values()},
    )
    runtime_secret_ids, secret_access, evidence_producers, credential_dependencies = (
        _credential_plan(scenario, workloads)
    )
    identity_topology = {
        "domains": {
            _local_name(name): value.model_dump(mode="json", exclude_none=True)
            for name, value in scenario.identity_domains.items()
            if name.startswith(CORE_PREFIX)
        },
        "forests": {
            _local_name(name): value.model_dump(mode="json", exclude_none=True)
            for name, value in scenario.identity_forests.items()
            if name.startswith(CORE_PREFIX)
        },
        "facades": {
            _local_name(name): value.model_dump(mode="json", exclude_none=True)
            for name, value in scenario.identity_facades.items()
            if name.startswith(CORE_PREFIX)
        },
        "relationships": {
            _local_name(name): relationship.model_dump(mode="json", exclude_none=True)
            for name, relationship in scenario.relationships.items()
            if name.startswith(CORE_PREFIX)
            and relationship.type.value
            in {"domain_controller_for", "joins_domain", "directory_federates_to"}
        },
    }
    shared_services = {
        _local_name(name): relationship.model_dump(mode="json", exclude_none=True)
        for name, relationship in scenario.relationships.items()
        if name.startswith(CORE_PREFIX)
        and relationship.type.value == "uses_shared_service"
    }
    service_materializations = _service_materialization_plan(scenario)
    challenge_count, module_count, green_activity_count = _behavior_contract_counts(scenario)
    if (
        not networks
        or not workloads
        or not physical_hosts
        or challenge_count < 60
        or module_count != 10
        or green_activity_count != 1
        or len(behaviors) != challenge_count + module_count + green_activity_count
    ):
        raise RealizationError("expanded SDL is not a complete KeplerOps scenario")

    payload: dict[str, Any] = {
        "schema_version": 3,
        "sdl_source": "sdl/keplerops-ai.sdl.yaml",
        "sdl_version": scenario.version,
        "logical_networks": networks,
        "workloads": workloads,
        "physical_hosts": physical_hosts,
        "placements": placements,
        "deployment_cells": deployment_cells,
        "identity_topology": identity_topology,
        "shared_services": shared_services,
        "declared_routes": routes,
        "service_bindings": service_bindings,
        "account_bindings": account_bindings,
        "content_bindings": content_bindings,
        "service_materializations": service_materializations,
        "runtime_secret_ids": runtime_secret_ids,
        "secret_access": secret_access,
        "evidence_producers": evidence_producers,
        "credential_dependencies": credential_dependencies,
        "behavior_specifications": behaviors,
        "runtime_images": runtime_images,
        "auxiliary_images": auxiliary_images,
    }
    payload["sdl_digest"] = _canonical_digest(payload)
    return payload


def write_realization(destination: Path, payload: dict[str, Any]) -> None:
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".sdl-realization-", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = build_realization()
    if args.output is not None:
        write_realization(args.output, payload)
    else:
        print(json.dumps({
            "physical_hosts": len(payload["physical_hosts"]),
            "workloads": len(payload["workloads"]),
            "behaviors": len(payload["behavior_specifications"]),
            "logical_networks": len(payload["logical_networks"]),
            "routes": len(payload["declared_routes"]),
            "sdl_digest": payload["sdl_digest"],
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RealizationError as error:
        print(f"error: {error}")
        raise SystemExit(2) from None
