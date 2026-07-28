#!/usr/bin/env python3
"""Reference CTFd loader for KeplerOps AI."""

from __future__ import annotations

import argparse
import os
import stat

import keplerops_flag_manifest as manifest
from ctfd_reconcile import (
    CtfdClient,
    SyncError,
    challenge_payload,
    ensure_children,
    get_all_items,
    live_prerequisite_ids,
    managed_challenges,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Sync KeplerOps challenges to CTFd", allow_abbrev=False)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--profile", choices=manifest.PROFILES, default=manifest.DEFAULT_PROFILE)
    parser.add_argument(
        "--challenge-id",
        action="append",
        default=[],
        help="custom challenge id to project; may be repeated; dependencies are included",
    )
    parser.add_argument("--token-file")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def resolve_token(token_file: str | None) -> str | None:
    if token_file is None:
        return os.environ.get("CTFD_TOKEN")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(token_file, flags)
    except OSError as exc:
        raise SyncError("token file could not be opened securely") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
            raise SyncError("token file must be regular and owner-only")
        with os.fdopen(descriptor, encoding="utf-8") as handle:
            descriptor = -1
            token = handle.read(8193).strip()
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if not token or len(token) > 8192:
        raise SyncError("token file did not contain a bounded token")
    return token


def sync_flag_layer(client, *, challenges, dry_run: bool):
    if dry_run:
        for row in challenges:
            print(f"ensure managed challenge {row['flag_id']}")
        return {row["flag_id"]: None for row in challenges}
    live = get_all_items(client, "/challenges", {"view": "admin"})
    managed = managed_challenges(client, live)
    expected_ids = {row["flag_id"] for row in challenges}
    result = {}
    current_by_flag = {}
    for position, row in enumerate(challenges, 1):
        payload = challenge_payload(row, position)
        current = managed.get(row["flag_id"])
        if current is None:
            current = client.post("/challenges", payload)["data"]
        else:
            patch = {key: value for key, value in payload.items() if current.get(key) != value}
            if patch:
                current = client.patch(f"/challenges/{current['id']}", patch)["data"]
        ensure_children(client, current["id"], row)
        result[row["flag_id"]] = current["id"]
        current_by_flag[row["flag_id"]] = current
    ids_by_challenge_id = {row["challenge_id"]: result[row["flag_id"]] for row in challenges}
    for position, row in enumerate(challenges, 1):
        payload = challenge_payload(
            row,
            position,
            live_prerequisite_ids(row, ids_by_challenge_id),
        )
        current = current_by_flag[row["flag_id"]]
        patch = {key: value for key, value in payload.items() if current.get(key) != value}
        if patch:
            client.patch(f"/challenges/{current['id']}", patch)
    for flag_id, current in managed.items():
        if flag_id not in expected_ids:
            client.delete(f"/challenges/{current['id']}")
    return result


def main(argv=None):
    args = parse_args(argv)
    rows = (
        manifest.load_custom_manifest(challenge_ids=args.challenge_id)
        if args.challenge_id else manifest.load_manifest(profile=args.profile)
    )
    if args.dry_run:
        sync_flag_layer(None, challenges=rows, dry_run=True)
        print(f"dry-run complete: {len(rows)} managed challenge(s)")
        return 0
    token = resolve_token(args.token_file)
    if not token:
        raise SyncError("missing CTFd admin token")
    client = CtfdClient(args.base_url, token)
    ids = sync_flag_layer(client, challenges=rows, dry_run=False)
    manifest.verify_challenge_rows(client, challenges=rows, flag_to_live_id=ids)
    print(f"sync complete: {len(rows)} managed challenge(s)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SyncError as error:
        raise SystemExit(f"error: {error}") from error
