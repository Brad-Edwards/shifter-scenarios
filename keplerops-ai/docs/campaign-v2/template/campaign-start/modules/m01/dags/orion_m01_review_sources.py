"""Index ordinary policy-exception files from the earned partner room."""

from __future__ import annotations

import hashlib
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote, unquote

import requests
from airflow.exceptions import AirflowSkipException
from airflow.sdk import dag, get_current_context, task
from haystack import Document
from haystack.components.preprocessors import DocumentSplitter
from qdrant_client import QdrantClient, models


NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "http://10.61.50.42").rstrip("/")
NEXTCLOUD_HOST = os.getenv("NEXTCLOUD_HOST", "files.keplerops.lab")
NEXTCLOUD_USER = os.getenv("NEXTCLOUD_OWNER_USER", "reviewer")
NEXTCLOUD_AUTH = (NEXTCLOUD_USER, os.getenv("NEXTCLOUD_OWNER_PASSWORD", "KeplerV2-Training-Reviewer"))
ROOM_PATH = "/Partner Rooms/Cinder Labs/Policy Exceptions"
DAV_ROOT = f"{NEXTCLOUD_URL}/remote.php/dav/files/{quote(NEXTCLOUD_USER)}{quote(ROOM_PATH, safe='/')}"
TIKA_URL = os.getenv("TIKA_URL", "http://tika:9998").rstrip("/")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant-writer:6333")
QDRANT_COLLECTION = "orion_partner_intake"
VECTOR_SIZE = 128


def vector(text: str) -> list[float]:
    result = [0.0] * VECTOR_SIZE
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        result[int.from_bytes(digest[:4], "big") % VECTOR_SIZE] += 1.0 if digest[4] & 1 else -1.0
    norm = sum(value * value for value in result) ** 0.5 or 1.0
    return [value / norm for value in result]


def properties(response: ET.Element) -> dict[str, str]:
    prop = response.find("{DAV:}propstat/{DAV:}prop")
    if prop is None:
        return {}
    return {
        "etag": (prop.findtext("{DAV:}getetag") or "").strip('"'),
        "content_type": prop.findtext("{DAV:}getcontenttype") or "application/octet-stream",
        "content_length": prop.findtext("{DAV:}getcontentlength") or "0",
    }


@dag(
    dag_id="orion_m01_review_sources",
    description="Extract and Haystack-index partner policy exceptions for Orion review summaries.",
    schedule="*/1 * * * *",
    start_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    tags=["orion", "partner", "nextcloud", "tika", "haystack", "qdrant"],
)
def orion_m01_review_sources():
    @task
    def index_policy_exceptions() -> dict[str, object]:
        run_id = str(get_current_context()["run_id"])
        response = requests.request(
            "PROPFIND", DAV_ROOT,
            headers={"Host": NEXTCLOUD_HOST, "Depth": "1"},
            auth=NEXTCLOUD_AUTH, timeout=30,
        )
        if response.status_code == 404:
            raise AirflowSkipException("the partner policy-exception folder is not available")
        response.raise_for_status()
        root = ET.fromstring(response.content)
        splitter = DocumentSplitter(split_by="passage", split_length=1, split_overlap=0)
        splitter.warm_up()
        qdrant = QdrantClient(url=QDRANT_URL)
        if not qdrant.collection_exists(QDRANT_COLLECTION):
            qdrant.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
            )
        indexed: list[dict[str, object]] = []
        for item in root.findall("{DAV:}response")[1:]:
            href = item.findtext("{DAV:}href") or ""
            filename = unquote(href.rstrip("/").split("/")[-1])
            if not filename or href.endswith("/") or filename.startswith("."):
                continue
            metadata = properties(item)
            downloaded = requests.get(
                f"{NEXTCLOUD_URL}{href}", headers={"Host": NEXTCLOUD_HOST},
                auth=NEXTCLOUD_AUTH, timeout=45,
            )
            downloaded.raise_for_status()
            content = downloaded.content
            source_sha256 = hashlib.sha256(content).hexdigest()
            extracted = requests.put(
                f"{TIKA_URL}/tika", data=content,
                headers={"Accept": "text/plain", "Content-Type": metadata["content_type"]},
                timeout=120,
            )
            extracted.raise_for_status()
            text = extracted.text.strip()
            if not text:
                continue
            nextcloud_path = f"{ROOM_PATH.lstrip('/')}/{filename}"
            source_uri = f"nextcloud://{nextcloud_path}"
            document = Document(
                id=source_sha256,
                content=text,
                meta={"sha256": source_sha256, "source_uri": source_uri},
            )
            children = splitter.run(documents=[document])["documents"]
            child_text = "\n\n".join(str(child.content or "").strip() for child in children if str(child.content or "").strip())
            if not child_text:
                continue
            payload = {
                "title": filename,
                "text": child_text,
                "sha256": source_sha256,
                "source_uri": source_uri,
                "nextcloud_path": nextcloud_path,
                "nextcloud_etag": metadata["etag"],
                "content_length": int(metadata["content_length"] or 0),
                "airflow_dag_id": "orion_m01_review_sources",
                "airflow_run_id": run_id,
                "haystack_document_id": document.id,
                "haystack_split_ids": [child.id for child in children],
                "haystack_splitter": "DocumentSplitter/passage",
                "source_identity": f"partner-policy:{source_sha256}",
            }
            points = [models.PointStruct(id=int(source_sha256[:15], 16), vector=vector(child_text), payload=payload)]
            qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)
            indexed.append({"nextcloud_path": nextcloud_path, "source_uri": source_uri, "sha256": source_sha256, "point_ids": [point.id for point in points]})
        if not indexed:
            raise AirflowSkipException("no policy-exception source requires indexing")
        return {"run_id": run_id, "indexed": indexed}

    index_policy_exceptions()


orion_m01_review_sources()
