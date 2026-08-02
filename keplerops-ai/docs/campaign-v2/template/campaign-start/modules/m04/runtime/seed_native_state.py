#!/usr/bin/env python3
"""Build deterministic normal Orion conversation and export seed records."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile


ARCHIVE_REFERENCE = "7403"
ARCHIVE_OWNER = "release.approver"
ARCHIVE_FLAG = "FLAG{dadac50b46dc79eb}"


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def conversation(conversation_id: str, actor: str, messages: list[dict[str, str]], *, attachment: dict[str, str] | None = None) -> dict[str, object]:
    record: dict[str, object] = {
        "conversation_id": conversation_id,
        "workflow_id": "workflow-support-history",
        "actor": actor,
        "messages": messages,
        "citations": [],
        "tool_events": [],
        "handoff_id": None,
        "request_id": f"seed-{conversation_id}",
        "trace_id": hashlib.sha256(conversation_id.encode()).hexdigest()[:32],
        "parser_state": {"unbalanced_context_delimiter": False, "structured_tool_keyword": False},
        "updated_at": 1785628800,
    }
    if attachment:
        record["attachments"] = [attachment]
    return record


def archive(owner: str, records: list[dict[str, object]]) -> bytes:
    manifest = {
        "schema": "keplerops.orion.conversation-export/v1",
        "owner": owner,
        "conversation_count": len(records),
        "conversation_ids": [str(item["conversation_id"]) for item in records],
        "created_at": 1785628800,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr("manifest.json", json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        for record in records:
            output.writestr(
                f"conversations/{record['conversation_id']}.json",
                json.dumps(record, sort_keys=True, indent=2) + "\n",
            )
    return buffer.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)

    own = conversation(
        "support-review-own-2026-07",
        "support.analyst",
        [
            {"role": "user", "content": "Summarize my open Orion support reviews."},
            {"role": "assistant", "content": "Your current review history contains only the Helios preview case."},
        ],
    )
    neighbor = [
        conversation(
            f"release-approver-{index}",
            ARCHIVE_OWNER,
            [
                {"role": "user", "content": f"Archive release approval discussion {index}."},
                {"role": "assistant", "content": "Stored under the bounded Orion support retention policy."},
            ],
            attachment={"name": "service-review.txt", "content": ARCHIVE_FLAG} if index == 2 else None,
        )
        for index in range(1, 4)
    ]
    payload = archive(ARCHIVE_OWNER, neighbor)
    export = {
        "reference": ARCHIVE_REFERENCE,
        "owner": ARCHIVE_OWNER,
        "archive_sha256": hashlib.sha256(payload).hexdigest(),
        "conversation_count": len(neighbor),
        "archive_base64": base64.b64encode(payload).decode(),
        "created_at": 1785628800,
    }
    (args.output / "own-conversation.json").write_text(canonical(own), encoding="utf-8")
    (args.output / "neighbor-export.json").write_text(canonical(export), encoding="utf-8")
    (args.output / "neighbor-archive.sha256").write_text(export["archive_sha256"] + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
