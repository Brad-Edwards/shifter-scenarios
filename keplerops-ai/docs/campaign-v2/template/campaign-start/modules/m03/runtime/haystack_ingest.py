#!/usr/bin/env python3
"""Write one exact, server-fetched source revision through Haystack into Qdrant."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request

from haystack import Document
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy
from haystack.utils import Secret
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore


def vector(text: str) -> list[float]:
    values = [0.0] * 128
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode()).digest()
        values[int.from_bytes(digest[:4], "big") % len(values)] += (
            1.0 if digest[4] & 1 else -1.0
        )
    norm = sum(item * item for item in values) ** 0.5 or 1.0
    return [item / norm for item in values]


def main() -> None:
    source = json.load(sys.stdin)
    required = {"source_id", "text", "source_sha256", "source_revision", "url", "title"}
    missing = required - set(source)
    if missing:
        raise ValueError(f"source record lacks {sorted(missing)}")
    text = str(source["text"])
    if hashlib.sha256(text.encode()).hexdigest() != source["source_sha256"]:
        raise ValueError("source bytes do not match the declared digest")
    document = Document(
        id=str(source["point_id"]),
        content=text,
        embedding=vector(text),
        meta={key: value for key, value in source.items() if key not in {"text", "point_id"}},
    )
    store = QdrantDocumentStore(
        url=os.environ["QDRANT_WRITE_URL"],
        api_key=Secret.from_token(os.environ["QDRANT_WRITE_KEY"]),
        index="orion_partner_intake",
        embedding_dim=128,
        recreate_index=False,
        return_embedding=False,
        wait_result_from_api=True,
    )
    result = DocumentWriter(document_store=store, policy=DuplicatePolicy.OVERWRITE).run(
        documents=[document]
    )
    flattened = {key: value for key, value in source.items() if key != "point_id"}
    request = urllib.request.Request(
        f"{os.environ['QDRANT_WRITE_URL'].rstrip('/')}/collections/orion_partner_intake/points/payload?wait=true",
        data=json.dumps({"payload": flattened, "points": [document.id]}, separators=(",", ":")).encode(),
        headers={"Content-Type": "application/json", "api-key": os.environ["QDRANT_WRITE_KEY"]},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status not in {200, 202}:
            raise RuntimeError(f"Qdrant metadata normalization returned {response.status}")
    print(json.dumps({"point_id": document.id, "documents_written": result["documents_written"]}))


if __name__ == "__main__":
    main()
