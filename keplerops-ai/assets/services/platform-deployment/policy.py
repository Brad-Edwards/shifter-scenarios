"""ACES-realized authority contract consumed by the deployment boundary."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from security import require_digest, require_repository


PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
REGION = re.compile(r"^[a-z]+-[a-z]+\d$", re.ASCII)
SERVICE_ACCOUNT_NAME = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
BUCKET = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
PROFILE = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
TENANT = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$")
IMAGE_TAG = re.compile(r"^\w[\w.-]{0,127}$", re.ASCII)
POLICY_FIELDS = {
    "schema_version",
    "range_instance",
    "participant",
    "project_id",
    "region",
    "service_account",
    "registry_url",
    "registry_username",
    "repositories",
    "images",
    "command_profiles",
    "resource_profiles",
    "min_ttl_seconds",
    "max_ttl_seconds",
    "export_bucket",
    "export_prefix",
    "export_max_files",
    "export_max_bytes",
}


def _bounded_match(pattern: re.Pattern[str], value: Any, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= maximum
        and pattern.fullmatch(value) is not None
    )


def _dns_name(value: str) -> bool:
    if len(value) > 253:
        return False
    labels = value.split(".")
    return len(labels) >= 2 and all(
        0 < len(label) <= 63
        and label[0] != "-"
        and label[-1] != "-"
        and all(
            character in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in label
        )
        for label in labels
    )


def _require_registry_host(value: str) -> None:
    if not value or len(value) > 320 or value.count(":") > 1:
        raise ValueError("workspace image registry is invalid")
    host, separator, port = value.rpartition(":")
    if not separator:
        host = value
    elif (
        not port
        or len(port) > 5
        or not port.isascii()
        or not port.isdecimal()
        or not 1 <= int(port) <= 65535
    ):
        raise ValueError("workspace image registry port is invalid")
    if not _dns_name(host):
        raise ValueError("workspace image registry must be a normalized DNS name")


def _require_service_account(value: Any, project: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 320
        or value.count("@") != 1
    ):
        raise ValueError("service_account must name an existing Google service account")
    local_name, domain = value.split("@", 1)
    if not _bounded_match(SERVICE_ACCOUNT_NAME, local_name, 30):
        raise ValueError("service_account local name is invalid")
    if domain != f"{project}.iam.gserviceaccount.com":
        raise ValueError("service_account must belong to the configured project")
    return value


def _require_registry_url(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError("registry_url is invalid")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError("registry_url is invalid") from error
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path.endswith("/")
        or "v2" in parsed.path.split("/")
        or not _dns_name(parsed.hostname)
        or port is not None
        and not 1 <= port <= 65535
    ):
        raise ValueError("registry_url must be an HTTPS registry root without /v2")
    return value


def _parse_image_reference(image: Any) -> tuple[str, str]:
    if (
        not isinstance(image, str)
        or not image
        or len(image) > 2048
        or image.count("@") != 1
    ):
        raise ValueError("workspace image reference must be a bounded string")
    named_reference, digest = image.rsplit("@", 1)
    require_digest(digest)
    registry, separator, image_path = named_reference.partition("/")
    if not separator or not image_path:
        raise ValueError("workspace image must include a registry and repository")
    _require_registry_host(registry)

    last_component = image_path.rsplit("/", 1)[-1]
    if ":" in last_component:
        repository, tag = image_path.rsplit(":", 1)
        if not _bounded_match(IMAGE_TAG, tag, 128):
            raise ValueError("workspace image tag is invalid")
    else:
        repository = image_path
    if len(repository) > 255:
        raise ValueError("workspace image repository is too long")
    require_repository(repository)
    return repository, digest


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not low <= value <= high
    ):
        raise ValueError(f"{name} must be an integer from {low} through {high}")
    return value


def _plain_strings(value: Any, name: str, maximum: int) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{name} must be a bounded list")
    result = tuple(value)
    if any(
        not isinstance(item, str) or not item or len(item) > 1024 for item in result
    ):
        raise ValueError(f"{name} contains an invalid string")
    return result


@dataclass(frozen=True)
class CommandProfile:
    command: tuple[str, ...]
    args: tuple[str, ...]


@dataclass(frozen=True)
class ResourceProfile:
    cpu: str
    memory: str
    timeout_seconds: int
    max_retries: int


@dataclass(frozen=True)
class DeploymentPolicy:
    range_instance: str
    participant: str
    project_id: str
    region: str
    service_account: str
    registry_url: str
    registry_username: str
    repositories: frozenset[str]
    images: frozenset[str]
    commands: dict[str, CommandProfile]
    resources: dict[str, ResourceProfile]
    min_ttl_seconds: int
    max_ttl_seconds: int
    export_bucket: str
    export_prefix: str
    export_max_files: int
    export_max_bytes: int

    @property
    def location_name(self) -> str:
        return f"projects/{self.project_id}/locations/{self.region}"

    @property
    def tenant_id(self) -> str:
        import hashlib

        identity = f"{self.range_instance}\0{self.participant}".encode()
        return hashlib.sha256(identity).hexdigest()[:12]


def _parse_tenant(raw: dict[str, Any]) -> tuple[str, str]:
    range_instance = raw.get("range_instance", "")
    participant = raw.get("participant", "")
    if not _bounded_match(TENANT, range_instance, 32) or not _bounded_match(
        TENANT, participant, 32
    ):
        raise ValueError(
            "range_instance and participant must be bounded lowercase tenant identifiers"
        )
    return range_instance, participant


def _parse_cloud_identity(raw: dict[str, Any]) -> tuple[str, str, str, str]:
    project = raw.get("project_id", "")
    region = raw.get("region", "")
    bucket = raw.get("export_bucket", "")
    if not _bounded_match(PROJECT, project, 30):
        raise ValueError("project_id is invalid")
    if not _bounded_match(REGION, region, 64):
        raise ValueError("region is invalid")
    identity = _require_service_account(raw.get("service_account"), project)
    if not _bounded_match(BUCKET, bucket, 63):
        raise ValueError("export_bucket must name an existing bucket")
    return project, region, bucket, identity


def _parse_registry_identity(raw: dict[str, Any]) -> tuple[str, str]:
    registry_url = _require_registry_url(raw.get("registry_url"))
    username = raw.get("registry_username", "")
    if not isinstance(username, str) or not username or len(username) > 128:
        raise ValueError("registry_username is invalid")
    return registry_url, username


def _parse_repositories(value: Any) -> frozenset[str]:
    repository_items = value
    if not isinstance(repository_items, list) or len(repository_items) > 128:
        raise ValueError("repositories must be a bounded list")
    repositories: set[str] = set()
    for repository in repository_items:
        if not isinstance(repository, str) or not repository or len(repository) > 255:
            raise ValueError("repository is not a bounded OCI repository name")
        repositories.add(require_repository(repository))
    if not repositories:
        raise ValueError("at least one OCI repository must be allowlisted")
    return frozenset(repositories)


def _parse_images(value: Any) -> frozenset[str]:
    images: set[str] = set()
    image_items = value
    if not isinstance(image_items, list) or len(image_items) > 128:
        raise ValueError("images must be a bounded list")
    for image in image_items:
        _parse_image_reference(image)
        images.add(image)
    if not images:
        raise ValueError(
            "at least one digest-pinned workspace image must be allowlisted"
        )
    return frozenset(images)


def _parse_commands(value: Any) -> dict[str, CommandProfile]:
    commands: dict[str, CommandProfile] = {}
    command_items = value
    if not isinstance(command_items, dict) or len(command_items) > 64:
        raise ValueError("command_profiles must be a bounded object")
    for name, item in command_items.items():
        if (
            not _bounded_match(PROFILE, name, 63)
            or not isinstance(item, dict)
            or set(item) != {"command", "args"}
        ):
            raise ValueError("command profile is invalid")
        commands[name] = CommandProfile(
            command=_plain_strings(item.get("command"), "command", 16),
            args=_plain_strings(item.get("args"), "args", 64),
        )
    return commands


def _parse_resource(name: Any, item: Any) -> ResourceProfile:
    if (
        not _bounded_match(PROFILE, name, 63)
        or not isinstance(item, dict)
        or set(item) != {"cpu", "memory", "timeout_seconds", "max_retries"}
    ):
        raise ValueError("resource profile is invalid")
    cpu, memory = item.get("cpu"), item.get("memory")
    memory_bounds = {
        "1": (128, 4096),
        "2": (512, 8192),
        "4": (2048, 16384),
        "8": (4096, 32768),
    }
    if not isinstance(cpu, str) or cpu not in memory_bounds:
        raise ValueError("resource CPU must be an allowlisted Cloud Run CPU value")
    if (
        not isinstance(memory, str)
        or len(memory) < 5
        or len(memory) > 7
        or not memory.endswith("Mi")
        or not memory[:-2].isascii()
        or not memory[:-2].isdecimal()
        or memory[0] == "0"
    ):
        raise ValueError("resource memory must be a bounded Mi value")
    memory_mi = int(memory.removesuffix("Mi"))
    minimum, maximum = memory_bounds[cpu]
    if not minimum <= memory_mi <= maximum:
        raise ValueError(
            "resource memory is incompatible with the selected Cloud Run CPU"
        )
    return ResourceProfile(
        cpu=cpu,
        memory=memory,
        timeout_seconds=_integer(
            item.get("timeout_seconds"), "timeout_seconds", 1, 3600
        ),
        max_retries=_integer(item.get("max_retries"), "max_retries", 0, 3),
    )


def _parse_resources(value: Any) -> dict[str, ResourceProfile]:
    resources: dict[str, ResourceProfile] = {}
    resource_items = value
    if not isinstance(resource_items, dict) or len(resource_items) > 64:
        raise ValueError("resource_profiles must be a bounded object")
    for name, item in resource_items.items():
        resources[name] = _parse_resource(name, item)
    return resources


def _parse_export_prefix(
    raw: dict[str, Any], range_instance: str, participant: str
) -> str:
    prefix = raw.get("export_prefix", "")
    if (
        not isinstance(prefix, str)
        or not prefix
        or len(prefix) > 1024
        or prefix.strip("/") != prefix
        or any(part in {"", ".", ".."} for part in prefix.split("/"))
    ):
        raise ValueError("export_prefix must be a normalized bucket prefix")
    if prefix.split("/")[-3:] != [range_instance, participant, "workspaces"]:
        raise ValueError(
            "export_prefix must terminate in the active range/participant workspace namespace"
        )
    return prefix + "/"


def parse_policy(raw: Any) -> DeploymentPolicy:
    if not isinstance(raw, dict) or set(raw) != POLICY_FIELDS:
        raise ValueError("deployment policy has missing or unsupported fields")
    if raw.get("schema_version") != 1:
        raise ValueError("deployment policy schema_version must be 1")
    range_instance, participant = _parse_tenant(raw)
    project, region, bucket, identity = _parse_cloud_identity(raw)
    registry_url, username = _parse_registry_identity(raw)
    repositories = _parse_repositories(raw.get("repositories"))
    images = _parse_images(raw.get("images"))
    commands = _parse_commands(raw.get("command_profiles"))
    resources = _parse_resources(raw.get("resource_profiles"))
    if not commands or not resources:
        raise ValueError("command and resource profiles are required")
    prefix = _parse_export_prefix(raw, range_instance, participant)
    min_ttl = _integer(raw.get("min_ttl_seconds"), "min_ttl_seconds", 60, 86400)
    max_ttl = _integer(raw.get("max_ttl_seconds"), "max_ttl_seconds", 60, 86400)
    if min_ttl > max_ttl:
        raise ValueError("minimum workspace TTL cannot exceed maximum TTL")
    return DeploymentPolicy(
        range_instance=range_instance,
        participant=participant,
        project_id=project,
        region=region,
        service_account=identity,
        registry_url=registry_url,
        registry_username=username,
        repositories=repositories,
        images=images,
        commands=commands,
        resources=resources,
        min_ttl_seconds=min_ttl,
        max_ttl_seconds=max_ttl,
        export_bucket=bucket,
        export_prefix=prefix,
        export_max_files=_integer(
            raw.get("export_max_files"), "export_max_files", 1, 1000
        ),
        export_max_bytes=_integer(
            raw.get("export_max_bytes"), "export_max_bytes", 1, 100_000_000
        ),
    )


def load_policy(path: Path) -> DeploymentPolicy:
    return parse_policy(json.loads(path.read_text(encoding="utf-8")))
