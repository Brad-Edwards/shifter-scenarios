"""Index documents placed in Orion's external review room."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import unquote

import requests
from airflow.decorators import dag, task
from qdrant_client import QdrantClient, models


NEXTCLOUD_URL = "http://10.61.30.23"
NEXTCLOUD_HOST = "files.keplerops.lab"
NEXTCLOUD_AUTH = ("reviewer", "KeplerV2-Training-Reviewer")
DAV_ROOT = f"{NEXTCLOUD_URL}/remote.php/dav/files/reviewer/Partner%20Rooms/Cinder%20Labs"
TIKA_URL = "http://10.61.50.71:9998"
QDRANT_URL = "http://10.61.50.72:6333"
QDRANT_COLLECTION = "orion_partner_intake"


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def vector(text: str) -> list[float]:
    result = [0.0] * 128
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        result[int.from_bytes(digest[:4], "big") % 128] += 1.0 if digest[4] & 1 else -1.0
    norm = sum(value * value for value in result) ** 0.5 or 1.0
    return [value / norm for value in result]


@dag(
    dag_id="orion_partner_sources",
    schedule="*/1 * * * *",
    start_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    tags=["orion", "partner", "retrieval"],
)
def orion_partner_sources():
    @task
    def index_room() -> dict[str, int]:
        qdrant = QdrantClient(url=QDRANT_URL)
        if not qdrant.collection_exists(QDRANT_COLLECTION):
            qdrant.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=models.VectorParams(size=128, distance=models.Distance.COSINE),
            )
        indexed = 0
        for folder in ("Submissions", "Policy%20Exceptions"):
            response = checked(requests.request(
                "PROPFIND",
                f"{DAV_ROOT}/{folder}",
                headers={"Host": NEXTCLOUD_HOST, "Depth": "1"},
                auth=NEXTCLOUD_AUTH,
                timeout=30,
            ))
            root = ET.fromstring(response.content)
            for item in root.findall("{DAV:}response")[1:]:
                href = item.findtext("{DAV:}href") or ""
                name = unquote(href.rstrip("/").split("/")[-1])
                if not name or href.endswith("/"):
                    continue
                content_response = checked(requests.get(
                    f"{NEXTCLOUD_URL}{href}",
                    headers={"Host": NEXTCLOUD_HOST},
                    auth=NEXTCLOUD_AUTH,
                    timeout=45,
                ))
                content = content_response.content
                digest = hashlib.sha256(content).hexdigest()
                tika = checked(requests.put(
                    f"{TIKA_URL}/tika",
                    data=content,
                    headers={"Accept": "text/plain", "Content-Type": content_response.headers.get("Content-Type", "application/octet-stream")},
                    timeout=120,
                )).text.strip()
                if not tika:
                    continue
                source_uri = f"nextcloud://Partner Rooms/Cinder Labs/{unquote(folder)}/{name}"
                qdrant.upsert(
                    collection_name=QDRANT_COLLECTION,
                    points=[models.PointStruct(
                        id=int(digest[:15], 16),
                        vector=vector(tika),
                        payload={
                            "title": name,
                            "filename": name,
                            "sha256": digest,
                            "source_uri": source_uri,
                            "partner_source": True,
                            "text": tika,
                            "citation": {"source": source_uri, "title": name, "filename": name, "sha256": digest},
                        },
                    )],
                    wait=True,
                )
                indexed += 1
        return {"indexed": indexed}

    index_room()


orion_partner_sources()
