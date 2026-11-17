#!/usr/bin/env python3
"""Build the Shifter CTF import document (shifter-challenges/v3) for Cinder Typhoon.

Joins the participant catalog (challenges/challenges.yaml) with the operator-only
fixed flag values (flags/placement.yaml). The output contains flag values and is
operator-only: import it through the CTF organizer import, never publish it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "challenges" / "challenges.yaml"
PLACEMENT = ROOT / "flags" / "placement.yaml"
FLAG = re.compile(r"^FLAG\{[0-9a-f]{16}\}$")


def build() -> tuple[dict, list[str]]:
    catalog = yaml.safe_load(CATALOG.read_text())
    flags = {f["flag_id"]: f for f in yaml.safe_load(PLACEMENT.read_text())["flags"]}
    penalties = catalog["scoring"]["hint_policy"]["penalty_percent"]
    challenges, unplaced, order = [], [], 0
    for phase in catalog["phases"].values():
        for operation in phase["operations"]:
            for card in operation["cards"]:
                completion = card["completion"]
                if completion != {"mode": "static_flag", "flag_id": card["id"]}:
                    raise SystemExit(f"{card['id']}: completion is not static_flag")
                flag = flags.get(card["id"])
                if flag is None or not FLAG.fullmatch(flag["value"]):
                    raise SystemExit(f"{card['id']}: missing or malformed flag value")
                if flag.get("path") in (None, "", "TBD"):
                    unplaced.append(card["id"])
                order += 1
                challenges.append({
                    "name": f"{card['id']}: {card['title']}",
                    "description": card["description"],
                    "category": phase["title"],
                    "points": card["points"],
                    "difficulty": card["difficulty"],
                    "flag_format": "FLAG{...}",
                    "order": order,
                    "flags": [{"flag_type": "static", "value": flag["value"], "case_sensitive": True, "order": 0}],
                    "hints": [{"text": text, "penalty": penalties[i], "order": i} for i, text in enumerate(card["hints"])],
                })
    if len({c["flags"][0]["value"] for c in challenges}) != len(challenges):
        raise SystemExit("duplicate flag values")
    return {"format": "shifter-challenges/v3", "challenges": challenges}, unplaced


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--release", action="store_true", help="fail if any flag has no placement path")
    args = parser.parse_args()
    document, unplaced = build()
    if args.release and unplaced:
        raise SystemExit(f"{len(unplaced)} flags have no placement path: {' '.join(unplaced)}")
    args.output.write_text(json.dumps(document, indent=2) + "\n")
    print(f"{len(document['challenges'])} challenges written to {args.output}; unplaced flags: {len(unplaced)}", file=sys.stderr)


if __name__ == "__main__":
    main()
