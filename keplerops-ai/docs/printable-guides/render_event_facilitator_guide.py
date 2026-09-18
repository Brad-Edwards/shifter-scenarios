#!/usr/bin/env python3
"""Render the printable KeplerOps event facilitator guide from SDL contracts."""

from __future__ import annotations

import re
import subprocess
import tempfile
import textwrap
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]
SDL_MODULE_DIR = PACK_ROOT / "sdl" / "modules"
GUIDE_ROOT = PACK_ROOT / "docs" / "printable-guides"
OUT_MD = GUIDE_ROOT / "keplerops-event-facilitator-guide.md"
OUT_DOCX = GUIDE_ROOT / "keplerops-event-facilitator-guide.docx"
ATLAS_LEDGER = PACK_ROOT / "docs" / "campaign-v2" / "atlas-coverage-ledger.md"

ENCODING = "utf-8"
HARDWARE_RESERVED = {"kep-m06-m", "kep-m08-i"}

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
        "adversarial expansion workflow, then request the module receipt"
    ),
    "agent_persistence_expansion": (
        "create the persistence action and attempt through the participant-facing "
        "persistence expansion or platform workflow, then request the module receipt"
    ),
    "ai_supply_chain_expansion": (
        "create or mutate the candidate through the participant-facing backdoor "
        "platform workflow, submit it to the backdoor attempt route, then request "
        "the module receipt"
    ),
    "context_expansion": (
        "create the required context object through the participant-facing context "
        "expansion workflow, then request the context receipt"
    ),
    "deployed_ai_impact_expansion": (
        "create the contained platform-impact object through the participant-facing "
        "capstone impact workflow, submit it to the capstone attempt route, then "
        "request the capstone receipt"
    ),
    "model_access_expansion": (
        "use the participant-facing extraction platform workflow to create the "
        "access object, then request the extraction receipt"
    ),
    "model_secret_expansion": (
        "use the participant-facing secrets expansion workflow to create the "
        "model-secret evidence, then request the secrets receipt"
    ),
    "training_expansion": (
        "submit the required component evidence through the participant-facing "
        "training expansion workflow, then request the training receipt"
    ),
}


def wrap(value: str, width: int = 92) -> str:
    return "\n".join(textwrap.wrap(value, width=width, break_long_words=False, break_on_hyphens=False))


def md_codes(values: list[Any] | None, fallback: str = "None") -> str:
    if not values:
        return fallback
    return ", ".join(f"`{value}`" for value in values)


def module_sort_key(module: str) -> int:
    match = re.search(r"module-(\d+)-", module)
    return int(match.group(1)) if match else 999


def challenge_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    match = re.match(r"kep-m\d+-([a-z]+)$", row["challenge_id"])
    if not match:
        return (module_sort_key(row["module"]), 999, row["challenge_id"])
    ordinal = 0
    for char in match.group(1):
        ordinal = ordinal * 26 + (ord(char) - 96)
    return (module_sort_key(row["module"]), ordinal, row["challenge_id"])


def load_atlas_names() -> dict[str, str]:
    names: dict[str, str] = {}
    pattern = re.compile(r"^\| `(?P<id>AML\.T\d+(?:\.\d+)?) (?P<name>[^`]+)` \|")
    for line in ATLAS_LEDGER.read_text(encoding=ENCODING).splitlines():
        match = pattern.match(line)
        if match:
            names[match.group("id")] = match.group("name").strip()
    return names


def load_contracts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(SDL_MODULE_DIR.glob("module-*.sdl.yaml")):
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
        for key, behavior in (data.get("behavior_specifications") or {}).items():
            contract = ((behavior or {}).get("extensions") or {}).get("x-keplerops:challenge")
            if not contract:
                continue
            challenge_id = contract.get("challenge_id")
            if challenge_id in HARDWARE_RESERVED:
                continue
            if contract.get("implementation_status") == "planned":
                continue
            row = dict(contract)
            row["_behavior_key"] = key
            row["_source_file"] = path.name
            row["_authority_scope_refs"] = list(behavior.get("authority_scope_refs") or [])
            row["_ai_offensive_behavior_refs"] = list(behavior.get("ai_offensive_behavior_refs") or [])
            rows.append(row)
    rows.sort(key=challenge_sort_key)
    if len(rows) != 132:
        raise SystemExit(f"expected 132 event-ready challenge contracts, found {len(rows)}")
    return rows


def participant(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("participant_copy") or {}


def proof(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("proof") or {}


def implementation(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("implementation_evidence") or {}


def question(row: dict[str, Any]) -> str:
    return participant(row).get("question") or row["title"]


def systems(row: dict[str, Any]) -> str:
    refs = []
    for ref in row.get("_authority_scope_refs") or []:
        text = ref
        text = text.removeprefix("nodes.core.")
        text = text.removeprefix("content.core.")
        text = text.replace(".services.", " / ")
        text = text.replace(".", " / ")
        refs.append(text)
    delivery = row.get("flag_delivery") or {}
    asset = (delivery.get("delivery") or {}).get("asset")
    service = (delivery.get("delivery") or {}).get("service")
    if asset and service:
        refs.append(f"{asset} / {service}")
    values = sorted(set(refs + list(row.get("interfaces") or [])))
    return ", ".join(values) if values else "module participant services"


def atlas(row: dict[str, Any], names: dict[str, str]) -> str:
    techniques = implementation(row).get("primary_atlas_techniques") or []
    if not techniques:
        behavior_refs = row.get("_ai_offensive_behavior_refs") or []
        return "No exact ATLAS technique declared; behavior refs: " + md_codes(behavior_refs)
    values = []
    for technique in techniques:
        name = names.get(str(technique))
        values.append(f"`{technique}` {name}" if name else f"`{technique}`")
    return "; ".join(values)


def learning(row: dict[str, Any]) -> str:
    proof_kind = (proof(row).get("kind") or "native evidence").replace("_", " ")
    article = "an" if row["difficulty"][0].lower() in "aeiou" else "a"
    return (
        f"Translate {article} {row['difficulty']} challenge objective into native service evidence; "
        f"separate {proof_kind} proof from notes or guesses; understand why participant, "
        "range instance, prerequisites, and reset generation matter for scoring."
    )


def workflow(row: dict[str, Any]) -> str:
    return WORKFLOW_HINTS.get(
        proof(row).get("kind"),
        "create the native participant-visible evidence described by the objective, then request the module receipt",
    )


def likely_snags(row: dict[str, Any]) -> str:
    parts = [
        "using operator-only state or source files instead of participant-visible records",
        "asking for a receipt before the qualifying evidence exists",
        "submitting a receipt or flag to the wrong Shifter challenge",
        "losing track of reset generation after a range reset",
    ]
    prereqs = row.get("prerequisites") or []
    if prereqs:
        parts.insert(0, "missing or stale prerequisites: " + ", ".join(prereqs))
    if "browser" in (row.get("interfaces") or []):
        parts.append("missing the browser-visible artifact that ties the action to the participant")
    return "; ".join(parts)


def expected_solve(row: dict[str, Any]) -> str:
    prereqs = md_codes(row.get("prerequisites"))
    predicate = proof(row).get("predicate") or "The owning service records the participant action."
    return (
        f"Complete prerequisites {prereqs}. Have the participant perform the objective through "
        f"the listed surfaces and {workflow(row)}. Expected proof shape: {predicate}"
    )


def first_hint(row: dict[str, Any]) -> str:
    hints = participant(row).get("hints") or []
    return hints[0] if hints else "No participant hint is declared."


def render_summary(rows: list[dict[str, Any]]) -> list[str]:
    counts = Counter(row["module"] for row in rows)
    category_counts = Counter(participant(row).get("category", "Uncategorized") for row in rows)
    difficulty_counts = Counter(row["difficulty"] for row in rows)
    lines = [
        "# KeplerOps Event Facilitator Guide",
        "",
        "This guide is for organizers and facilitators coaching the KeplerOps AI Systems event.",
        "It covers the 132 event-ready challenges currently projected for participant play.",
        "It excludes the two hardware-reserved contracts, `kep-m06-m` and `kep-m08-i`.",
        "",
        "Use it to understand what each challenge is testing, what systems are involved,",
        "what a valid solve looks like at a high level, and where participants usually get stuck.",
        "",
        "## Coaching Model",
        "",
        "Coach the process, not the answer. Ask the participant to show the native record,",
        "receipt, run, artifact, model output, ticket, repository object, or browser state that",
        "they think satisfies the objective. Then help them find the first missing causal link.",
        "",
        "A valid solve has three parts:",
        "",
        "1. The participant performs the required action from an allowed participant surface.",
        "2. The owning KeplerOps system records the qualifying evidence in the current range and reset generation.",
        "3. The participant receives a `FLAG{...}` value and Shifter accepts it for the matching challenge.",
        "",
        "Do not reveal flags, final payload wording, source-code internals, proof database state,",
        "operator credentials, cloud console details, or exact hidden validator conditions.",
        "",
        "## Event Coverage",
        "",
        "| Module | Challenges |",
        "| --- | ---: |",
    ]
    for module in sorted(counts, key=module_sort_key):
        lines.append(f"| {MODULE_LABELS[module]} | {counts[module]} |")
    lines.extend(["", "| Difficulty | Challenges |", "| --- | ---: |"])
    for difficulty in ["accessible", "intermediate", "advanced", "expert"]:
        if difficulty_counts[difficulty]:
            lines.append(f"| {difficulty} | {difficulty_counts[difficulty]} |")
    lines.extend(["", "| Shifter category | Challenges |", "| --- | ---: |"])
    for category, count in sorted(category_counts.items()):
        lines.append(f"| {category} | {count} |")
    lines.extend(
        [
            "",
            "## Universal Snag Triage",
            "",
            "- If Shifter rejects a flag, confirm the participant copied the complete `FLAG{...}` value into the matching challenge.",
            "- If a receipt route rejects, confirm prerequisites, participant token, current reset generation, and the native evidence object.",
            "- If a participant has only prose, screenshots, or terminal output, ask which owning service recorded the effect.",
            "- If a challenge depends on a browser artifact, check that the action happened inside the assigned range desktop.",
            "- If the participant used a host shell, source tree, database console, cloud console, or operator credential, restart from the participant path.",
            "- If a reset happened, treat old receipts, IDs, and prerequisite state as stale until proven otherwise.",
            "",
            "## Challenge Facilitation Briefs",
            "",
        ]
    )
    return lines


def render_module_header(module: str, rows: list[dict[str, Any]]) -> list[str]:
    categories = sorted({participant(row).get("category", "Uncategorized") for row in rows})
    lines = [
        f"## {MODULE_LABELS[module]}",
        "",
        f"Challenges: {len(rows)}",
        "",
        f"Shifter categories: {', '.join(categories)}",
        "",
        "Facilitator stance: keep participants on the allowed participant surfaces,",
        "then ask them to explain which native system should hold the evidence.",
        "",
    ]
    return lines


def render_challenge(row: dict[str, Any], atlas_names: dict[str, str]) -> list[str]:
    p = participant(row)
    delivery = row.get("flag_delivery") or {}
    delivery_body = delivery.get("delivery") or {}
    event = proof(row).get("event") or {}
    lines = [
        f"### {row['challenge_id']} - {row['title']}",
        "",
        f"- **Shifter category:** {p.get('category', 'Uncategorized')}",
        f"- **Difficulty and points:** {row['difficulty']}, {row['points']} points",
        f"- **Prerequisites:** {md_codes(row.get('prerequisites'))}",
        f"- **Interfaces:** {md_codes(row.get('interfaces'))}",
        f"- **What it is:** {question(row)}",
        f"- **ATLAS techniques:** {atlas(row, atlas_names)}",
        f"- **Participants should learn:** {learning(row)}",
        f"- **Systems involved:** {systems(row)}",
        f"- **Expected solve:** {expected_solve(row)}",
        f"- **Likely snags:** {likely_snags(row)}",
        f"- **First coaching nudge:** {first_hint(row)}",
        f"- **Receipt coaching:** Use the `{MODULE_API[row['module']]}` module receipt path for `{row['flag_id']}` after native evidence exists.",
        f"- **Proof anchor:** evidence `{delivery.get('evidence_id', proof(row).get('evidence_id', 'not declared'))}`, event `{event.get('event_kind', 'not declared')}`, delivery `{delivery_body.get('kind', 'not declared')}` via `{delivery_body.get('asset', 'not declared')}` / `{delivery_body.get('service', 'not declared')}`.",
        "",
    ]
    return lines


def render_markdown(rows: list[dict[str, Any]]) -> str:
    atlas_names = load_atlas_names()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["module"]].append(row)
    lines = render_summary(rows)
    for module in sorted(grouped, key=module_sort_key):
        module_rows = grouped[module]
        lines.extend(render_module_header(module, module_rows))
        for row in module_rows:
            lines.extend(render_challenge(row, atlas_names))
    return "\n".join(lines).rstrip() + "\n"


def strip_docx_bookmarks(path: Path) -> None:
    bookmark_re = re.compile(rb"<w:bookmark(Start|End)\b[^>]*/>")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp_path = Path(tmp.name)
    try:
        with ZipFile(path, "r") as zin, ZipFile(tmp_path, "w", ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                    data = bookmark_re.sub(b"", data)
                zout.writestr(info, data)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def render_docx() -> None:
    subprocess.run(
        [
            "pandoc",
            str(OUT_MD),
            "--from=gfm",
            "--to=docx",
            "--standalone",
            "--metadata",
            "title=KeplerOps Event Facilitator Guide",
            "--output",
            str(OUT_DOCX),
        ],
        check=True,
    )
    strip_docx_bookmarks(OUT_DOCX)


def main() -> int:
    GUIDE_ROOT.mkdir(parents=True, exist_ok=True)
    rows = load_contracts()
    OUT_MD.write_text(render_markdown(rows), encoding=ENCODING)
    render_docx()
    print(f"rendered {len(rows)} challenges into {OUT_MD.relative_to(PACK_ROOT)}")
    print(f"rendered {OUT_DOCX.relative_to(PACK_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
