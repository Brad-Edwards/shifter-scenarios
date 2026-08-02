#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DESIGN_ROOT = ROOT.parent.parent
OPERATION_ID = re.compile(r"`(kep-m\d{2}-[a-z])`")


def campaign_order() -> tuple[dict[str, int], dict[str, str]]:
    """Return the authored act order and participant-facing act names."""
    text = (DESIGN_ROOT / "operation-allocation.md").read_text(encoding="utf-8")
    order: dict[str, int] = {}
    categories: dict[str, str] = {}
    category = "Campaign"
    for line in text.splitlines():
        if line.startswith("## Act "):
            category = line.removeprefix("## ").strip()
        for source_id in OPERATION_ID.findall(line):
            if source_id not in order:
                order[source_id] = len(order) + 1
                categories[source_id] = category
    return order, categories


def records() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for path in sorted((ROOT / "modules").glob("m??/operations.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{path} must contain an array")
        result.extend(payload)
    return sorted(result, key=lambda item: str(item["id"]))


def shifter_bundle(scenario_id: str) -> dict[str, object]:
    order, categories = campaign_order()
    challenges: list[dict[str, object]] = []
    difficulty = {
        "Accessible": "easy",
        "Intermediate": "medium",
        "Advanced": "hard",
        "Expert": "expert",
    }
    for record in records():
        source_id = str(record["id"])
        # Shifter's native graph is conjunctive. Alternative in-world ingress
        # paths remain discoverable and enforced by the enterprise itself, so
        # an OR-gated operation must not be incorrectly locked behind all paths.
        prerequisites = record.get("board_prerequisites")
        if prerequisites is None:
            prerequisites = (
                []
                if record.get("prerequisite_mode") == "any"
                else record["prerequisites"]
            )
        challenges.append(
            {
                "id": source_id,
                "name": record["title"],
                "description": record["description"],
                "category": categories[source_id],
                "points": record["points"],
                "difficulty": difficulty[str(record["difficulty"])],
                "order": order[source_id],
                "flags": [
                    {
                        "type": "static",
                        "value": record["flag"],
                        "case_sensitive": True,
                        "order": 0,
                    }
                ],
                "hints": [
                    {"text": text, "penalty": 0, "order": index}
                    for index, text in enumerate(record["hints"], start=1)
                ],
                "prerequisites": prerequisites,
                "flag_format": "FLAG{16 lowercase hexadecimal characters}",
                "visibility": "visible",
            }
        )
    challenges.sort(key=lambda challenge: int(challenge["order"]))
    return {
        "contract": "shifter-ctf-content/v1",
        "scenario_id": scenario_id,
        "challenges": challenges,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--scenario-id", default="keplerops-ai")
    args = parser.parse_args()
    payload = shifter_bundle(args.scenario_id)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
