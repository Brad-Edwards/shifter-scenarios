#!/usr/bin/env python3
"""Render SDL-backed campaign handoff sections for module docs."""

from __future__ import annotations

import re
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]
SDL_MODULE_DIR = PACK_ROOT / "sdl" / "modules"
MODULE_DOC_ROOT = PACK_ROOT / "docs" / "campaign-v2" / "template" / "campaign-start" / "modules"

AUTHORITY_SCOPE_REFS = "_authority_scope_refs"
BEHAVIOR_KEY = "_behavior_key"
CHALLENGE_ID = "challenge_id"
ENCODING = "utf-8"
IMPLEMENTATION_EVIDENCE = "implementation_evidence"
MODULE = "module"
PARTICIPANT_COPY = "participant_copy"
PREREQUISITES = "prerequisites"
PROOF = "proof"
SOURCE_FILE = "_source_file"
TITLE = "title"

BEGIN = "<!-- BEGIN GENERATED CHALLENGE HANDOFF -->"
END = "<!-- END GENERATED CHALLENGE HANDOFF -->"

MODULE_LABELS = {
    "module-01-agent-control": "Module 01 - Agent Control",
    "module-02-model-evasion": "Module 02 - Model Evasion",
    "module-03-context-poisoning": "Module 03 - Context Poisoning",
    "module-04-model-secrets": "Module 04 - Model Secrets",
    "module-05-agent-persistence": "Module 05 - Agent Persistence",
    "module-06-adversarial-input": "Module 06 - Adversarial Input",
    "module-07-training-poisoning": "Module 07 - Training Poisoning",
    "module-08-model-extraction": "Module 08 - Model Extraction",
    "module-09-model-backdoor": "Module 09 - Model Backdoor",
    "module-10-ai-capstone": "Module 10 - AI Capstone",
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
        "create the required component evidence through the participant-facing "
        "/v1/adversarial/expansion workflow, then request the module receipt"
    ),
    "agent_persistence_expansion": (
        "create the persistence action and attempt through the participant-facing "
        "/v1/persistence expansion or platform workflow, then request the module receipt"
    ),
    "ai_supply_chain_expansion": (
        "create or mutate the candidate through the participant-facing "
        "/v1/backdoor platform workflow, submit it to /v1/backdoor/attempt, then request the module receipt"
    ),
    "context_expansion": (
        "create the required context object through the participant-facing "
        "/v1/context expansion workflow, then request the context receipt"
    ),
    "deployed_ai_impact_expansion": (
        "create the contained platform-impact object through the participant-facing "
        "/v1/capstone/impact workflow, submit it to /v1/capstone/attempt, then request the capstone receipt"
    ),
    "model_access_expansion": (
        "use the participant-facing /v1/extraction/platform workflow to create "
        "the access object, then request the extraction receipt"
    ),
    "model_secret_expansion": (
        "use the participant-facing /v1/secrets/expansion workflow to create "
        "the model-secret evidence, then request the secrets receipt"
    ),
    "training_expansion": (
        "submit the required component evidence through the participant-facing "
        "/v1/training/expansion workflow, then request the training receipt"
    ),
}

HARDWARE_RESERVED = {"kep-m06-m", "kep-m08-i"}


def wrap(value: str, width: int = 88) -> str:
    return "\n".join(textwrap.wrap(value, width=width, break_long_words=False, break_on_hyphens=False))


def bullet(label: str, value: str) -> str:
    wrapped = textwrap.wrap(value, width=84, break_long_words=False, break_on_hyphens=False)
    if not wrapped:
        return f"- **{label}:**"
    lines = [f"- **{label}:** {wrapped[0]}"]
    lines.extend(f"  {line}" for line in wrapped[1:])
    return "\n".join(lines)


def md_codes(values: list[Any] | None, fallback: str = "None") -> str:
    if not values:
        return fallback
    return ", ".join(f"`{value}`" for value in values)


def challenge_sort_key(row: dict[str, Any]) -> tuple[str, int, str]:
    match = re.match(r"kep-m(\d+)-([a-z]+)$", row[CHALLENGE_ID])
    if not match:
        return (row[MODULE], 999, row[CHALLENGE_ID])
    suffix = match.group(2)
    ordinal = 0
    for char in suffix:
        ordinal = ordinal * 26 + (ord(char) - 96)
    return (row[MODULE], ordinal, row[CHALLENGE_ID])


def module_dir(module: str) -> str:
    match = re.search(r"module-(\d+)-", module)
    if not match:
        raise ValueError(f"cannot derive module dir from {module}")
    return f"m{match.group(1)}"


def load_contracts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(SDL_MODULE_DIR.glob("module-*.sdl.yaml")):
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
        for key, behavior in (data.get("behavior_specifications") or {}).items():
            contract = ((behavior or {}).get("extensions") or {}).get("x-keplerops:challenge")
            if not contract:
                continue
            row = dict(contract)
            row[BEHAVIOR_KEY] = key
            row[SOURCE_FILE] = path.name
            row[AUTHORITY_SCOPE_REFS] = list(behavior.get("authority_scope_refs") or [])
            rows.append(row)
    rows.sort(key=challenge_sort_key)
    if len(rows) != 134:
        raise SystemExit(f"expected 134 playable challenge contracts, found {len(rows)}")
    return rows


def systems(row: dict[str, Any]) -> str:
    refs = []
    for ref in row.get(AUTHORITY_SCOPE_REFS) or []:
        text = ref
        text = text.removeprefix("nodes.core.")
        text = text.removeprefix("content.core.")
        text = text.replace(".services.", " / ")
        text = text.replace(".", " / ")
        refs.append(text)
    values = sorted(set(refs + list(row.get("interfaces") or [])))
    return ", ".join(values) if values else "module participant services"


def atlas(row: dict[str, Any]) -> str:
    evidence = row.get(IMPLEMENTATION_EVIDENCE) or {}
    return md_codes(evidence.get("primary_atlas_techniques"))


def question(row: dict[str, Any]) -> str:
    return (row.get(PARTICIPANT_COPY) or {}).get("question") or row[TITLE]


def workflow(row: dict[str, Any]) -> str:
    proof = row.get(PROOF) or {}
    return WORKFLOW_HINTS.get(
        proof.get("kind"),
        "create the native participant-visible evidence described by the module procedure, then request the module receipt",
    )


def learning(row: dict[str, Any]) -> str:
    proof_kind = ((row.get(PROOF) or {}).get("kind") or "native evidence").replace("_", " ")
    return (
        f"how to turn the {row['difficulty']} objective into native service evidence, "
        f"how the {proof_kind} proof boundary differs from a local note or copied answer, "
        "and how immutable records, controls, and reset generation affect scoring"
    )


def likely_snags(row: dict[str, Any]) -> str:
    prereqs = row.get(PREREQUISITES) or []
    parts = [
        "using operator-only state instead of participant-visible records",
        "requesting the receipt before the qualifying evidence exists",
        "copying local notes instead of the owning system locator",
    ]
    if prereqs:
        parts.insert(0, "missing or stale prerequisites: " + ", ".join(prereqs))
    if row[CHALLENGE_ID] in HARDWARE_RESERVED:
        parts.insert(0, "hardware-reserved coverage requires an enabled hardware lab and is outside the issue-62 event-ready count")
    return "; ".join(parts)


def receipt_command(row: dict[str, Any]) -> str:
    api = MODULE_API[row[MODULE]]
    return "\n".join(
        [
            "```sh",
            f'curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \\',
            f'  "$GATEWAY/v1/{api}/challenges" | python3 -m json.tool',
            f'curl --fail --silent --show-error -X POST \\',
            f'  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\',
            f'  -d "{{}}" "$GATEWAY/v1/{api}/receipts/{row["flag_id"]}" | python3 -m json.tool',
            "```",
        ]
    )


def challenge_list_command(row: dict[str, Any]) -> str:
    api = MODULE_API[row[MODULE]]
    return "\n".join(
        [
            "```sh",
            f'curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \\',
            f'  "$GATEWAY/v1/{api}/challenges" | python3 -m json.tool',
            "```",
        ]
    )


def render_facilitator(rows: list[dict[str, Any]]) -> str:
    module = rows[0][MODULE]
    lines = [
        BEGIN,
        "",
        "## Challenge Facilitation Briefs",
        "",
        wrap(
            f"Generated from the SDL challenge contracts for {MODULE_LABELS[module]}. "
            "Use this as the per-challenge facilitation checklist; keep the hand-authored "
            "module notes below for deeper diagnosis and recovery guidance."
        ),
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### `{row[CHALLENGE_ID]}` - {row[TITLE]}",
                "",
                bullet("What it is", question(row)),
                bullet("ATLAS techniques", atlas(row)),
                bullet("Participants should learn", learning(row)),
                bullet("Systems involved", systems(row)),
                bullet(
                    "Expected solve",
                    f"Complete prerequisites {md_codes(row.get(PREREQUISITES))}; {workflow(row)}. "
                    "The facilitator should look for a native carrier owned by the relevant service, "
                    "not chat prose, shell output, or an operator reconstruction.",
                ),
                bullet("Likely snags", likely_snags(row)),
                "",
            ]
        )
    lines.extend([END, ""])
    return "\n".join(lines)


def render_qa(rows: list[dict[str, Any]]) -> str:
    module = rows[0][MODULE]
    lines = [
        BEGIN,
        "",
        "## Challenge-by-Challenge QA Checklist",
        "",
        wrap(
            f"Generated from the SDL challenge contracts for {MODULE_LABELS[module]}. "
            "Walk these from the participant Kali/Kasm desktop and the Shifter UI. "
            "Use any more detailed hand-authored positive procedure below when present, "
            "but every challenge still needs the receipt and UI acceptance checks here."
        ),
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### `{row[CHALLENGE_ID]}` - {row[TITLE]}",
                "",
                bullet("Preconditions", md_codes(row.get(PREREQUISITES))),
                bullet("Participant surfaces", systems(row)),
                "",
                "**Do this:**",
                "",
                "1. Start from the assigned Kasm/Kali participant desktop. Do not use host shells,",
                "   database consoles, source files, seed files, operator credentials, or internal",
                "   cloud/project views.",
                "2. In the Kali terminal, set the participant token and gateway:",
                "",
                "   ```sh",
                "   export GATEWAY=https://inference-gateway.keplerops.lab",
                "   export CURL_CA_BUNDLE=/run/tls/ca.crt",
                "   export TOKEN=<participant-earned-token>",
                "   ```",
                "",
                f"3. Confirm `{row[CHALLENGE_ID]}` is visible in the module challenge list:",
                "",
                challenge_list_command(row),
                "",
                f"4. Complete prerequisites first: {md_codes(row.get(PREREQUISITES))}.",
                f"5. Perform the participant objective: {question(row)}",
                f"6. Evidence workflow: {workflow(row)}.",
                "7. Request the challenge receipt only after the native evidence exists:",
                "",
                "```sh",
                f'curl --fail --silent --show-error -X POST \\',
                f'  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\',
                f'  -d "{{}}" "$GATEWAY/v1/{MODULE_API[module]}/receipts/{row["flag_id"]}" | python3 -m json.tool',
                "```",
                "",
                "8. Copy the returned `FLAG{...}` value into the matching Shifter challenge and submit it.",
                "",
                "**You should get:**",
                "",
                "- The native owning system shows the qualifying evidence created by the participant.",
                "- The receipt response is bound to the current participant, range, reset generation,",
                "  challenge id, and evidence id.",
                "- Shifter accepts the value and marks this challenge complete.",
                "",
                "**Negative check:** Try one shortcut that omits the required native evidence, uses",
                "stale prerequisite state, or substitutes a local/operator record. The shortcut must",
                "not produce an accepted receipt.",
                "",
                "**Capture:** Screenshots or exports for the owning-system evidence, challenge list,",
                "receipt JSON, Shifter acceptance, and the failed negative check.",
                "",
            ]
        )
    lines.extend([END, ""])
    return "\n".join(lines)


def render_participant(rows: list[dict[str, Any]]) -> str:
    module = rows[0][MODULE]
    lines = [
        BEGIN,
        "",
        "## No-Spoiler Challenge Briefs",
        "",
        wrap(
            f"Generated from the SDL challenge contracts for {MODULE_LABELS[module]}. "
            "This section is safe for participant orientation: it explains relevance, skills, "
            "and likely systems without giving flags, internal proof details, receipt routes, or final answers."
        ),
        "",
    ]
    for row in rows:
        hints = ((row.get(PARTICIPANT_COPY) or {}).get("hints") or [])[:2]
        hint_text = " ".join(hints) if hints else "Look for the native record that the affected system would normally retain."
        lines.extend(
            [
                f"### `{row[CHALLENGE_ID]}` - {row[TITLE]}",
                "",
                bullet("Why it matters", question(row)),
                bullet(
                    "Skills tested",
                    "reading the participant prompt carefully, using the allowed interfaces, "
                    "preserving native service evidence, checking controls, and keeping digest or locator continuity",
                ),
                bullet("Systems you may touch", systems(row)),
                bullet("Before starting", f"Complete prerequisites {md_codes(row.get(PREREQUISITES))}."),
                bullet("If stuck", hint_text),
                "",
            ]
        )
    lines.extend([END, ""])
    return "\n".join(lines)


def replace_section(text: str, section: str) -> str:
    pattern = re.compile(rf"{re.escape(BEGIN)}.*?{re.escape(END)}\n?", re.DOTALL)
    if pattern.search(text):
        return pattern.sub(section, text)
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join([lines[0], "", section, *lines[1:]]) + "\n"
    return section + text


def write_kind(rows: list[dict[str, Any]], kind: str, content: str) -> None:
    target = MODULE_DOC_ROOT / module_dir(rows[0][MODULE]) / f"{kind}.md"
    original = target.read_text(encoding=ENCODING)
    updated = replace_section(original, content)
    target.write_text(updated, encoding=ENCODING)


def main() -> int:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in load_contracts():
        grouped[row[MODULE]].append(row)
    for module in sorted(grouped):
        rows = grouped[module]
        write_kind(rows, "facilitator", render_facilitator(rows))
        write_kind(rows, "qa", render_qa(rows))
        write_kind(rows, "participant", render_participant(rows))
    print(f"rendered campaign handoff sections for {sum(len(v) for v in grouped.values())} challenges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
