"""Canonical flag/challenge contract parsing for participant-path smoketests."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACK_ROOT))

from contract_source import load_yaml  # noqa: E402


@dataclass(frozen=True)
class Challenge:
    """One canonical challenge and its configured static value."""

    flag_id: str
    name: str
    static_flag: str | None


def load_board(
    placement_path: str | Path,
    challenges_path: str | Path,
) -> list[Challenge]:
    """Join canonical placement and participant-copy contracts by flag id."""

    placements = load_yaml(placement_path).get("flags")
    challenge_rows = load_yaml(challenges_path).get("challenges")
    if not isinstance(placements, list) or not isinstance(challenge_rows, list):
        raise ValueError("canonical flag contracts require list roots")
    placement_by_id = {
        row.get("flag_id"): row for row in placements if isinstance(row, dict)
    }
    challenge_by_id = {
        row.get("flag_id"): row for row in challenge_rows if isinstance(row, dict)
    }
    if (
        len(placement_by_id) != len(placements)
        or len(challenge_by_id) != len(challenge_rows)
        or set(placement_by_id) != set(challenge_by_id)
    ):
        raise ValueError(
            "placement and challenge contracts require a unique flag-id bijection"
        )
    result: list[Challenge] = []
    for row in challenge_rows:
        flag_id = row["flag_id"]
        placement = placement_by_id[flag_id]
        static_flag = (
            placement.get("value")
            if placement.get("source") == "value"
            else None
        )
        result.append(
            Challenge(
                flag_id=flag_id,
                name=str(row.get("title", "")),
                static_flag=static_flag,
            )
        )
    return result
