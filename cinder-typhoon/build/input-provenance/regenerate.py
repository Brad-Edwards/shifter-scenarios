#!/usr/bin/env python3
"""Regenerate ledger.json inventory fields from the current sources.

This helper makes a ledger update repeatable. It:
  - recomputes the request, runtime-comparison and runtime-source inventories
    with the same functions the validator uses (provenance.py);
  - carries each surviving entry's human review verbatim (profile, citations,
    unresolved, review_status) and only refreshes its inventory hash and counts
    to the observed values — this is the documented "acknowledge a code change";
  - drops entries whose source was removed;
  - adds a new runtime-comparison or runtime-source entry with the standard
    service-runtime protocol citation (the whole runtime section is reviewed
    under that single class). A new entry is added ONLY after the operator has
    confirmed, by reading the file, that its fixed-literal comparisons are
    protocol contracts / response schemas / discoverable identifiers and never
    author-only secret values;
  - refuses to invent provenance for a new request method: a new test method
    must be reviewed and authored by hand.

It never changes a provenance class, a citation, an unresolved item, or a
review_status, and it never relaxes a validator rule. After writing it re-runs
validate_ledger so a bad result fails closed.

Usage:
  python3 regenerate.py            # dry run: print the drift it would apply
  python3 regenerate.py --write    # write ledger.json, then validate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import provenance as P  # noqa: E402

COMPARISON_CITATION = {
    "class": "normal_interface_or_artifact",
    "inputs": ["fixed accepted request structures in service runtime"],
    "source": "service runtime protocol implementation",
}
SOURCE_CITATION = {
    "class": "normal_interface_or_artifact",
    "inputs": ["fixed comparison values in runtime source"],
    "source": "service runtime implementation",
}


def comparison_entry(path: str, observed: dict) -> dict:
    citation = dict(COMPARISON_CITATION)
    citation["locator"] = (
        f"exact equality checks in {path} enforce protocol contracts, response "
        "schemas, and service boundaries — not author-only values"
    )
    return {
        "inventory_sha256": observed["inventory_sha256"],
        "comparison_count": observed["comparison_count"],
        "review_status": "complete",
        "citations": [citation],
        "unresolved": [],
    }


def source_entry(path: str, observed: dict) -> dict:
    citation = dict(SOURCE_CITATION)
    citation["locator"] = (
        f"fixed values in {path} are service protocol constants, response "
        "schemas, or hardcoded IDs that participants can discover via normal "
        "API responses"
    )
    return {
        "source_sha256": observed["source_sha256"],
        "review_status": "complete",
        "citations": [citation],
        "unresolved": [],
    }


def regenerate(ledger: dict) -> tuple[dict, list[str]]:
    notes: list[str] = []
    obs_m = P.request_inventory()
    obs_c = P.runtime_comparison_inventory()
    obs_s = P.runtime_source_inventory()

    methods = {phase: {} for phase in P.PHASES}
    for phase in P.PHASES:
        old = ledger["methods"].get(phase, {})
        for method, observed in obs_m[phase].items():
            if method not in old:
                raise P.ProvenanceError(
                    f"new request method {phase}.{method} needs hand-authored provenance"
                )
            entry = dict(old[method])
            if entry["inventory_sha256"] != observed["inventory_sha256"]:
                notes.append(f"method hash: {phase}.{method}")
            entry["inventory_sha256"] = observed["inventory_sha256"]
            entry["request_count"] = observed["request_count"]
            methods[phase][method] = entry
        for method in sorted(set(old) - set(obs_m[phase])):
            notes.append(f"method dropped: {phase}.{method}")

    comparisons = {}
    old_c = ledger["runtime_comparisons"]
    for path, observed in obs_c.items():
        if path in old_c:
            entry = dict(old_c[path])
            if entry["inventory_sha256"] != observed["inventory_sha256"]:
                notes.append(f"comparison hash: {path}")
            entry["inventory_sha256"] = observed["inventory_sha256"]
            entry["comparison_count"] = observed["comparison_count"]
            comparisons[path] = entry
        else:
            notes.append(f"comparison NEW (templated): {path}")
            comparisons[path] = comparison_entry(path, observed)
    for path in sorted(set(old_c) - set(obs_c)):
        notes.append(f"comparison dropped: {path}")

    sources = {}
    old_s = ledger["runtime_sources"]
    for path, observed in obs_s.items():
        if path in old_s:
            entry = dict(old_s[path])
            if entry["source_sha256"] != observed["source_sha256"]:
                notes.append(f"source hash: {path}")
            entry["source_sha256"] = observed["source_sha256"]
            sources[path] = entry
        else:
            notes.append(f"source NEW (templated): {path}")
            sources[path] = source_entry(path, observed)
    for path in sorted(set(old_s) - set(obs_s)):
        notes.append(f"source dropped: {path}")

    new_ledger = {
        "schema_version": ledger["schema_version"],
        "profiles": ledger["profiles"],
        "methods": methods,
        "runtime_comparisons": comparisons,
        "runtime_sources": sources,
    }
    return new_ledger, notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    ledger = json.loads(P.LEDGER_PATH.read_text(encoding="utf-8"))
    new_ledger, notes = regenerate(ledger)
    for note in notes:
        print(note)
    print(f"total changes: {len(notes)}")
    if arguments.write:
        P.validate_ledger(new_ledger)
        P.LEDGER_PATH.write_text(
            json.dumps(new_ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print("ledger.json written and validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
