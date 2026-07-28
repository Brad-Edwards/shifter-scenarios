#!/usr/bin/env python3
"""Build the CTFd projection from validated KeplerOps pack contracts."""

from __future__ import annotations

import importlib.util
import os

from ctfd_reconcile import MANAGED_PREFIX, SyncError, verify_rows

CTFD_DIR = os.path.dirname(os.path.abspath(__file__))
PACK_DIR = os.path.dirname(CTFD_DIR)
BUNDLE_PROFILES = [
    "novice-manual", "intermediate-manual", "advanced-manual",
    "mixed-cohort", "agent-heavy",
]
PROFILES = ["gcp_full", "local_reduced", *BUNDLE_PROFILES]
DEFAULT_PROFILE = "gcp_full"


def _validator(pack_dir: str):
    path = os.path.join(pack_dir, "validation", "validate_oracle.py")
    spec = importlib.util.spec_from_file_location("keplerops_ctfd_validator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _aces_contract(pack_dir: str):
    path = os.path.join(pack_dir, "aces_contract.py")
    spec = importlib.util.spec_from_file_location("keplerops_ctfd_aces_contract", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_rows(pack_dir: str, *, selected_ids: set[str] | None):
    contract = _aces_contract(pack_dir)
    placement = contract.flag_rows(pack_dir)
    challenges = contract.challenge_content_rows(pack_dir)
    challenge_by_id = {row["flag_id"]: row for row in challenges}
    rows = []
    for flag in sorted(placement, key=lambda row: row["flag_id"]):
        if selected_ids is not None and flag["challenge_id"] not in selected_ids:
            continue
        position = len(rows) + 1
        challenge = challenge_by_id[flag["flag_id"]]
        rows.append({
            "flag_id": flag["flag_id"],
            "challenge_id": flag["challenge_id"],
            "managed_tag": MANAGED_PREFIX + flag["flag_id"],
            "name": challenge["title"],
            "category": challenge["category"],
            "description": challenge["question"],
            "value": challenge["points"],
            "difficulty": challenge["difficulty"],
            "prerequisites": list(challenge["prerequisites"]),
            "hints": list(challenge["hints"]),
            "acceptance": {
                "type": "keplerops_oracle",
                "challenge_id": flag["challenge_id"],
                "flag_id": flag["flag_id"],
                "outcome": flag["outcome"],
                "evidence": flag["evidence"],
                "prerequisites": list(challenge["prerequisites"]),
            },
            "position": position,
        })
    if selected_ids is not None:
        projected = {row["challenge_id"] for row in rows}
        missing = sorted(selected_ids - projected)
        if missing:
            raise SyncError(f"selection contains unprojectable challenge(s): {', '.join(missing)}")
    return rows


def load_manifest(pack_dir: str = PACK_DIR, *, profile: str = DEFAULT_PROFILE):
    if profile not in PROFILES:
        raise SyncError(f"unsupported profile {profile}")
    failures = _validator(pack_dir).validate_pack(pack_dir)
    if failures:
        raise SyncError(f"flag layer validation failed with {len(failures)} issue(s)")
    contract = _aces_contract(pack_dir)
    if profile == "local_reduced":
        return []
    if profile == "gcp_full":
        return _load_rows(pack_dir, selected_ids=None)
    try:
        selected = contract.event_bundle_selection(profile, pack_dir)
    except contract.AcesContractError as exc:
        raise SyncError(str(exc)) from exc
    return _load_rows(pack_dir, selected_ids=selected)


def load_custom_manifest(
    pack_dir: str = PACK_DIR,
    *,
    challenge_ids: list[str],
    include_dependencies: bool = True,
):
    failures = _validator(pack_dir).validate_pack(pack_dir)
    if failures:
        raise SyncError(f"flag layer validation failed with {len(failures)} issue(s)")
    contract = _aces_contract(pack_dir)
    try:
        selected = contract.custom_challenge_selection(
            challenge_ids,
            pack_dir,
            include_dependencies=include_dependencies,
        )
    except contract.AcesContractError as exc:
        raise SyncError(str(exc)) from exc
    return _load_rows(pack_dir, selected_ids=selected)


def verify_challenge_rows(client, *, challenges, flag_to_live_id):
    verify_rows(client, challenges, flag_to_live_id)


__all__ = [
    "BUNDLE_PROFILES", "DEFAULT_PROFILE", "PROFILES", "SyncError",
    "load_custom_manifest", "load_manifest", "verify_challenge_rows",
]
