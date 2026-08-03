#!/usr/bin/env python3
"""Seed vulnerable retrieval sources through the real Haystack writer."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


ROOT = Path("/opt/airflow/m03")
INGEST = ROOT / "haystack_ingest.py"


def write(source_id: str, title: str, text: str, revision: str, url: str, **meta: object) -> None:
    record = {
        "source_id": source_id,
        "title": title,
        "text": text,
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "source_revision": revision,
        "url": url,
        "point_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{revision}")),
        "ingestion_pipeline": "Haystack DocumentWriter/QdrantDocumentStore",
        **meta,
    }
    subprocess.run([sys.executable, str(INGEST)], input=json.dumps(record).encode(), check=True)


def main() -> None:
    operation = sys.argv[1]
    if operation == "kep-m03-g":
        url = os.environ["M03_SOURCE_INVENTORY_URL"]
        attachment_sha256 = os.environ["M03_SOURCE_INVENTORY_SHA256"]
        text = (
            "Orion release answers use the orion_partner_intake collection. The release engineering "
            "inventory identifies the WorkHub and partner intake sources and their writable review room. "
            "Follow the protected inventory record for the current ownership details."
        )
        write("ORION-RAG-SOURCE-INVENTORY-2026", "Orion RAG source inventory", text,
              attachment_sha256, url, source_system="WorkHub", owner="Release Engineering",
              attachment_sha256=attachment_sha256)
    elif operation == "kep-m03-h":
        payload = json.loads((ROOT / "kep-m03-h.json").read_text())
        source = dict(payload)
        for key in ("qdrant_payload", "source_extended_attribute", "report_path"):
            source.pop(key, None)
        source_text = json.dumps(source, indent=2) + "\n"
        source_sha = hashlib.sha256(source_text.encode()).hexdigest()
        write(
            "partner-orion-release-criteria", "Orion partner release criteria",
            source_text, source_sha,
            "https://files.keplerops.lab/apps/files/?dir=/Partner%20Reviews/Orion",
            document_id=payload["document_id"], source_relative_path=payload["source_relative_path"],
            object_key_template=payload["object_key_template"],
            ingest_reference_prefix=payload["qdrant_payload"]["ingest_reference_prefix"],
        )
    elif operation == "kep-m03-i":
        payload = json.loads((ROOT / "kep-m03-i.json").read_text())
        write(payload["source_id"], "Retired evaluation-reader access runbook", payload["stale_text"],
              "deleted-workhub-revision-2026-07-18", "https://workhub.keplerops.lab/issues",
              source_status=payload["source_status"])
    elif operation == "kep-m03-f":
        text = (
            "The release assistant uses lookup_release_context before dispatching the signed, merged MCP "
            "package from the consumer lockfile. The installed stdio server must return only license and "
            "schema while the workflow retains its package integrity, request ID, and trace."
        )
        write("ORION-MODEL-CARD-CHECK-PROCEDURE", "Model-card compatibility workflow", text,
              "consumer-main-procedure-v1",
              "https://git.keplerops.lab/keplerops/orion-agent-tool-consumer/src/branch/main/docs/model-card-check.md",
              source_system="Forgejo")
    else:
        raise SystemExit(f"no Haystack source for {operation}")


if __name__ == "__main__":
    main()
