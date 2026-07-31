#!/usr/bin/env python3
"""Render SDL-backed playtester challenge walkthroughs."""

from __future__ import annotations

import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]
SDL_MODULE_DIR = PACK_ROOT / "sdl" / "modules"
OUT_ROOT = PACK_ROOT / "docs" / "playtester-guide" / "challenges"

AUTHORITY_SCOPE_REFS = "_authority_scope_refs"
BEHAVIOR_KEY = "_behavior_key"
CHALLENGE_ID = "challenge_id"
DIFFICULTY = "difficulty"
ENCODING = "utf-8"
FLAG_ID = "flag_id"
IMPLEMENTATION_EVIDENCE = "implementation_evidence"
IMPLEMENTATION_STATUS = "implementation_status"
MODULE = "module"
NOT_DECLARED = "not declared"
PARTICIPANT_COPY = "participant_copy"
PREREQUISITES = "prerequisites"
PROOF = "proof"
SOURCE_FILE = "_source_file"
TARGET_MINUTES = "target_minutes"
TITLE = "title"

MODULE_LABELS = {
    "module-01-agent-control": "Module 01 — Agent Control",
    "module-02-model-evasion": "Module 02 — Model Evasion",
    "module-03-context-poisoning": "Module 03 — Context Poisoning",
    "module-04-model-secrets": "Module 04 — Model Secrets",
    "module-05-agent-persistence": "Module 05 — Agent Persistence",
    "module-06-adversarial-input": "Module 06 — Adversarial Input",
    "module-07-training-poisoning": "Module 07 — Training Poisoning",
    "module-08-model-extraction": "Module 08 — Model Extraction",
    "module-09-model-backdoor": "Module 09 — Model Backdoor",
    "module-10-ai-capstone": "Module 10 — AI Capstone",
}

MODULE_API = {
    "module-01-agent-control": "agent",
    "module-02-model-evasion": "evasion",
    "module-03-context-poisoning": "context",
    "module-04-model-secrets": "secrets",
    "module-05-agent-persistence": "persistence",
    "module-06-adversarial-input": "adversarial",
    "module-07-training-poisoning": "training",
    "module-08-model-extraction": "extraction",
    "module-09-model-backdoor": "backdoor",
    "module-10-ai-capstone": "capstone",
}

WORKFLOW_HINTS = {
    "adversarial_expansion": (
        "Create the required component evidence through the participant-facing "
        "`/v1/adversarial/expansion/*` workflow, then request the module receipt."
    ),
    "agent_persistence_expansion": (
        "Create the persistence action and attempt through the participant-facing "
        "`/v1/persistence/expansion/*` or `/v1/persistence/platform/*` workflow, "
        "then request the module receipt."
    ),
    "ai_supply_chain_expansion": (
        "Create or mutate the candidate through the participant-facing "
        "`/v1/backdoor/platform/*` workflow, submit it to `/v1/backdoor/attempt`, "
        "then request the module receipt."
    ),
    "context_expansion": (
        "Create the required context object through the participant-facing "
        "`/v1/context/*` expansion workflow, then request the context receipt."
    ),
    "deployed_ai_impact_expansion": (
        "Create the contained platform-impact object through the participant-facing "
        "`/v1/capstone/impact/*` workflow, submit it to `/v1/capstone/attempt`, "
        "then request the capstone receipt."
    ),
    "model_access_expansion": (
        "Use the participant-facing `/v1/extraction/platform/*` workflow to create "
        "the access object, then request the extraction receipt."
    ),
    "model_secret_expansion": (
        "Use the participant-facing `/v1/secrets/expansion/*` workflow to create "
        "the model-secret evidence, then request the secrets receipt."
    ),
    "training_expansion": (
        "Submit the required component evidence through the participant-facing "
        "`/v1/training/expansion/*` workflow, then request the training receipt."
    ),
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def md_list(values: list[Any] | None, fallback: str = "None") -> str:
    if not values:
        return fallback
    return ", ".join(f"`{value}`" for value in values)


def load_contracts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(SDL_MODULE_DIR.glob("module-*.sdl.yaml")):
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
        for key, behavior in (data.get("behavior_specifications") or {}).items():
            extensions = (behavior or {}).get("extensions") or {}
            contract = extensions.get("x-keplerops:challenge")
            if not contract:
                continue
            row = dict(contract)
            row[BEHAVIOR_KEY] = key
            row[SOURCE_FILE] = path.name
            row[AUTHORITY_SCOPE_REFS] = list(behavior.get("authority_scope_refs") or [])
            rows.append(row)
    rows.sort(key=lambda item: item[CHALLENGE_ID])
    if len(rows) != 134:
        raise SystemExit(f"expected 134 playable challenge contracts, found {len(rows)}")
    return rows


def challenge_path(row: dict[str, Any]) -> Path:
    module_dir = OUT_ROOT / row[MODULE]
    return module_dir / f"{row[CHALLENGE_ID]}-{slug(row[TITLE])}.md"


def source_walkthrough_link(row: dict[str, Any]) -> str:
    evidence = row.get(IMPLEMENTATION_EVIDENCE) or {}
    path = evidence.get("manual_walkthrough")
    if not path:
        return "No deeper walkthrough contract is declared in the SDL."
    target_path = Path(path)
    if target_path.parts and target_path.parts[0] == "docs":
        target_path = Path(*target_path.parts[1:])
    target = Path("..") / ".." / ".." / target_path
    return f"[{path}]({target.as_posix()})"


def route_block(row: dict[str, Any]) -> str:
    api = MODULE_API[row[MODULE]]
    return "\n".join(
        [
            "```sh",
            f'curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \\',
            f'  "$GATEWAY/v1/{api}/challenges" | python3 -m json.tool',
            f'curl --fail --silent --show-error -X POST \\',
            f'  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\',
            f'  -d "{{}}" "$GATEWAY/v1/{api}/receipts/{row[FLAG_ID]}" | python3 -m json.tool',
            "```",
        ]
    )


def render_challenge(row: dict[str, Any]) -> str:
    proof = row.get(PROOF) or {}
    event = proof.get("event") or {}
    participant = row.get(PARTICIPANT_COPY) or {}
    flag_delivery = row.get("flag_delivery") or {}
    evidence = row.get(IMPLEMENTATION_EVIDENCE) or {}
    proof_kind = proof.get("kind", NOT_DECLARED)
    workflow_note = WORKFLOW_HINTS.get(
        proof_kind,
        "Use the module walkthrough contract and participant-facing APIs to create "
        "server-observed evidence, then request the module receipt.",
    )
    hints = participant.get("hints") or []
    hint_rows = "\n".join(f"- {hint}" for hint in hints) if hints else "- No participant hints declared."
    source = source_walkthrough_link(row)
    authority_refs = row.get(AUTHORITY_SCOPE_REFS) or []
    proof_fields = proof.get("proof_fields") or []
    primary_techniques = evidence.get("primary_atlas_techniques") or []
    lines = [
        f"# {row[CHALLENGE_ID]} — {row[TITLE]}",
        "",
        "[Challenge index](../README.md) | "
        f"[{MODULE_LABELS[row[MODULE]]}](index.md)",
        "",
        "This is an operator/playtester walkthrough. Do not place it in a participant bundle.",
        "",
        "## SDL contract",
        "",
        f"- Module: `{row[MODULE]}`",
        f"- Source SDL: `{row[SOURCE_FILE]}` / behavior `{row[BEHAVIOR_KEY]}`",
        f"- Status: `{row.get(IMPLEMENTATION_STATUS, NOT_DECLARED)}`",
        f"- Difficulty: `{row[DIFFICULTY]}`",
        f"- Points: `{row['points']}`",
        f"- Target time: {row.get(TARGET_MINUTES, NOT_DECLARED)} minutes",
        f"- Prerequisites: {md_list(row.get(PREREQUISITES))}",
        f"- Interfaces: {md_list(row.get('interfaces'))}",
        f"- Flag id: `{row[FLAG_ID]}`",
        f"- Outcome: `{row['outcome']}`",
        f"- Evidence id: `{flag_delivery.get('evidence_id', proof.get('evidence_id', NOT_DECLARED))}`",
        f"- Proof kind: `{proof_kind}`",
        f"- Event kind: `{event.get('event_kind', NOT_DECLARED)}`",
        f"- Reset owner: `{proof.get('reset_owner', NOT_DECLARED)}`",
        f"- Mutates scenario state: `{proof.get('mutates_scenario_state', NOT_DECLARED)}`",
        f"- Primary ATLAS techniques: {md_list(primary_techniques)}",
        f"- Authority scope refs: {md_list(authority_refs)}",
        "",
        "## Participant-facing objective",
        "",
        participant.get("question", "No participant objective declared."),
        "",
        "## Step-by-step walkthrough",
        "",
        "1. Start from the external Kasm participant workstation. Do not use GCP, SSH, "
        "Terraform outputs, database consoles, proof internals, generated service "
        "credentials, or operator-only files as proof of success.",
        "2. Obtain the participant token from the in-world synthetic start material "
        "described in [participant-start](../../participant-start.md). Set "
        "`GATEWAY=https://inference-gateway.keplerops.lab` and keep "
        "`CURL_CA_BUNDLE=/run/tls/ca.crt` exported.",
        f"3. Confirm this item is visible in the module challenge listing and, if "
        f"needed, view the CTFd prompt and hints. The SDL-declared participant hints are:",
        "",
        hint_rows,
        "",
        f"4. Complete prerequisites first: {md_list(row.get(PREREQUISITES))}. "
        "Prerequisite receipts must come from the participant path in the same range "
        "and reset generation; do not synthesize them from operator evidence.",
        f"5. Execute the challenge action: {participant.get('question', row.get(TITLE))}",
        f"6. Evidence workflow: {workflow_note}",
        "7. Request and inspect the receipt through the participant-visible receipt "
        "route. The route skeleton is:",
        "",
        route_block(row),
        "",
        "8. Verify that the returned receipt is bound to the current participant, "
        "range instance, reset generation, challenge id, flag id, and evidence id. "
        "A receipt that can be issued before the qualifying evidence exists is a defect.",
        "9. Run at least one representative negative control from the participant "
        "surface. Use the proof predicate below to choose the shortcut that should fail.",
        "10. Record timing, hints used, participant confusion, defects, and whether "
        "the proof route gave enough feedback to recover without operator intervention.",
        "",
        "## Expected proof",
        "",
        proof.get("predicate", "No proof predicate declared."),
        "",
        f"Required proof fields: {md_list(proof_fields)}",
        "",
        f"Deeper source walkthrough: {source}",
        "",
        "## Playtest capture template",
        "",
        "- Range instance:",
        "- Participant id:",
        "- Reset generation:",
        "- Start time / end time:",
        "- Hints viewed:",
        "- Outcome: pass / fail / abandoned / blocked",
        "- Receipt issued and verified: yes / no",
        "- Negative control attempted:",
        "- Defects or confusing behavior:",
        "- Notes for guide update:",
        "",
    ]
    return "\n".join(lines)


def render_module_index(module: str, rows: list[dict[str, Any]]) -> str:
    lines = [
        f"# {MODULE_LABELS[module]}",
        "",
        "[All challenges](../README.md)",
        "",
        "| Challenge | Difficulty | Points | Status | Target min | Prerequisites |",
        "| --- | --- | ---: | --- | ---: | --- |",
    ]
    for row in rows:
        path = challenge_path(row).name
        lines.append(
            f"| [{row[CHALLENGE_ID]} — {row[TITLE]}]({path}) | "
            f"{row[DIFFICULTY]} | {row['points']} | "
            f"{row.get(IMPLEMENTATION_STATUS, NOT_DECLARED)} | "
            f"{row.get(TARGET_MINUTES, '')} | {md_list(row.get(PREREQUISITES))} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_root_index(grouped: dict[str, list[dict[str, Any]]]) -> str:
    total = sum(len(rows) for rows in grouped.values())
    lines = [
        "# Challenge walkthrough index",
        "",
        "This index is generated from the playable challenge contracts in the modular ACES SDL.",
        f"It covers {total} realized challenges. The reserved hardware-attestation design is not included here because it is not a playable contract.",
        "",
        "| Module | Count | Walkthroughs |",
        "| --- | ---: | --- |",
    ]
    for module in sorted(grouped):
        lines.append(f"| {MODULE_LABELS[module]} | {len(grouped[module])} | [{module}]({module}/index.md) |")
    lines.extend(["", "## All challenge files", ""])
    for module in sorted(grouped):
        lines.append(f"### {MODULE_LABELS[module]}")
        lines.append("")
        for row in grouped[module]:
            path = challenge_path(row).relative_to(OUT_ROOT)
            lines.append(f"- [{row[CHALLENGE_ID]} — {row[TITLE]}]({path.as_posix()})")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    rows = load_contracts()
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row[MODULE]].append(row)
    for module, module_rows in grouped.items():
        (OUT_ROOT / module).mkdir()
        for row in module_rows:
            challenge_path(row).write_text(render_challenge(row), encoding=ENCODING)
        (OUT_ROOT / module / "index.md").write_text(
            render_module_index(module, module_rows),
            encoding=ENCODING,
        )
    (OUT_ROOT / "README.md").write_text(render_root_index(grouped), encoding=ENCODING)
    print(f"rendered {len(rows)} challenge walkthroughs into {OUT_ROOT.relative_to(PACK_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
