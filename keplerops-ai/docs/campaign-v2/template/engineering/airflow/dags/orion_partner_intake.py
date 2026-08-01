from __future__ import annotations

import hashlib
import math
import os
import re
from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import quote

import boto3
import requests
from airflow.exceptions import AirflowSkipException
from airflow.sdk import dag, get_current_context, task
from qdrant_client import QdrantClient, models


ZAMMAD_URL = os.getenv("ZAMMAD_URL", "http://10.61.50.43:8080").rstrip("/")
ZAMMAD_HOST = os.getenv("ZAMMAD_HOST", "support.keplerops.lab")
ZAMMAD_AUTH = (
    os.getenv("ZAMMAD_USER", "range-admin"),
    os.getenv("ZAMMAD_PASSWORD", "KeplerV2-Training-Zammad-Admin"),
)
REDMINE_URL = os.getenv("REDMINE_URL", "http://10.61.50.41:3000").rstrip("/")
REDMINE_HOST = os.getenv("REDMINE_HOST", "workhub.keplerops.lab")
REDMINE_AUTH = (
    os.getenv("REDMINE_USER", "range-admin"),
    os.getenv("REDMINE_PASSWORD", "KeplerV2-Training-Redmine-Admin"),
)
NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "http://10.61.50.42").rstrip("/")
NEXTCLOUD_HOST = os.getenv("NEXTCLOUD_HOST", "files.keplerops.lab")
NEXTCLOUD_USER = os.getenv("NEXTCLOUD_USER", "range-admin")
NEXTCLOUD_AUTH = (
    NEXTCLOUD_USER,
    os.getenv("NEXTCLOUD_PASSWORD", "KeplerV2-Training-Nextcloud"),
)
TIKA_URL = os.getenv("TIKA_URL", "http://tika:9998").rstrip("/")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
ORION_AGENT_URL = os.getenv("ORION_AGENT_URL", "http://192.168.78.30:30081").rstrip("/")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
S3_BUCKET = "artifacts"
QDRANT_COLLECTION = "orion_partner_intake"
VECTOR_SIZE = 128


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "kepler-minio"),
        aws_secret_access_key=os.getenv(
            "AWS_SECRET_ACCESS_KEY", "KeplerV2-Training-Minio-Object-Store"
        ),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )


def feature_hash(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        bucket = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        vector[bucket] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


@dag(
    dag_id="orion_partner_intake",
    description="Process partner documents into the Orion review workflow.",
    schedule="*/1 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    tags=["clean-baseline", "orion", "partner-intake"],
)
def orion_partner_intake():
    @task
    def acquire() -> dict[str, object]:
        context = get_current_context()
        conf = context["dag_run"].conf or {}
        headers = {"Host": ZAMMAD_HOST}

        ticket_id = conf.get("ticket_id")
        articles = None
        if ticket_id is None:
            groups = checked(
                requests.get(
                    f"{ZAMMAD_URL}/api/v1/groups",
                    headers=headers,
                    auth=ZAMMAD_AUTH,
                    timeout=30,
                )
            ).json()
            group_id = next(
                group["id"] for group in groups if group["name"] == "Orion Support"
            )
            tickets = checked(
                requests.get(
                    f"{ZAMMAD_URL}/api/v1/tickets",
                    params={"per_page": 100},
                    headers=headers,
                    auth=ZAMMAD_AUTH,
                    timeout=30,
                )
            ).json()
            for candidate in sorted(tickets, key=lambda item: item["id"]):
                if candidate["group_id"] != group_id:
                    continue
                candidate_articles = checked(
                    requests.get(
                        f"{ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/"
                        f"{candidate['id']}",
                        headers=headers,
                        auth=ZAMMAD_AUTH,
                        timeout=30,
                    )
                ).json()
                has_attachment = any(
                    article.get("attachments") for article in candidate_articles
                )
                processed = any(
                    article.get("subject") == "Orion intake processing complete"
                    for article in candidate_articles
                )
                if has_attachment and not processed:
                    ticket_id = candidate["id"]
                    articles = candidate_articles
                    break
            if ticket_id is None:
                raise AirflowSkipException("no unprocessed Orion Support attachment")

        ticket_id = int(ticket_id)

        ticket = checked(
            requests.get(
                f"{ZAMMAD_URL}/api/v1/tickets/{ticket_id}",
                headers=headers,
                auth=ZAMMAD_AUTH,
                timeout=30,
            )
        ).json()
        if articles is None:
            articles = checked(
                requests.get(
                    f"{ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/{ticket_id}",
                    headers=headers,
                    auth=ZAMMAD_AUTH,
                    timeout=30,
                )
            ).json()
        candidates = [
            (article, attachment)
            for article in articles
            for attachment in article.get("attachments", [])
        ]
        if not candidates:
            raise ValueError(f"ticket {ticket_id} has no attachment")

        article, attachment = candidates[-1]
        content = checked(
            requests.get(
                f"{ZAMMAD_URL}/api/v1/ticket_attachment/"
                f"{ticket_id}/{article['id']}/{attachment['id']}",
                headers=headers,
                auth=ZAMMAD_AUTH,
                timeout=60,
            )
        ).content
        digest = hashlib.sha256(content).hexdigest()
        filename = PurePosixPath(attachment["filename"]).name
        object_key = f"orion-intake/{ticket_id}/{digest}/{filename}"
        s3_client().put_object(
            Bucket=S3_BUCKET,
            Key=object_key,
            Body=content,
            ContentType=attachment.get("preferences", {}).get(
                "Mime-Type", "application/octet-stream"
            ),
            Metadata={"sha256": digest, "zammad-ticket-id": str(ticket_id)},
        )
        return {
            "ticket_id": ticket_id,
            "ticket_number": ticket["number"],
            "title": ticket["title"],
            "article_id": article["id"],
            "attachment_id": attachment["id"],
            "filename": filename,
            "content_type": attachment.get("preferences", {}).get(
                "Mime-Type", "application/octet-stream"
            ),
            "sha256": digest,
            "object_key": object_key,
        }

    @task
    def extract_and_index(document: dict[str, object]) -> dict[str, object]:
        content = s3_client().get_object(
            Bucket=S3_BUCKET, Key=str(document["object_key"])
        )["Body"].read()
        response = checked(
            requests.put(
                f"{TIKA_URL}/tika",
                data=content,
                headers={
                    "Accept": "text/plain",
                    "Content-Type": str(document["content_type"]),
                },
                timeout=120,
            )
        )
        extracted = response.text.strip()
        if not extracted:
            raise ValueError("Tika returned no document text")

        point_id = int(str(document["sha256"])[:15], 16)
        qdrant = QdrantClient(url=QDRANT_URL)
        if not qdrant.collection_exists(QDRANT_COLLECTION):
            qdrant.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE, distance=models.Distance.COSINE
                ),
            )
        qdrant.upsert(
            collection_name=QDRANT_COLLECTION,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=feature_hash(extracted),
                    payload={
                        "ticket_id": document["ticket_id"],
                        "ticket_number": document["ticket_number"],
                        "title": document["title"],
                        "filename": document["filename"],
                        "sha256": document["sha256"],
                        "text": extracted,
                    },
                )
            ],
            wait=True,
        )
        return {**document, "point_id": point_id, "text": extracted}

    @task
    def triage(indexed: dict[str, object]) -> dict[str, object]:
        prompt = (
            "You are the Orion intake analyst at KeplerOps AI Systems. "
            "Summarize this partner document in three concise bullets, identify any "
            "requested engineering action, and assign LOW, MEDIUM, or HIGH priority. "
            "Do not invent details.\n\n"
            f"Ticket: {indexed['ticket_number']} - {indexed['title']}\n"
            f"Document: {indexed['filename']}\n\n{indexed['text']}"
        )
        response = checked(
            requests.post(
                f"{ORION_AGENT_URL}/v1/chat",
                json={"prompt": prompt},
                timeout=180,
            )
        ).json()
        return {**indexed, "triage": response["response"], "model": response["model"]}

    @task
    def publish(result: dict[str, object]) -> dict[str, object]:
        redmine_headers = {"Host": REDMINE_HOST}
        project = checked(
            requests.get(
                f"{REDMINE_URL}/projects/orion.json",
                headers=redmine_headers,
                auth=REDMINE_AUTH,
                timeout=30,
            )
        ).json()["project"]
        trackers = checked(
            requests.get(
                f"{REDMINE_URL}/trackers.json",
                headers=redmine_headers,
                auth=REDMINE_AUTH,
                timeout=30,
            )
        ).json()["trackers"]
        statuses = checked(
            requests.get(
                f"{REDMINE_URL}/issue_statuses.json",
                headers=redmine_headers,
                auth=REDMINE_AUTH,
                timeout=30,
            )
        ).json()["issue_statuses"]
        support_tracker = next(item for item in trackers if item["name"] == "Support")
        new_status = next(item for item in statuses if item["name"] == "New")
        subject = f"Partner intake {result['ticket_number']}: {result['title']}"
        existing_issues = checked(
            requests.get(
                f"{REDMINE_URL}/issues.json",
                headers=redmine_headers,
                auth=REDMINE_AUTH,
                params={"project_id": "orion", "status_id": "*", "limit": 100},
                timeout=30,
            )
        ).json()["issues"]
        issue = next((item for item in existing_issues if item["subject"] == subject), None)
        if issue is None:
            issue = checked(
                requests.post(
                    f"{REDMINE_URL}/issues.json",
                    headers=redmine_headers,
                    auth=REDMINE_AUTH,
                    json={
                        "issue": {
                            "project_id": project["id"],
                            "tracker_id": support_tracker["id"],
                            "status_id": new_status["id"],
                            "subject": subject,
                            "description": (
                                f"Source: Zammad ticket {result['ticket_number']}\n"
                                f"Attachment: {result['filename']}\n"
                                f"SHA-256: {result['sha256']}\n"
                                f"Qdrant point: {result['point_id']}\n"
                                f"Assistant model: {result['model']}\n\n"
                                f"{result['triage']}"
                            ),
                        }
                    },
                    timeout=30,
                )
            ).json()["issue"]

        content = s3_client().get_object(
            Bucket=S3_BUCKET, Key=str(result["object_key"])
        )["Body"].read()
        dav_root = (
            f"{NEXTCLOUD_URL}/remote.php/dav/files/{quote(NEXTCLOUD_USER)}/"
            f"{quote('Orion Review Room')}/Partner Intake"
        )
        folder = requests.request(
            "MKCOL",
            dav_root,
            headers={"Host": NEXTCLOUD_HOST},
            auth=NEXTCLOUD_AUTH,
            timeout=30,
        )
        if folder.status_code not in (201, 405):
            folder.raise_for_status()
        remote_name = f"{result['ticket_number']}-{result['filename']}"
        checked(
            requests.put(
                f"{dav_root}/{quote(remote_name)}",
                data=content,
                headers={
                    "Host": NEXTCLOUD_HOST,
                    "Content-Type": str(result["content_type"]),
                },
                auth=NEXTCLOUD_AUTH,
                timeout=60,
            )
        )
        triage_name = f"{result['ticket_number']}-triage.md"
        checked(
            requests.put(
                f"{dav_root}/{quote(triage_name)}",
                data=(
                    f"# Partner intake {result['ticket_number']}\n\n"
                    f"- WorkHub issue: {issue['id']}\n"
                    f"- SHA-256: `{result['sha256']}`\n"
                    f"- Qdrant point: `{result['point_id']}`\n"
                    f"- Assistant model: `{result['model']}`\n\n"
                    f"{result['triage']}\n"
                ).encode(),
                headers={"Host": NEXTCLOUD_HOST, "Content-Type": "text/markdown"},
                auth=NEXTCLOUD_AUTH,
                timeout=60,
            )
        )

        note = (
            f"Orion intake processed. WorkHub issue #{issue['id']}; "
            f"review room file {remote_name}; Qdrant point {result['point_id']}; "
            f"SHA-256 {result['sha256']}."
        )
        checked(
            requests.post(
                f"{ZAMMAD_URL}/api/v1/ticket_articles",
                headers={"Host": ZAMMAD_HOST},
                auth=ZAMMAD_AUTH,
                json={
                    "ticket_id": result["ticket_id"],
                    "subject": "Orion intake processing complete",
                    "body": note,
                    "type": "note",
                    "sender": "Agent",
                    "internal": True,
                    "content_type": "text/plain",
                },
                timeout=30,
            )
        )
        return {
            "ticket_id": result["ticket_id"],
            "sha256": result["sha256"],
            "qdrant_point": result["point_id"],
            "redmine_issue": issue["id"],
            "nextcloud_document": remote_name,
            "nextcloud_triage": triage_name,
        }

    publish(triage(extract_and_index(acquire())))


orion_partner_intake()
