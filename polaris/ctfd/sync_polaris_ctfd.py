#!/usr/bin/env python3
"""Reference CTFd projection for the canonical Polaris flag layer."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import (
    CtfdClient,
    read_token_file as read_common_token_file,
    resolve_admin_token,
)
from ctfd_reconcile import (
    build_challenge_payload,
    ensure_flags,
    ensure_hints,
    get_all_items,
    upsert_challenge,
)
from polaris_manifest import SyncError, load_manifest, verify_challenge_rows


PACK_ROOT = Path(__file__).resolve().parents[1]
_MANAGED_TAG_PREFIXES = ("panw:polaris:", "difficulty:")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync the canonical Polaris flag layer to CTFd.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="CTFd origin, normally an HTTPS URL",
    )
    parser.add_argument(
        "--profile",
        default="aws_event",
        choices=("aws_event", "local_degraded"),
    )
    parser.add_argument(
        "--event-namespace",
        default=None,
        help="optional lowercase slug isolating one managed event",
    )
    parser.add_argument(
        "--token-file",
        default=None,
        help="permission-restricted file containing the CTFd admin token",
    )
    parser.add_argument(
        "--allow-loopback-http",
        action="store_true",
        help="allow plain HTTP only for an explicit loopback development URL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and show managed operations without contacting CTFd",
    )
    return parser.parse_args(argv)


def read_token_file(path: str | Path) -> str:
    try:
        return read_common_token_file(path)
    except ValueError as error:
        raise SyncError(str(error)) from error


def resolve_token(token_file: str | None) -> str | None:
    try:
        return resolve_admin_token(token_file)
    except ValueError as error:
        raise SyncError(str(error)) from error


def ensure_tags(
    client,
    *,
    challenge_id: int | None,
    challenge_name: str,
    tags: list[str],
    dry_run: bool,
) -> None:
    """Reconcile loader-owned tags while preserving unrelated live tags."""

    if dry_run or challenge_id is None:
        for tag in tags:
            print(f"sync tag: {challenge_name} :: {tag}")
        return
    live = client.get(f"/challenges/{challenge_id}/tags").get("data", [])
    live_by_value = {row.get("value"): row for row in live}
    expected = set(tags)
    for tag in tags:
        if tag not in live_by_value:
            print(f"create tag: {challenge_name} :: {tag}")
            client.post(
                "/tags",
                {"challenge_id": challenge_id, "value": tag},
            )
    for value, row in live_by_value.items():
        loader_owned = isinstance(value, str) and value.startswith(
            _MANAGED_TAG_PREFIXES
        )
        if loader_owned and value not in expected:
            print(f"delete stale managed tag: {challenge_name}")
            client.delete(f"/tags/{row['id']}")


def _owned_challenges(
    client,
    existing: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    by_tag: dict[str, dict[str, Any]] = {}
    for challenge in existing:
        challenge_id = challenge.get("id")
        if not isinstance(challenge_id, int):
            continue
        tags = client.get(f"/challenges/{challenge_id}/tags").get("data", [])
        for tag in tags:
            value = tag.get("value")
            if not isinstance(value, str) or not value.startswith(
                "panw:polaris:"
            ):
                continue
            if value in by_tag:
                raise SyncError("duplicate managed ownership tag on live board")
            by_tag[value] = challenge
    return by_tag


def sync_flag_layer(
    client,
    *,
    challenges: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, int | None]:
    """Reconcile by stable ownership tag and leave partial rows hidden."""

    existing: list[dict[str, Any]] = []
    owned: dict[str, dict[str, Any]] = {}
    if not dry_run:
        existing = get_all_items(client, "/challenges", {"view": "admin"})
        owned = _owned_challenges(client, existing)

    expected_tags = {row["ownership_tag"] for row in challenges}
    expected_prefixes = {row["ownership_prefix"] for row in challenges}
    for tag, challenge in list(owned.items()):
        if any(tag.startswith(prefix) for prefix in expected_prefixes) and (
            tag not in expected_tags
        ):
            print("delete stale managed challenge")
            if not dry_run:
                client.delete(f"/challenges/{challenge['id']}")
                existing.remove(challenge)
            owned.pop(tag, None)

    synced: dict[str, dict[str, Any]] = {}
    for position, challenge in enumerate(challenges, start=1):
        hidden_source = {**challenge, "state": "hidden"}
        payload = build_challenge_payload(
            challenge=hidden_source,
            position=position,
            requirements={"prerequisites": []},
        )
        row = upsert_challenge(
            client,
            existing_challenges=existing,
            existing_challenge=owned.get(challenge["ownership_tag"]),
            payload=payload,
            dry_run=dry_run,
            match_by_name=False,
        )
        synced[challenge["flag_id"]] = row

    for challenge in challenges:
        row = synced[challenge["flag_id"]]
        challenge_id = row.get("id")
        ensure_flags(
            client,
            challenge_id=challenge_id,
            challenge_name=challenge["name"],
            flags=challenge["flags"],
            dry_run=dry_run,
        )
        ensure_hints(
            client,
            challenge_id=challenge_id,
            challenge_name=challenge["name"],
            hints=challenge["hints"],
            dry_run=dry_run,
        )
        ensure_tags(
            client,
            challenge_id=challenge_id,
            challenge_name=challenge["name"],
            tags=challenge["tags"],
            dry_run=dry_run,
        )
        if not dry_run and challenge_id is not None:
            client.patch(
                f"/challenges/{challenge_id}",
                {"state": challenge["state"]},
            )
            row["state"] = challenge["state"]

    return {
        flag_id: row.get("id")
        for flag_id, row in synced.items()
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    challenges = load_manifest(
        PACK_ROOT,
        runtime_profile_id=args.profile,
        event_namespace=args.event_namespace,
    )
    token = resolve_token(args.token_file)
    if not args.dry_run and not token:
        raise SyncError(
            "missing CTFd admin token: set CTFD_TOKEN or use --token-file"
        )
    client = None
    if not args.dry_run:
        client = CtfdClient(
            args.base_url,
            token,
            allow_loopback_http=args.allow_loopback_http,
        )
    ids = sync_flag_layer(
        client,
        challenges=challenges,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        verify_challenge_rows(
            client,
            challenges=challenges,
            flag_id_to_live_id=ids,
        )
        print("Polaris CTFd flag-layer sync complete")
    else:
        print("dry-run complete (no CTFd writes)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SyncError as error:
        raise SystemExit(f"error: {error}") from error
