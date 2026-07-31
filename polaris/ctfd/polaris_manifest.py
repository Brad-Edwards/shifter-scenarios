"""Canonical Polaris flag/challenge projection for the reference CTFd loader."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any


PACK_ROOT = Path(__file__).resolve().parents[1]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

from contract_source import load_yaml  # noqa: E402
from ctfd_reconcile import get_all_items  # noqa: E402


SUPPORTED_FLAG_TYPES = {"static", "regex"}
_CANONICAL_FLAG_WRAPPER_RE = re.compile(r"^FLAG\{([0-9a-fA-F]{16})\}$")
_FLAG_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NAMESPACE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

ORDERED_FLAG_IDS = [
    "company-registration",
    "employee-directory",
    "careers-tech-stack",
    "client-contracts",
    "dns-zone-transfer",
    "annual-report-supplier",
    "intranet-config-leak",
    "project-status-mail",
    "terminated-engineer",
    "default-password-mail",
    "cafeteria-metadata",
    "project-wiki-comment",
    "procurement-actuator",
    "nested-project-group",
    "fileshare-service-creds",
    "guard-badge-anomaly",
    "domain-admin-secrets",
    "analyst-lab-pivot",
    "jenkins-default-creds",
    "research-compartment-a",
    "reactor-interface-spec",
    "midnight-standard-run",
    "navigation-git-history",
    "midnight-after-hours",
    "center-of-gravity",
    "research-compartment-b",
    "final-assembly-metadata",
    "deleted-schematic",
    "full-integration-video",
    "ops-scada-credentials",
    "scada-control-room",
    "scada-blackout",
    "bunker-controller-map",
    "tail-controller-unlock",
    "leg-controller-gait",
    "arms-response-window",
    "brain-control-channel",
    "brain-full-override",
]

_CATEGORY_BY_FLAG_ID = {
    **{flag_id: "Mission 1 — Boreas" for flag_id in ORDERED_FLAG_IDS[:6]},
    **{flag_id: "Mission 2 — Inside Boreas" for flag_id in ORDERED_FLAG_IDS[6:17]},
    **{flag_id: "Mission 3 — The Lab" for flag_id in ORDERED_FLAG_IDS[17:29]},
    **{flag_id: "Mission 4 — Lights Out" for flag_id in ORDERED_FLAG_IDS[29:32]},
    **{flag_id: "Mission 5 — Bunker" for flag_id in ORDERED_FLAG_IDS[32:]},
}


class SyncError(RuntimeError):
    """Raised when canonical source or live CTFd state is unsafe to mutate."""


def _ownership_namespace(event_namespace: str | None) -> str:
    namespace = event_namespace or "default"
    if not _NAMESPACE_RE.fullmatch(namespace):
        raise SyncError("event namespace must be a lowercase slug")
    return namespace


def _index_source_rows(
    rows: Any,
    *,
    source_name: str,
) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise SyncError(f"{source_name} source must contain a non-empty list")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise SyncError(f"{source_name} source rows must be mappings")
        flag_id = row.get("flag_id")
        if not isinstance(flag_id, str) or not _FLAG_ID_RE.fullmatch(flag_id):
            raise SyncError(f"{source_name} source has a malformed stable flag id")
        if flag_id in indexed:
            raise SyncError(f"{source_name} source has a duplicate stable flag id")
        indexed[flag_id] = row
    return indexed


def load_manifest(
    pack_root: str | Path = PACK_ROOT,
    *,
    runtime_profile_id: str = "aws_event",
    event_namespace: str | None = None,
) -> list[dict[str, Any]]:
    """Join canonical placement and participant copy into CTFd rows."""

    if runtime_profile_id != "aws_event":
        raise SyncError(
            "only aws_event may project the live Polaris event flag set"
        )
    root = Path(pack_root)
    placements = load_yaml(root / "flags" / "placement.yaml").get("flags")
    challenges = load_yaml(
        root / "challenges" / "challenges.yaml"
    ).get("challenges")
    placement_by_id = _index_source_rows(
        placements,
        source_name="placement",
    )
    challenge_by_id = _index_source_rows(
        challenges,
        source_name="challenge",
    )
    if set(placement_by_id) != set(challenge_by_id):
        raise SyncError("placement and challenge flag ids do not match")
    if set(placement_by_id) != set(ORDERED_FLAG_IDS):
        raise SyncError("canonical Polaris flag inventory is incomplete or unexpected")

    namespace = _ownership_namespace(event_namespace)
    ownership_prefix = f"panw:polaris:{namespace}:"
    rows: list[dict[str, Any]] = []
    for flag_id in ORDERED_FLAG_IDS:
        placement = placement_by_id[flag_id]
        challenge = challenge_by_id[flag_id]
        value = placement.get("value")
        source = placement.get("source")
        if source != "value" or not isinstance(value, str) or not value:
            raise SyncError(
                f"{flag_id}: the reference CTFd adapter currently requires a static value"
            )
        hints = [
            {"title": f"Hint {index}", "content": hint, "cost": 0}
            for index, hint in enumerate(challenge.get("hints", []), start=1)
        ]
        row = {
            "flag_id": flag_id,
            "name": challenge.get("title"),
            "description": challenge.get("question"),
            "category": _CATEGORY_BY_FLAG_ID[flag_id],
            "value": challenge.get("points"),
            "type": "standard",
            "state": "visible",
            "flags": [{"type": "static", "content": value}],
            "hints": hints,
            "tags": [
                f"{ownership_prefix}{flag_id}",
                f"difficulty:{challenge.get('difficulty')}",
            ],
            "ownership_tag": f"{ownership_prefix}{flag_id}",
            "ownership_prefix": ownership_prefix,
            "source_challenge": challenge,
        }
        rows.append(row)
    validate_manifest(rows)
    return rows


def validate_manifest(challenges: list[dict[str, Any]]) -> None:
    """Validate the complete projection before any remote write."""

    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_ownership: set[str] = set()
    for challenge in challenges:
        flag_id = challenge.get("flag_id")
        if (
            not isinstance(flag_id, str)
            or not _FLAG_ID_RE.fullmatch(flag_id)
            or flag_id in seen_ids
        ):
            errors.append("duplicate or malformed stable flag id")
            continue
        seen_ids.add(flag_id)
        for field in ("name", "description", "category", "ownership_tag"):
            if not isinstance(challenge.get(field), str) or not challenge[field]:
                errors.append(f"{flag_id}: missing {field}")
        ownership = challenge.get("ownership_tag")
        if ownership in seen_ownership:
            errors.append(f"{flag_id}: duplicate ownership tag")
        seen_ownership.add(ownership)
        if ownership not in challenge.get("tags", []):
            errors.append(f"{flag_id}: ownership tag is not projected")
        if "category" in challenge.get("source_challenge", {}):
            errors.append(f"{flag_id}: category must remain adapter-local")
        if not isinstance(challenge.get("value"), int) or challenge["value"] <= 0:
            errors.append(f"{flag_id}: points must be a positive integer")
        flags = challenge.get("flags", [])
        if len(flags) != 1:
            errors.append(f"{flag_id}: exactly one answer is required")
        else:
            flag = flags[0]
            content = flag.get("content")
            if flag.get("type", "static") not in SUPPORTED_FLAG_TYPES:
                errors.append(f"{flag_id}: unsupported answer type")
            if (
                not isinstance(content, str)
                or not _CANONICAL_FLAG_WRAPPER_RE.fullmatch(content)
            ):
                errors.append(f"{flag_id}: malformed canonical answer")
        if not challenge.get("hints"):
            errors.append(f"{flag_id}: at least one hint is required")
    if errors:
        raise SyncError(
            "manifest validation failed: " + "; ".join(sorted(set(errors)))
        )


def sort_challenges(challenges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {flag_id: index for index, flag_id in enumerate(ORDERED_FLAG_IDS)}
    return sorted(
        challenges,
        key=lambda row: order.get(row.get("flag_id"), len(order)),
    )


def _expected_live_flag(flag: dict[str, Any]) -> tuple[str, str, str]:
    """Independently derive the documented CTFd answer-row contract."""

    source_type = flag.get("type", "static")
    content = flag["content"]
    if source_type == "static":
        match = _CANONICAL_FLAG_WRAPPER_RE.fullmatch(content)
        if match:
            body = match.group(1)
            return (
                "regex",
                rf"^(?:FLAG\{{{body}\}}|{body})$",
                "case_insensitive",
            )
    return source_type, content, flag.get("data", "")


def verify_challenge_rows(
    client,
    *,
    challenges: list[dict[str, Any]],
    flag_id_to_live_id: dict[str, int | None],
) -> None:
    """Read managed challenge, answer, hint, point, state, and tag rows back."""

    live = {
        row.get("id"): row
        for row in get_all_items(client, "/challenges", {"view": "admin"})
    }
    failures: list[str] = []
    for challenge in challenges:
        flag_id = challenge["flag_id"]
        live_id = flag_id_to_live_id.get(flag_id)
        row = live.get(live_id)
        if row is None:
            failures.append(f"{flag_id}: missing live challenge")
            continue
        if (
            row.get("name") != challenge["name"]
            or row.get("value") != challenge["value"]
            or row.get("state") != challenge["state"]
        ):
            failures.append(f"{flag_id}: challenge readback drift")
        expected_flags = {
            _expected_live_flag(flag)
            for flag in challenge["flags"]
        }
        live_flags = client.get(
            f"/challenges/{live_id}/flags"
        ).get("data", [])
        actual_flags = {
            (row.get("type"), row.get("content"), row.get("data", ""))
            for row in live_flags
        }
        if actual_flags != expected_flags:
            failures.append(f"{flag_id}: answer readback drift")

        expected_hints = {
            (
                row.get("title", f"Hint {index}"),
                row["content"],
                row.get("cost", 0),
                tuple(row.get("requirements", [])),
            )
            for index, row in enumerate(challenge["hints"], start=1)
        }
        live_hints = client.get(
            f"/challenges/{live_id}/hints"
        ).get("data", [])
        actual_hints = {
            (
                row.get("title"),
                row.get("content"),
                row.get("cost"),
                tuple(row.get("requirements", [])),
            )
            for row in live_hints
        }
        if actual_hints != expected_hints:
            failures.append(f"{flag_id}: hint readback drift")

        live_tags = client.get(
            f"/challenges/{live_id}/tags"
        ).get("data", [])
        actual_managed_tags = {
            row.get("value")
            for row in live_tags
            if isinstance(row.get("value"), str)
            and row["value"].startswith(("panw:polaris:", "difficulty:"))
        }
        if actual_managed_tags != set(challenge["tags"]):
            failures.append(f"{flag_id}: ownership readback drift")
    if failures:
        raise SyncError(
            "post-sync verification failed: " + "; ".join(failures)
        )


__all__ = [
    "ORDERED_FLAG_IDS",
    "SUPPORTED_FLAG_TYPES",
    "SyncError",
    "load_manifest",
    "sort_challenges",
    "validate_manifest",
    "verify_challenge_rows",
]
