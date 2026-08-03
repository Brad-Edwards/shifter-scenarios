"""Index participant-owned bytes from an earned Orion partner room."""

from __future__ import annotations

import hashlib
import json
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
NEXTCLOUD_AUTH = (
    os.getenv("NEXTCLOUD_OWNER_USER", "reviewer"),
    os.getenv("NEXTCLOUD_OWNER_PASSWORD", "KeplerV2-Training-Reviewer"),
)
ROOM_PATH = "/Partner Rooms/Cinder Labs"
DAV_ROOT = (
    f"{NEXTCLOUD_URL}/remote.php/dav/files/{quote(NEXTCLOUD_AUTH[0])}"
    f"{quote(ROOM_PATH, safe='/')}"
)
TIKA_URL = os.getenv("TIKA_URL", "http://tika:9998").rstrip("/")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant-writer:6333")
QDRANT_COLLECTION = "orion_partner_intake"
ZAMMAD_URL = os.getenv("ZAMMAD_URL", "http://10.61.50.43:8080").rstrip("/")
ZAMMAD_HOST = os.getenv("ZAMMAD_HOST", "support.keplerops.lab")
ZAMMAD_AUTH = (
    os.getenv("ZAMMAD_USER", "range-admin"),
    os.getenv("ZAMMAD_PASSWORD", "KeplerV2-Training-Zammad-Admin"),
)
VECTOR_SIZE = 128


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def vector(text: str) -> list[float]:
    result = [0.0] * VECTOR_SIZE
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        result[int.from_bytes(digest[:4], "big") % VECTOR_SIZE] += 1.0 if digest[4] & 1 else -1.0
    norm = sum(value * value for value in result) ** 0.5 or 1.0
    return [value / norm for value in result]


def room_origin() -> dict[str, object]:
    headers = {"Host": ZAMMAD_HOST}
    tickets = checked(requests.get(
        f"{ZAMMAD_URL}/api/v1/tickets", params={"per_page": 100},
        headers=headers, auth=ZAMMAD_AUTH, timeout=30,
    )).json()
    for ticket in sorted(tickets, key=lambda item: int(item["id"]), reverse=True):
        articles = checked(requests.get(
            f"{ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/{ticket['id']}",
            headers=headers, auth=ZAMMAD_AUTH, timeout=30,
        )).json()
        if not any(article.get("subject") == "External collaboration ready" for article in articles):
            continue
        customer = checked(requests.get(
            f"{ZAMMAD_URL}/api/v1/users/{ticket['customer_id']}", headers=headers,
            auth=ZAMMAD_AUTH, timeout=30,
        )).json()
        email = str(customer.get("email", "")).lower()
        if email.endswith("@cinder.lab"):
            return {"ticket_id": int(ticket["id"]), "ticket_number": str(ticket["number"]), "source_actor": email}
    raise AirflowSkipException("the Cinder partner room has not been earned")


def props(response: ET.Element) -> dict[str, str]:
    prop = response.find("{DAV:}propstat/{DAV:}prop")
    if prop is None:
        return {}
    return {
        "etag": (prop.findtext("{DAV:}getetag") or "").strip('"'),
        "last_modified": prop.findtext("{DAV:}getlastmodified") or "",
        "content_type": prop.findtext("{DAV:}getcontenttype") or "application/octet-stream",
        "content_length": prop.findtext("{DAV:}getcontentlength") or "0",
    }


def source_card(document: Document) -> dict[str, str] | None:
    """Recognize a complete card only after Haystack produced a child document."""
    try:
        value = json.loads((document.content or "").strip())
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value.get("schema") != "orion.source-card/v1":
        return None
    fields = {key: str(value.get(key, "")).strip() for key in ("title", "authority", "locator", "digest", "body")}
    if not all(fields.values()):
        return None
    body_digest = hashlib.sha256(fields["body"].encode()).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", fields["digest"]) or fields["digest"] != body_digest:
        return None
    return fields


@dag(
    dag_id="orion_partner_sources",
    schedule="*/1 * * * *",
    start_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    tags=["orion", "partner", "retrieval", "haystack"],
)
def orion_partner_sources():
    @task
    def index_room() -> dict[str, object]:
        context = get_current_context()
        run_id = str(context["run_id"])
        origin = room_origin()
        splitter = DocumentSplitter(split_by="passage", split_length=1, split_overlap=0)
        splitter.warm_up()
        qdrant = QdrantClient(url=QDRANT_URL)
        if not qdrant.collection_exists(QDRANT_COLLECTION):
            qdrant.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
            )
        indexed: list[dict[str, object]] = []
        for folder in ("Submissions", "Policy%20Exceptions"):
            response = requests.request(
                "PROPFIND", f"{DAV_ROOT}/{folder}",
                headers={"Host": NEXTCLOUD_HOST, "Depth": "1"},
                auth=NEXTCLOUD_AUTH, timeout=30,
            )
            if response.status_code == 404:
                continue
            root = ET.fromstring(checked(response).content)
            for item in root.findall("{DAV:}response")[1:]:
                href = item.findtext("{DAV:}href") or ""
                name = unquote(href.rstrip("/").split("/")[-1])
                if not name or href.endswith("/") or name.startswith("."):
                    continue
                metadata = props(item)
                downloaded = checked(requests.get(
                    f"{NEXTCLOUD_URL}{href}", headers={"Host": NEXTCLOUD_HOST},
                    auth=NEXTCLOUD_AUTH, timeout=45,
                ))
                content = downloaded.content
                digest = hashlib.sha256(content).hexdigest()
                extracted = checked(requests.put(
                    f"{TIKA_URL}/tika", data=content,
                    headers={"Accept": "text/plain", "Content-Type": metadata["content_type"]},
                    timeout=120,
                )).text.strip()
                if not extracted:
                    continue
                source_uri = f"nextcloud://{ROOM_PATH.lstrip('/')}/{unquote(folder)}/{name}"
                base_id = int(digest[:15], 16)
                common = {
                    **origin,
                    "title": name,
                    "filename": name,
                    "sha256": digest,
                    "source_uri": source_uri,
                    "nextcloud_path": f"{ROOM_PATH}/{unquote(folder)}/{name}",
                    "nextcloud_etag": metadata["etag"],
                    "content_length": int(metadata["content_length"] or 0),
                    "airflow_run_id": run_id,
                    "partner_source": True,
                    "source_identity": f"outer:{digest}",
                    "text": extracted,
                    "citation": {"source": source_uri, "title": name, "sha256": digest},
                }
                outer = Document(id=digest, content=extracted, meta=common)
                split_documents = splitter.run(documents=[outer])["documents"]
                points = [models.PointStruct(id=base_id, vector=vector(extracted), payload={**common, "haystack_document_id": outer.id})]
                for split_index, split_document in enumerate(split_documents):
                    fields = source_card(split_document)
                    if fields is None:
                        continue
                    child_id = int(hashlib.sha256(f"{digest}:{fields['digest']}".encode()).hexdigest()[:15], 16)
                    points.append(models.PointStruct(
                        id=child_id,
                        vector=vector(fields["body"]),
                        payload={
                            **origin,
                            "title": fields["title"],
                            "authority": fields["authority"],
                            "source_uri": fields["locator"],
                            "sha256": fields["digest"],
                            "text": fields["body"],
                            "source_identity": f"inner:{fields['digest']}",
                            "parent_sha256": digest,
                            "parent_source_uri": source_uri,
                            "haystack_parent_id": split_document.meta.get("source_id", outer.id),
                            "haystack_split_id": split_document.id,
                            "haystack_split_index": split_index,
                            "haystack_splitter": "DocumentSplitter/passage",
                            "airflow_run_id": run_id,
                            "partner_source": True,
                            "citation": {
                                "source": fields["locator"], "title": fields["title"],
                                "authority": fields["authority"], "sha256": fields["digest"],
                            },
                        },
                    ))
                qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)
                indexed.append({"path": common["nextcloud_path"], "sha256": digest, "point_ids": [point.id for point in points]})
        if not indexed:
            raise AirflowSkipException("no earned-room source requires indexing")
        return {"run_id": run_id, "ticket_id": origin["ticket_id"], "indexed": indexed}

    index_room()


orion_partner_sources()
