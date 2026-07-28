#!/usr/bin/env python3
"""Validate the SDL-driven KeplerOps provider realization and immutable inputs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

from render_sdl_realization import RealizationError, build_realization


PACK_ROOT = Path(__file__).resolve().parents[2]
DIGEST_REF = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
LOCK_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ValidationError(ValueError):
    """A bounded build-input failure."""


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path.relative_to(PACK_ROOT)}: mapping required")
    return value


def _validate_terraform_projection(issues: list[str]) -> None:
    main = (PACK_ROOT / "build/gcp/main.tf").read_text(encoding="utf-8")
    required = (
        "sdl_realization  = jsondecode(file(var.sdl_realization_file))",
        "logical_networks = local.sdl_realization.logical_networks",
        "workloads        = local.sdl_realization.workloads",
        "physical_hosts   = local.sdl_realization.physical_hosts",
        "placements       = local.sdl_realization.placements",
        "declared_routes  = local.sdl_realization.declared_routes",
        "runtime_secret_ids = toset(local.sdl_realization.runtime_secret_ids)",
        "for binding in local.sdl_realization.secret_access",
    )
    for declaration in required:
        if declaration not in main:
            issues.append("Terraform must consume the rendered ACES SDL realization directly")
            break
    if re.search(
        r"(?m)^\s*(?:logical_networks|workloads|physical_hosts|placements|declared_routes|secret_access)\s*=\s*\{",
        main,
    ):
        issues.append("Terraform contains a parallel hard-coded scenario projection")


def _validate_runtime_images(
    runtime: dict[str, Any], components: set[str], issues: list[str]
) -> list[str]:
    image_rows = runtime.get("images")
    if not isinstance(image_rows, list):
        issues.append("ACES runtime image projection must be a list")
        image_rows = []
    image_ids = [row.get("component_id") for row in image_rows if isinstance(row, dict)]
    if len(image_ids) != len(set(image_ids)) or set(image_ids) != components:
        issues.append("ACES runtime image projection must bind every root software feature exactly once")
    for row in image_rows:
        component_id = row.get("component_id", "unknown")
        if not isinstance(row.get("source"), str) or not DIGEST_REF.fullmatch(row["source"]):
            issues.append(f"ACES runtime image {component_id}: immutable source required")
        for sidecar in row.get("sidecars", []):
            if not isinstance(sidecar, str) or not DIGEST_REF.fullmatch(sidecar):
                issues.append(f"ACES runtime image {component_id}: immutable dependency required")
        context = row.get("context")
        dockerfile = row.get("dockerfile")
        revision = row.get("build_revision", 1)
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            issues.append(f"ACES runtime image {component_id}: invalid build revision")
        if context is not None:
            if not isinstance(context, str) or not (PACK_ROOT / context).is_dir():
                issues.append(f"ACES runtime image {component_id}: context missing")
            if not isinstance(dockerfile, str) or not (PACK_ROOT / dockerfile).is_file():
                issues.append(f"ACES runtime image {component_id}: Dockerfile missing")
    return image_ids


def _validate_auxiliary_images(runtime: dict[str, Any], issues: list[str]) -> list[str]:
    rows = runtime.get("auxiliary_images")
    if not isinstance(rows, list):
        issues.append("ACES auxiliary image projection must be a list")
        rows = []
    image_ids = [row.get("image_id") for row in rows if isinstance(row, dict)]
    if len(image_ids) != len(set(image_ids)):
        issues.append("ACES feature graph must bind each auxiliary image exactly once")
    for row in rows:
        image_id = row.get("image_id", "unknown")
        if not isinstance(row.get("source"), str) or not DIGEST_REF.fullmatch(row["source"]):
            issues.append(f"ACES auxiliary image {image_id}: immutable source required")
        if not isinstance(row.get("local_tag"), str) or "@" in row["local_tag"]:
            issues.append(f"ACES auxiliary image {image_id}: invalid local tag")
    return image_ids


def _validate_model_manifest(relative: str, issues: list[str]) -> None:
    model = load_yaml(PACK_ROOT / relative)
    revision = (model.get("upstream") or {}).get("revision")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        issues.append(f"model artifact {relative}: immutable revision required")
    rows = model.get("files", [])
    paths = [row.get("path") for row in rows if isinstance(row, dict)]
    if not rows or len(paths) != len(rows) or len(paths) != len(set(paths)):
        issues.append(f"model artifact {relative}: unique files required")
    for row in rows:
        if (
            not isinstance(row, dict)
            or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256", "")))
            or not isinstance(row.get("size"), int)
            or isinstance(row.get("size"), bool)
            or row["size"] <= 0
        ):
            issues.append(f"model artifact {relative}: sha256 and size required")


def _validate_models(issues: list[str]) -> None:
    for relative in (
        "assets/model-artifacts/model.yaml",
        "assets/model-artifacts/embedding-model.yaml",
    ):
        _validate_model_manifest(relative, issues)


def _validate_content_sources(realization: dict[str, Any], issues: list[str]) -> None:
    for content_id, binding in realization["content_bindings"].items():
        source = (binding.get("source") or {}).get("name")
        if isinstance(source, str) and source.startswith("assets/"):
            if not (PACK_ROOT / source).exists():
                issues.append(f"SDL content {content_id}: source path missing")


def _validate_image_lock(
    image_lock: Path,
    components: set[str],
    auxiliary_ids: set[str],
    issues: list[str],
) -> None:
    try:
        lock = json.loads(image_lock.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        issues.append("image lock: unreadable")
        return
    if set(lock) != {"schema_version", "project_id", "images", "auxiliary_images"}:
        issues.append("image lock: invalid fields")
    locked = lock.get("images", {})
    if set(locked) != components:
        issues.append("image lock: incomplete component set")
    for component_id, row in locked.items():
        if set(row) != {"uri", "digest"} or not LOCK_DIGEST.fullmatch(str(row.get("digest", ""))):
            issues.append(f"image lock {component_id}: invalid binding")
    auxiliary_locked = lock.get("auxiliary_images", {})
    if set(auxiliary_locked) != auxiliary_ids:
        issues.append("image lock: incomplete auxiliary image set")
    for image_id, row in auxiliary_locked.items():
        if (
            set(row) != {"uri", "digest", "local_tag"}
            or not LOCK_DIGEST.fullmatch(str(row.get("digest", "")))
            or not isinstance(row.get("local_tag"), str)
        ):
            issues.append(f"image lock {image_id}: invalid auxiliary binding")


def validate(image_lock: Path | None = None) -> list[str]:
    issues: list[str] = []
    try:
        realization = build_realization(PACK_ROOT / "sdl/keplerops-ai.sdl.yaml")
    except (RealizationError, OSError, ValueError) as error:
        return [f"ACES SDL realization: {error}"]
    components = {row["component"] for row in realization["workloads"].values()}
    if len(realization["workloads"]) != 28:
        issues.append("ACES SDL realization must project exactly 28 logical workloads")
    if len(realization["physical_hosts"]) != 7:
        issues.append("ACES SDL realization must project exactly seven range kernels")
    if len(realization["logical_networks"]) != 10:
        issues.append("ACES SDL realization must preserve ten logical network zones")
    if len(realization["placements"]) != 26:
        issues.append("ACES SDL realization must project every packed workload placement")
    if set(realization["deployment_cells"]) != {"range-cell", "shared-model-cell"}:
        issues.append("ACES SDL realization must project range and shared-model deployment cells")
    if set(realization["identity_topology"]["relationships"]) != {
        "ad-domain-controller",
        "workforce-domain-join",
        "ml-domain-join",
        "workforce-directory-federation",
    }:
        issues.append("ACES SDL realization must project complete enterprise identity topology")
    if set(realization["shared_services"]) != {"shared-inference-service"}:
        issues.append("ACES SDL realization must project the shared inference contract")
    if len(realization["declared_routes"]) < 31:
        issues.append("ACES SDL realization must preserve the 31-route foundation")
    if len(realization["service_bindings"]) < 22:
        issues.append("ACES SDL realization must preserve the 22-service foundation")

    _validate_terraform_projection(issues)
    _validate_content_sources(realization, issues)
    runtime = {
        "images": realization["runtime_images"],
        "auxiliary_images": realization["auxiliary_images"],
    }
    _validate_runtime_images(runtime, components, issues)
    auxiliary_ids = set(_validate_auxiliary_images(runtime, issues))
    _validate_models(issues)
    if image_lock is not None:
        _validate_image_lock(image_lock, components, auxiliary_ids, issues)
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-lock", type=Path)
    args = parser.parse_args()
    issues = validate(args.image_lock)
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("KeplerOps SDL-driven GCP realization valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
