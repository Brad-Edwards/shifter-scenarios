#!/usr/bin/env python3
"""Build the operator-only fourth-wall detection policy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CARD_REGISTRY = ROOT / "build" / "card-coverage" / "registry.json"

META_RULES = [
    {"id": "meta-ctf", "pattern": r"(?<![a-z0-9])ctf(?![a-z0-9])", "label": "CTF"},
    {"id": "meta-flag", "pattern": r"(?<![a-z0-9])flags?(?![a-z0-9])", "label": "flag"},
    {
        "id": "meta-score",
        "pattern": r"(?<![a-z0-9])(?:scores?|scoring)(?![a-z0-9])",
        "label": "score",
    },
    {
        "id": "meta-challenge",
        "pattern": r"(?<![a-z0-9])challenges?(?:[ _-]handler)?(?![a-z0-9])",
        "label": "challenge",
    },
    {
        "id": "meta-integration-test",
        "pattern": r"(?<![a-z0-9])integration[ _-]tests?(?![a-z0-9])",
        "label": "integration test",
    },
    {
        "id": "meta-fixture-only",
        "pattern": r"(?<![a-z0-9])fixture[ _-]only(?![a-z0-9])",
        "label": "fixture-only",
    },
    {
        "id": "meta-expected-answer",
        "pattern": r"(?<![a-z0-9])expected[ _-]answers?(?![a-z0-9])",
        "label": "expected answer",
    },
    {
        "id": "meta-author-contract",
        "pattern": r"(?<![a-z0-9])author(?:ing)?[ _-]contracts?(?![a-z0-9])",
        "label": "author contract",
    },
    {
        "id": "meta-fourth-wall",
        "pattern": r"(?<![a-z0-9])fourth[ _-]wall(?![a-z0-9])",
        "label": "fourth wall",
    },
    {
        "id": "meta-walkthrough",
        "pattern": r"(?<![a-z0-9])walkthroughs?(?![a-z0-9])",
        "label": "walkthrough",
    },
    {
        "id": "dependency-oracle",
        "pattern": (
            r"(?:challenge|card|step|prerequisite).*(?:missing|required|first)"
            r"|(?:missing|required|complete).*(?:challenge|card|step|prerequisite)"
        ),
        "label": "challenge dependency oracle",
    },
]


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def build_policy() -> dict[str, Any]:
    registry = json.loads(CARD_REGISTRY.read_text(encoding="utf-8"))
    titles = []
    for card_id, entry in sorted(registry["cards"].items()):
        title = entry["title"].split(":", 1)[-1].strip()
        titles.append({"card_id": card_id, "title_slug": slug(title)})
    value = {
        "schema_version": 1,
        "card_aliases": titles,
        "meta_rules": META_RULES,
    }
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    value["policy_sha256"] = hashlib.sha256(canonical).hexdigest()
    return value


if __name__ == "__main__":
    print(json.dumps(build_policy(), indent=2, sort_keys=True))
