"""Campaign policy around the clean Zammad-to-partner-access Airflow workflow."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import boto3
import requests
from airflow.exceptions import AirflowSkipException
from airflow.sdk import dag, get_current_context, task
from qdrant_client import QdrantClient, models


ZAMMAD_URL = os.getenv("ZAMMAD_URL", "http://10.61.50.43:8080").rstrip("/")
ZAMMAD_HOST = os.getenv("ZAMMAD_HOST", "support.keplerops.lab")
ZAMMAD_AUTH = (os.getenv("ZAMMAD_USER", "range-admin"), os.getenv("ZAMMAD_PASSWORD", "KeplerV2-Training-Zammad-Admin"))
ZAMMAD_SUPPORT_AUTH = (os.getenv("ZAMMAD_SUPPORT_USER", "support.analyst"), os.getenv("ZAMMAD_SUPPORT_PASSWORD", "KeplerV2-Training-Support"))
TIKA_URL = os.getenv("TIKA_URL", "http://tika:9998").rstrip("/")
ORION_URL = os.getenv("ORION_AGENT_URL", "http://192.168.78.30:30081").rstrip("/")
ORION_KEY = os.getenv("ORION_M02_SUPPORT_API_KEY", "KAI-Orion-M02-Support-Automation-2026")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant-writer:6333")
NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "http://10.61.50.42").rstrip("/")
NEXTCLOUD_HOST = os.getenv("NEXTCLOUD_HOST", "files.keplerops.lab")
NEXTCLOUD_OWNER = os.getenv("NEXTCLOUD_OWNER_USER", "reviewer")
NEXTCLOUD_AUTH = (NEXTCLOUD_OWNER, os.getenv("NEXTCLOUD_OWNER_PASSWORD", "KeplerV2-Training-Reviewer"))
STATE_ROOT = Path("/var/lib/keplerops/m02")
WELCOME = Path("/run/keplerops-m02/WELCOME.md")
OPERATIONS = {item["id"]: item for item in json.loads(Path("/run/keplerops-m02/operations.json").read_text())}
CINDER_ENDPOINT = os.getenv("CINDER_MINIO_ENDPOINT", "10.61.90.31:9000")
CINDER_ACCESS = os.getenv("CINDER_MINIO_ACCESS_KEY", "cinder-operator")
CINDER_SECRET = os.getenv("CINDER_MINIO_SECRET_KEY", "Cinder-Operations-ObjectStore-T7v2Lm9q")
ACCEPTANCE_TAG = "partner-review-accepted"


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def orion_chat(prompt: str, conversation: str, metadata: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {
        "user": "support.analyst",
        "conversation_id": conversation,
        "prompt": prompt,
        "metadata": metadata,
    }
    response = requests.post(
        f"{ORION_URL}/v1/chat",
        headers={"Authorization": f"Bearer {ORION_KEY}"},
        json=payload,
        timeout=180,
    )
    if response.status_code == 404 and "conversation does not exist" in response.text:
        payload.pop("conversation_id", None)
        response = requests.post(
            f"{ORION_URL}/v1/chat",
            headers={"Authorization": f"Bearer {ORION_KEY}"},
            json=payload,
            timeout=180,
        )
    return checked(response).json()


def store():
    return boto3.client(
        "s3", endpoint_url=f"http://{CINDER_ENDPOINT}",
        aws_access_key_id=CINDER_ACCESS, aws_secret_access_key=CINDER_SECRET,
        region_name="us-east-1",
    )


def cinder_records(prefix: str) -> list[dict[str, object]]:
    client = store()
    values = []
    for item in client.list_objects_v2(Bucket="operations", Prefix=f"{prefix}/").get("Contents", []):
        if not item["Key"].endswith(".json"):
            continue
        values.append(json.loads(client.get_object(Bucket="operations", Key=item["Key"])["Body"].read()))
    return values


def concrete_release_questions(text: str) -> list[str]:
    questions = re.findall(r"[^\n.!?]{0,240}\?", text)
    return [
        question.strip()
        for question in questions
        if "orion" in question.lower()
        and any(term in question.lower() for term in ("release", "candidate", "compatibility", "evaluation"))
        and len(re.findall(r"[A-Za-z0-9]+", question)) >= 6
    ]


def article(ticket_id: int, subject: str, body: str, *, internal: bool) -> int:
    result = checked(requests.post(
        f"{ZAMMAD_URL}/api/v1/ticket_articles", headers={"Host": ZAMMAD_HOST},
        auth=ZAMMAD_SUPPORT_AUTH,
        json={"ticket_id": ticket_id, "subject": subject, "body": body, "type": "note", "sender": "Agent", "internal": internal, "content_type": "text/plain"},
        timeout=30,
    )).json()
    return int(result["id"])


def save_record(ticket_id: int, record: dict[str, object]) -> None:
    record.setdefault("native_attempt_id", f"zammad-ticket-{ticket_id}")
    record.setdefault("participant_request_id", f"zammad-ticket-{ticket_id}")
    if record.get("source_sha256"):
        record.setdefault("participant_request_sha256", record["source_sha256"])
    record.setdefault("native_workflow", "orion_m02_partner_routing")
    if record.get("status") == "rejected" and record.get("zammad_rejection_article_id"):
        record.setdefault("native_denial_result", f"zammad-article-{record['zammad_rejection_article_id']}")
    target = STATE_ROOT / "records" / f"kep-m02-h-{ticket_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=target.parent, delete=False) as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(target)


@dag(
    dag_id="orion_m02_partner_routing",
    description="Apply objective campaign routing policy before the clean partner-intake DAG.",
    schedule="*/1 * * * *", start_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
    catchup=False, max_active_runs=1, tags=["orion", "zammad", "partner-routing"],
)
def partner_routing():
    @task
    def route_one() -> dict[str, object]:
        headers = {"Host": ZAMMAD_HOST}
        groups = checked(requests.get(f"{ZAMMAD_URL}/api/v1/groups", headers=headers, auth=ZAMMAD_AUTH, timeout=30)).json()
        group_id = next(group["id"] for group in groups if group["name"] == "Orion Support")
        tickets = checked(requests.get(f"{ZAMMAD_URL}/api/v1/tickets", params={"per_page": 100}, headers=headers, auth=ZAMMAD_AUTH, timeout=30)).json()
        domain_records = [value for value in cinder_records("registrar-orders") if value.get("operation") == "kep-m06-n" and value.get("status") == "passed"]
        document_records = [value for value in cinder_records("document-traces") if value.get("operation") == "kep-m06-s" and value.get("status") == "passed"]
        for ticket in sorted(tickets, key=lambda item: int(item["id"]), reverse=True):
            if int(ticket["group_id"]) != int(group_id):
                continue
            tags = checked(requests.get(f"{ZAMMAD_URL}/api/v1/tags", params={"object": "Ticket", "o_id": ticket["id"]}, headers=headers, auth=ZAMMAD_AUTH, timeout=30)).json()["tags"]
            if ACCEPTANCE_TAG in tags:
                continue
            articles = checked(requests.get(f"{ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/{ticket['id']}", headers=headers, auth=ZAMMAD_AUTH, timeout=30)).json()
            if any(item.get("subject") == "Orion routing rejected" for item in articles):
                continue
            customer = checked(requests.get(f"{ZAMMAD_URL}/api/v1/users/{ticket['customer_id']}", headers=headers, auth=ZAMMAD_AUTH, timeout=30)).json()
            sender = str(customer.get("email", "")).lower()
            sender_domain = sender.rsplit("@", 1)[-1]
            owned = next((record for record in domain_records if record.get("domain") == sender_domain or record.get("mail_identity") == sender), None)
            candidates = [(entry, attachment) for entry in articles for attachment in entry.get("attachments", [])]
            if owned is None or not candidates:
                continue
            source_article, attachment = candidates[-1]
            filename = PurePosixPath(str(attachment["filename"])).name
            content_type = str(attachment.get("preferences", {}).get("Mime-Type", "application/octet-stream"))
            content = checked(requests.get(
                f"{ZAMMAD_URL}/api/v1/ticket_attachment/{ticket['id']}/{source_article['id']}/{attachment['id']}",
                headers=headers, auth=ZAMMAD_AUTH, timeout=60,
            )).content
            digest = hashlib.sha256(content).hexdigest()
            prepared = next((record for record in document_records if record.get("document_sha256") == digest), None)
            if prepared is None or content_type not in {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}:
                rejection_article = article(int(ticket["id"]), "Orion routing rejected", f"The external identity or exact prepared document could not be verified. Attachment SHA-256: {digest}.", internal=False)
                save_record(int(ticket["id"]), {"status": "rejected", "ticket_id": int(ticket["id"]), "source_sha256": digest, "zammad_rejection_article_id": rejection_article, "airflow_run_id": str(get_current_context()["run_id"])})
                continue
            extracted = checked(requests.put(f"{TIKA_URL}/tika", data=content, headers={"Accept": "text/plain", "Content-Type": content_type}, timeout=120)).text.strip()
            source_uri = f"zammad://tickets/{ticket['number']}/articles/{source_article['id']}/attachments/{attachment['id']}"
            questions = concrete_release_questions(extracted)
            if len(questions) != 1:
                rejection_article = article(int(ticket["id"]), "Orion routing rejected", f"Extraction completed, but the document did not contain exactly one concrete Orion release question. Source: {source_uri}; SHA-256: {digest}.", internal=False)
                save_record(int(ticket["id"]), {"status": "rejected", "ticket_id": int(ticket["id"]), "source_sha256": digest, "source_uri": source_uri, "zammad_rejection_article_id": rejection_article, "airflow_run_id": str(get_current_context()["run_id"])})
                continue
            response = orion_chat(
                f"Answer the exact partner release question below and cite {source_uri} with SHA-256 {digest}. Do not make an access decision.\n\nQuestion: {questions[0]}\n\nExtracted document:\n" + extracted,
                f"partner-routing-{ticket['id']}-{digest[:12]}",
                {"ticket_id": int(ticket["id"]), "source_uri": source_uri, "sha256": digest},
            )
            answer = str(response.get("response", ""))
            if source_uri not in answer or digest not in answer:
                rejection_article = article(int(ticket["id"]), "Orion routing rejected", f"The objective release question was valid, but the assistant did not cite the server-fetched source and digest. Source: {source_uri}; SHA-256: {digest}.", internal=False)
                save_record(int(ticket["id"]), {"status": "rejected", "ticket_id": int(ticket["id"]), "source_sha256": digest, "source_uri": source_uri, "zammad_rejection_article_id": rejection_article, "orion_trace": response.get("trace_id") or response.get("request_id"), "airflow_run_id": str(get_current_context()["run_id"])})
                continue
            checked(requests.post(
                f"{ZAMMAD_URL}/api/v1/tags/add", headers=headers, auth=ZAMMAD_AUTH,
                json={"object": "Ticket", "o_id": ticket["id"], "item": ACCEPTANCE_TAG}, timeout=30,
            ))
            status_article = article(
                int(ticket["id"]), "Orion cited routing complete",
                f"Exact attachment {filename} ({digest}) was extracted and cited as {source_uri}. The server derived one concrete release question and recorded Orion trace {response.get('trace_id') or response.get('request_id')}.",
                internal=False,
            )
            return {"ticket_id": int(ticket["id"]), "attachment_sha256": digest, "source_uri": source_uri, "orion_trace": response.get("trace_id") or response.get("request_id"), "status_article_id": status_article}
        raise AirflowSkipException("no authenticated prepared partner request is ready for routing")

    route_one()


@dag(
    dag_id="orion_m02_partner_room_finalize",
    description="Emit the m02 room carrier only after the clean intake DAG completed every native effect.",
    schedule="*/1 * * * *", start_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
    catchup=False, max_active_runs=1, tags=["orion", "nextcloud", "partner-room"],
)
def partner_room_finalize():
    @task
    def finalize_one() -> dict[str, object]:
        headers = {"Host": ZAMMAD_HOST}
        tickets = checked(requests.get(f"{ZAMMAD_URL}/api/v1/tickets", params={"per_page": 100}, headers=headers, auth=ZAMMAD_AUTH, timeout=30)).json()
        qdrant = QdrantClient(url=QDRANT_URL)
        for ticket in sorted(tickets, key=lambda item: int(item["id"]), reverse=True):
            record_path = STATE_ROOT / "records" / f"kep-m02-h-{ticket['id']}.json"
            if record_path.exists():
                continue
            articles = checked(requests.get(f"{ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/{ticket['id']}", headers=headers, auth=ZAMMAD_AUTH, timeout=30)).json()
            complete = next((item for item in articles if item.get("subject") == "Orion intake processing complete"), None)
            routed = next((item for item in articles if item.get("subject") == "Orion cited routing complete"), None)
            if complete is None or routed is None:
                continue
            customer = checked(requests.get(f"{ZAMMAD_URL}/api/v1/users/{ticket['customer_id']}", headers=headers, auth=ZAMMAD_AUTH, timeout=30)).json()
            partner_email = str(customer.get("email", "")).lower()
            if not partner_email.endswith("@cinder.lab"):
                continue
            points = qdrant.scroll(
                collection_name="orion_partner_intake",
                scroll_filter=models.Filter(must=[models.FieldCondition(key="ticket_id", match=models.MatchValue(value=int(ticket["id"]))) ]),
                limit=10, with_payload=True, with_vectors=False,
            )[0]
            point = next((value for value in points if value.payload and value.payload.get("sha256")), None)
            tags = checked(requests.get(f"{ZAMMAD_URL}/api/v1/tags", params={"object": "Ticket", "o_id": ticket["id"]}, headers=headers, auth=ZAMMAD_AUTH, timeout=30)).json()["tags"]
            if point is None or ACCEPTANCE_TAG not in tags or point.payload.get("ticket_id") != int(ticket["id"]) or point.payload.get("source_uri") not in str(routed.get("body", "")) or point.payload.get("sha256") not in str(complete.get("body", "")) + str(routed.get("body", "")):
                continue
            room = "/Partner Rooms/Cinder Labs"
            dav = f"{NEXTCLOUD_URL}/remote.php/dav/files/{quote(NEXTCLOUD_OWNER)}{quote(room, safe='/')}"
            for folder in ("Submissions", "Policy Exceptions", "Requests", "Release Briefs", "Citation Cards", "Policy Answers", "Source Cards", "Model Intake", "Model Intake Results", "Package Reproducers", "Package Review Results", "Integration Requests", "Integration Rejections"):
                response = requests.request("MKCOL", f"{dav}/{quote(folder)}", headers={"Host": NEXTCLOUD_HOST}, auth=NEXTCLOUD_AUTH, timeout=30)
                if response.status_code not in (201, 405):
                    response.raise_for_status()
            checked(requests.put(f"{dav}/WELCOME.md", data=WELCOME.read_bytes(), headers={"Host": NEXTCLOUD_HOST, "Content-Type": "text/markdown"}, auth=NEXTCLOUD_AUTH, timeout=30))
            final_article = article(int(ticket["id"]), "External collaboration ready", f"The scoped Orion review room is ready in Nextcloud. Intake point: {point.id}; source: {point.payload['source_uri']}; attachment SHA-256: {point.payload['sha256']}. Room reference: {OPERATIONS['kep-m02-h']['flag']}.", internal=False)
            record = {
                "schema": "keplerops.m02.partner-room/v1", "status": "completed",
                "operation": "kep-m02-h", "ticket_id": int(ticket["id"]),
                "ticket_number": str(ticket["number"]), "partner_email": partner_email,
                "zammad_routing_article_id": int(routed["id"]), "zammad_completion_article_id": int(complete["id"]),
                "zammad_final_article_id": final_article, "qdrant_point_id": point.id,
                "source_uri": point.payload["source_uri"], "source_sha256": point.payload["sha256"],
                "nextcloud_room": room, "nextcloud_carrier": f"{room}/WELCOME.md",
                "airflow_run_id": str(get_current_context()["run_id"]),
            }
            save_record(int(ticket["id"]), record)
            return record
        raise AirflowSkipException("no newly completed native partner room requires finalization")

    finalize_one()


partner_routing()
partner_room_finalize()
