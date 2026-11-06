#!/usr/bin/env python3
"""Generate and verify the Cinder Typhoon immutable release manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = ROOT.parent
CANDIDATE_PATH = ROOT / "build/participant-runner/candidate.json"
MANIFEST_PATH = ROOT / "build/release/manifest.json"
ZERO_DIGEST = "sha256:" + "0" * 64
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+\-]{0,159}$")

COMMON_ROOTS = (
    "build/card-coverage",
    "build/fourth-wall",
    "build/hint-delivery",
    "build/input-provenance",
    "build/participant-runner",
    "build/participant-surface",
    "build/release",
    "challenges",
    "ctfd/import_catalog.py",
    "ctfd/prize_policy.py",
    "docs/design/challenge-dependencies.json",
    "docs/design/challenges",
    "docs/design/portfolio.csv",
    "sdl/modules/operations",
)
PHASES = {
    "training": {
        "roots": ("build/training", "assets/training"),
        "compose": "build/training/compose.yaml",
        "restore": "build/training/gcp/deploy.sh",
        "suite": "build/training/tests/test_known_solution_live.py",
        "participant_service": "participant",
        "instance": "cinder-training-golden",
    },
    "keplerops": {
        "roots": (
            "build/keplerops",
            "assets/keplerops/opening",
            "assets/keplerops/registry",
            "assets/keplerops/build-operations",
            "assets/keplerops/policy-compiler",
            "assets/keplerops/connector-archive",
            "assets/keplerops/release-lineage",
        ),
        "compose": "build/keplerops/compose.yaml",
        "restore": "build/keplerops/restore-pristine.sh",
        "suite": "build/keplerops/tests/test_known_solution_live.py",
        "participant_service": "k-dev",
        "instance": "cinder-keplerops-golden",
    },
    "arwc": {
        "roots": (
            "build/arwc",
            "assets/narrative/generated/packages/arwc-documents.json",
        ),
        "compose": "build/arwc/compose.yaml",
        "restore": "build/arwc/restore-pristine.sh",
        "suite": "build/arwc/tests/test_known_solution_live.py",
        "participant_service": "a-connector",
        "instance": "cinder-arwc-golden",
    },
}
EXCLUDED_PATHS = {
    "build/participant-runner/candidate.json",
    "build/release/manifest.json",
}
EXCLUDED_PARTS = {".operator", ".terraform", "__pycache__"}


class ManifestError(RuntimeError):
    """The release cannot be generated or verified."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _included(relative: Path) -> bool:
    value = relative.as_posix()
    return (
        value not in EXCLUDED_PATHS
        and not EXCLUDED_PARTS.intersection(relative.parts)
        and relative.suffix != ".pyc"
    )


def phase_files(phase: str, root: Path = ROOT) -> list[Path]:
    if phase not in PHASES:
        raise ManifestError(f"unknown phase: {phase}")
    files: set[Path] = set()
    for relative_root in (*COMMON_ROOTS, *PHASES[phase]["roots"]):
        path = root / relative_root
        if path.is_file():
            candidates = (path,)
        elif path.is_dir():
            candidates = (item for item in path.rglob("*") if item.is_file())
        else:
            raise ManifestError(f"release input is missing: {relative_root}")
        for candidate in candidates:
            relative = candidate.relative_to(root)
            if _included(relative):
                files.add(relative)
    return sorted(files, key=lambda item: item.as_posix())


def build_input_binding(phase: str, root: Path = ROOT) -> dict[str, Any]:
    records = []
    for relative in phase_files(phase, root):
        path = root / relative
        records.append({
            "path": relative.as_posix(),
            "size": path.stat().st_size,
            "sha256": file_digest(path),
        })
    return {
        "roots": list(COMMON_ROOTS) + list(PHASES[phase]["roots"]),
        "file_count": len(records),
        "sha256": hashlib.sha256(canonical_bytes(records)).hexdigest(),
    }


def release_file_bindings(phase: str, root: Path = ROOT) -> dict[str, dict[str, Any]]:
    paths = {
        "participant_surface": f"build/participant-surface/manifests/{phase}.json",
        "compose": PHASES[phase]["compose"],
        "restore": PHASES[phase]["restore"],
        "acceptance_suite": PHASES[phase]["suite"],
        "participant_runner": "build/participant-runner/run.py",
        "candidate_schema": "build/participant-runner/candidate.schema.json",
        "report_schema": "build/participant-runner/report.schema.json",
    }
    result = {}
    for name, relative in paths.items():
        path = root / relative
        if not path.is_file():
            raise ManifestError(f"release file is missing: {relative}")
        result[name] = {
            "path": relative,
            "size": path.stat().st_size,
            "sha256": file_digest(path),
        }
    return result


def observe_images(phase: str, root: Path = ROOT) -> dict[str, str]:
    compose = root / PHASES[phase]["compose"]
    configured = subprocess.run(
        ["docker", "compose", "-f", str(compose), "--profile", "*", "config", "--format", "json"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if configured.returncode:
        raise ManifestError(f"cannot read {phase} Compose configuration: {configured.stderr.strip()}")
    try:
        services = json.loads(configured.stdout)["services"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ManifestError(f"{phase} Compose configuration is invalid") from error
    images = {}
    for service, configuration in sorted(services.items()):
        image = configuration.get("image")
        if not isinstance(image, str) or not image:
            raise ManifestError(f"{phase}/{service} has no image identity")
        inspected = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{json .Id}}", image],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if inspected.returncode:
            raise ManifestError(f"{phase}/{service} image is not present: {image}")
        try:
            digest = json.loads(inspected.stdout)
        except json.JSONDecodeError as error:
            raise ManifestError(f"{phase}/{service} image identity is invalid") from error
        if not isinstance(digest, str) or not SHA256.fullmatch(digest) or digest == ZERO_DIGEST:
            raise ManifestError(f"{phase}/{service} image identity is not immutable")
        images[service] = digest
    if PHASES[phase]["participant_service"] not in images:
        raise ManifestError(f"{phase} participant image is absent from Compose")
    return images


def observe_phase(phase: str, root: Path = ROOT, *, images: bool = False) -> dict[str, Any]:
    value = {
        "build_inputs": build_input_binding(phase, root),
        "files": release_file_bindings(phase, root),
    }
    if images:
        value["images"] = observe_images(phase, root)
    return value


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=REPOSITORY, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode:
        raise ManifestError(completed.stderr.strip() or "Git command failed")
    return completed.stdout.strip()


def clean_source_commit() -> str:
    commit = _git("rev-parse", "HEAD")
    if not HEX_40.fullmatch(commit):
        raise ManifestError("source commit is not a full Git identity")
    status = _git("status", "--porcelain", "--untracked-files=all", "--", "cinder-typhoon")
    dirty = []
    for line in status.splitlines():
        path = line[3:].split(" -> ")[-1]
        if path not in {
            "cinder-typhoon/build/participant-runner/candidate.json",
            "cinder-typhoon/build/release/manifest.json",
        }:
            dirty.append(line)
    if dirty:
        raise ManifestError("tracked release inputs are dirty")
    return commit


def require_complete_card_coverage(root: Path = ROOT) -> None:
    """Stop promotion before GCP access when reviewed card bindings are stale."""
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "build/card-coverage/coverage.py"),
            "--require-complete",
            "--output",
            os.devnull,
        ],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ManifestError(
            "complete card-coverage gate failed"
            + (f": {detail}" if detail else "")
        )


def _load_catalog_module():
    sys.path.insert(0, str(ROOT / "challenges"))
    import catalog  # type: ignore
    return catalog


def _remote_observation(instance: str, project: str, zone: str, phase: str) -> dict[str, Any]:
    command = (
        "cd /opt/cinder-typhoon && "
        f"sudo python3 build/participant-surface/run.py --phase {phase} >/dev/null && "
        f"sudo python3 build/release/manifest.py observe --phase {phase} --images"
    )
    completed = subprocess.run(
        [
            "gcloud", "compute", "ssh", instance,
            "--project", project, "--zone", zone, "--tunnel-through-iap",
            "--command", command,
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode:
        raise ManifestError(f"{phase} golden observation failed: {completed.stderr.strip()}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ManifestError(f"{phase} golden returned invalid release observation") from error


def _write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def generate(candidate_id: str, project: str, zone: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not SAFE_ID.fullmatch(candidate_id):
        raise ManifestError("candidate ID is invalid")
    source_commit = clean_source_commit()
    require_complete_card_coverage()
    catalog = _load_catalog_module()
    local = {phase: observe_phase(phase) for phase in PHASES}
    remote = {}
    for phase, configuration in PHASES.items():
        observed = _remote_observation(configuration["instance"], project, zone, phase)
        for field in ("build_inputs", "files"):
            if observed.get(field) != local[phase][field]:
                raise ManifestError(f"{phase} golden {field.replace('_', ' ')} differ from source")
        remote[phase] = observed

    artifact_digests = {
        f"{phase}/{service}": digest
        for phase in sorted(remote)
        for service, digest in sorted(remote[phase]["images"].items())
    }
    deployments = {}
    for phase, configuration in PHASES.items():
        images = remote[phase]["images"]
        participant_service = configuration["participant_service"]
        deployments[phase] = {
            "project": project,
            "zone": zone,
            "instance": configuration["instance"],
            "participant_service": participant_service,
            "participant_image_digest": images[participant_service],
            "images": images,
        }
    candidate = {
        "schema_version": 3,
        "candidate_id": candidate_id,
        "immutable": True,
        "source_commit": source_commit,
        "challenge_delivery": catalog.catalog_metadata(),
        "hint_delivery": catalog.hint_manifest_metadata(),
        "artifact_digests": artifact_digests,
        "deployments": deployments,
    }
    _write_json(CANDIDATE_PATH, candidate)
    candidate_digest = file_digest(CANDIDATE_PATH)
    manifest = {
        "schema_version": 1,
        "release_id": candidate_id,
        "source_commit": source_commit,
        "candidate": {
            "path": "build/participant-runner/candidate.json",
            "candidate_id": candidate_id,
            "sha256": candidate_digest,
        },
        "challenge_delivery": candidate["challenge_delivery"],
        "hint_delivery": candidate["hint_delivery"],
        "build_inputs": {phase: local[phase]["build_inputs"] for phase in sorted(local)},
        "file_bindings": {phase: local[phase]["files"] for phase in sorted(local)},
        "deployments": deployments,
    }
    _write_json(MANIFEST_PATH, manifest)
    return candidate, manifest


def validate_release(
    manifest_path: Path, candidate_path: Path, phase: str, root: Path = ROOT,
    *, verify_images: bool = False,
) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_path.read_text())
        candidate = json.loads(candidate_path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManifestError(f"release record cannot be read: {error}") from error
    required = {
        "schema_version", "release_id", "source_commit", "candidate",
        "challenge_delivery", "hint_delivery", "build_inputs", "file_bindings",
        "deployments",
    }
    if not isinstance(manifest, dict) or set(manifest) != required or manifest["schema_version"] != 1:
        raise ManifestError("release manifest fields are invalid")
    if phase not in PHASES:
        raise ManifestError("release phase is invalid")
    if (
        not isinstance(manifest["release_id"], str)
        or not SAFE_ID.fullmatch(manifest["release_id"])
        or not isinstance(manifest["source_commit"], str)
        or not HEX_40.fullmatch(manifest["source_commit"])
    ):
        raise ManifestError("release identity is invalid")
    for field in ("build_inputs", "file_bindings", "deployments"):
        if not isinstance(manifest[field], dict) or set(manifest[field]) != set(PHASES):
            raise ManifestError(f"release {field.replace('_', ' ')} must cover every phase")
    if not isinstance(candidate, dict) or set(candidate.get("deployments", {})) != set(PHASES):
        raise ManifestError("release candidate must cover every phase")
    if manifest["source_commit"] != candidate.get("source_commit"):
        raise ManifestError("release and candidate source commits differ")
    expected_candidate = {
        "path": "build/participant-runner/candidate.json",
        "candidate_id": candidate.get("candidate_id"),
        "sha256": file_digest(candidate_path),
    }
    if manifest["candidate"] != expected_candidate or manifest["release_id"] != candidate.get("candidate_id"):
        raise ManifestError("release candidate binding differs")
    catalog = _load_catalog_module()
    if (
        manifest["challenge_delivery"] != catalog.catalog_metadata()
        or candidate.get("challenge_delivery") != manifest["challenge_delivery"]
    ):
        raise ManifestError("release challenge delivery differs")
    if (
        manifest["hint_delivery"] != catalog.hint_manifest_metadata()
        or candidate.get("hint_delivery") != manifest["hint_delivery"]
    ):
        raise ManifestError("release hint delivery differs")
    observed = observe_phase(phase, root, images=verify_images)
    if manifest["build_inputs"].get(phase) != observed["build_inputs"]:
        raise ManifestError(f"{phase} release build inputs differ")
    if manifest["file_bindings"].get(phase) != observed["files"]:
        raise ManifestError(f"{phase} release files differ")
    deployment = manifest["deployments"].get(phase)
    if not isinstance(deployment, dict) or deployment != candidate.get("deployments", {}).get(phase):
        raise ManifestError(f"{phase} release deployment differs")
    expected_deployment_fields = {
        "project", "zone", "instance", "participant_service",
        "participant_image_digest", "images",
    }
    images = deployment.get("images")
    if (
        set(deployment) != expected_deployment_fields
        or deployment.get("instance") != PHASES[phase]["instance"]
        or deployment.get("participant_service") != PHASES[phase]["participant_service"]
        or not isinstance(images, dict) or not images
        or images.get(deployment["participant_service"]) != deployment.get("participant_image_digest")
        or any(
            not isinstance(digest, str) or not SHA256.fullmatch(digest) or digest == ZERO_DIGEST
            for digest in images.values()
        )
    ):
        raise ManifestError(f"{phase} release deployment identity is invalid")
    if verify_images and deployment["images"] != observed["images"]:
        raise ManifestError(f"{phase} running image inventory differs")
    return {
        "release_id": manifest["release_id"],
        "source_commit": manifest["source_commit"],
        "manifest_sha256": file_digest(manifest_path),
        "candidate_manifest_sha256": expected_candidate["sha256"],
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subcommands = result.add_subparsers(dest="command", required=True)
    observe = subcommands.add_parser("observe")
    observe.add_argument("--phase", choices=sorted(PHASES), required=True)
    observe.add_argument("--images", action="store_true")
    generate_command = subcommands.add_parser("generate")
    generate_command.add_argument("--candidate-id", required=True)
    generate_command.add_argument("--project", default="prod-mgau4w")
    generate_command.add_argument("--zone", default="us-central1-a")
    verify = subcommands.add_parser("verify")
    verify.add_argument("--phase", choices=sorted(PHASES), required=True)
    verify.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    verify.add_argument("--candidate", type=Path, default=CANDIDATE_PATH)
    verify.add_argument("--images", action="store_true")
    return result


def main() -> int:
    arguments = parser().parse_args()
    try:
        if arguments.command == "observe":
            print(json.dumps(observe_phase(arguments.phase, images=arguments.images), sort_keys=True))
        elif arguments.command == "generate":
            candidate, manifest = generate(arguments.candidate_id, arguments.project, arguments.zone)
            print(json.dumps({
                "candidate": candidate["candidate_id"],
                "candidate_sha256": file_digest(CANDIDATE_PATH),
                "release_sha256": file_digest(MANIFEST_PATH),
                "images": len(candidate["artifact_digests"]),
            }, sort_keys=True))
        else:
            print(json.dumps(validate_release(
                arguments.manifest, arguments.candidate, arguments.phase,
                verify_images=arguments.images,
            ), sort_keys=True))
    except ManifestError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
