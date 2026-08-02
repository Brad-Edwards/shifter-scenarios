from __future__ import annotations

import hashlib
import hmac
import math
import os
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
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
ZAMMAD_SUPPORT_AUTH = (
    os.getenv("ZAMMAD_SUPPORT_USER", "support.analyst"),
    os.getenv("ZAMMAD_SUPPORT_PASSWORD", "KeplerV2-Training-Support"),
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
NEXTCLOUD_OWNER_USER = os.getenv("NEXTCLOUD_OWNER_USER", "reviewer")
NEXTCLOUD_OWNER_AUTH = (
    NEXTCLOUD_OWNER_USER,
    os.getenv("NEXTCLOUD_OWNER_PASSWORD", "KeplerV2-Training-Reviewer"),
)
TIKA_URL = os.getenv("TIKA_URL", "http://tika:9998").rstrip("/")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
ORION_AGENT_URL = os.getenv("ORION_AGENT_URL", "http://192.168.78.30:30081").rstrip("/")
ORION_AGENT_API_KEY = os.getenv(
    "ORION_AGENT_API_KEY", "KAI-Orion-Agent-Runtime-8f4c1a7d29e6b053"
)
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://10.61.50.20:8080").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "keplerops")
KEYCLOAK_PARTNER_CLIENT_ID = os.getenv(
    "KEYCLOAK_PARTNER_CLIENT_ID", "orion-partner-intake"
)
KEYCLOAK_PARTNER_CLIENT_SECRET = os.getenv(
    "KEYCLOAK_PARTNER_CLIENT_SECRET",
    "KeplerV2-Training-Partner-Intake-Keycloak",
)
NEXTCLOUD_OIDC_PROVIDER = os.getenv("NEXTCLOUD_OIDC_PROVIDER", "keplerops")
PARTNER_NEXTCLOUD_GROUP = "RG-Nextcloud-Orion-Partner"
PARTNER_WORKHUB_GROUP = "RG-WorkHub-Orion-Partner"
PARTNER_ACCEPTANCE_TAG = "partner-review-accepted"
PARTNER_INITIAL_ACCESS_KEY = os.getenv(
    "PARTNER_INITIAL_ACCESS_KEY", "KeplerV2-Training-Partner-Initial-Access"
)
PARTNER_SMTP_HOST = os.getenv("PARTNER_SMTP_HOST", "10.61.10.20")
PARTNER_SMTP_PORT = int(os.getenv("PARTNER_SMTP_PORT", "587"))
PARTNER_SMTP_USER = os.getenv("PARTNER_SMTP_USER", "partner-intake")
PARTNER_SMTP_PASSWORD = os.getenv("PARTNER_SMTP_PASSWORD", "KeplerV2-Training-Partner")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
S3_BUCKET = "artifacts"
QDRANT_COLLECTION = "orion_partner_intake"
VECTOR_SIZE = 128


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def ocs_data(response: requests.Response):
    payload = checked(response).json()
    if payload.get("ocs", {}).get("meta", {}).get("status") != "ok":
        raise RuntimeError(f"Nextcloud OCS request failed: {payload!r}")
    return payload["ocs"]["data"]


def keycloak_token() -> str:
    response = checked(
        requests.post(
            f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": KEYCLOAK_PARTNER_CLIENT_ID,
                "client_secret": KEYCLOAK_PARTNER_CLIENT_SECRET,
            },
            timeout=30,
        )
    )
    return response.json()["access_token"]


def partner_password(email_address: str) -> str:
    digest = hmac.new(
        PARTNER_INITIAL_ACCESS_KEY.encode(), email_address.encode(), hashlib.sha256
    ).hexdigest()
    return f"Kp!{digest[:20]}"


def partner_organization(email_address: str) -> str:
    domain_label = email_address.rsplit("@", 1)[1].split(".", 1)[0]
    if domain_label.lower() == "cinder":
        return "Cinder Labs"
    return f"{domain_label.replace('-', ' ').title()} Partner"


def partner_identifier(email_address: str) -> str:
    local = email_address.split("@", 1)[0].lower()
    identifier = re.sub(r"[^a-z0-9._-]+", "-", local).strip("-._")
    if not identifier:
        raise ValueError(f"could not derive partner identifier from {email_address}")
    return identifier


def redmine_headers() -> dict[str, str]:
    return {"Host": REDMINE_HOST, "Content-Type": "application/json"}


def nextcloud_headers() -> dict[str, str]:
    return {
        "Host": NEXTCLOUD_HOST,
        "OCS-APIRequest": "true",
        "Accept": "application/json",
    }


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


def ensure_keycloak_partner(partner: dict[str, object]) -> dict[str, object]:
    token = keycloak_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    username = str(partner["partner_username"])
    email_address = str(partner["partner_email"])
    name_parts = str(partner["partner_name"]).split(maxsplit=1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else "Partner"
    users_url = f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/users"
    users = checked(
        requests.get(
            users_url,
            headers=headers,
            params={"username": username, "exact": "true"},
            timeout=30,
        )
    ).json()
    representation = {
        "username": username,
        "enabled": True,
        "email": email_address,
        "emailVerified": False,
        "firstName": first_name,
        "lastName": last_name,
        "requiredActions": ["UPDATE_PASSWORD", "VERIFY_EMAIL"],
        "attributes": {
            "organization": [str(partner["partner_organization"])],
            "relationship": ["Orion partner review"],
        },
    }
    if users:
        user_id = users[0]["id"]
        checked(
            requests.put(
                f"{users_url}/{user_id}",
                headers=headers,
                json=representation,
                timeout=30,
            )
        )
    else:
        checked(
            requests.post(
                users_url,
                headers=headers,
                json=representation,
                timeout=30,
            )
        )
        users = checked(
            requests.get(
                users_url,
                headers=headers,
                params={"username": username, "exact": "true"},
                timeout=30,
            )
        ).json()
        user_id = users[0]["id"]

    checked(
        requests.put(
            f"{users_url}/{user_id}/reset-password",
            headers=headers,
            json={
                "type": "password",
                "value": partner_password(email_address),
                "temporary": True,
            },
            timeout=30,
        )
    )

    desired_groups: dict[str, str] = {}
    for group_name in (PARTNER_NEXTCLOUD_GROUP, PARTNER_WORKHUB_GROUP):
        groups = checked(
            requests.get(
                f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/groups",
                headers=headers,
                params={"search": group_name, "exact": "true"},
                timeout=30,
            )
        ).json()
        group_id = next(group["id"] for group in groups if group["name"] == group_name)
        desired_groups[group_name] = group_id

    memberships_url = f"{users_url}/{user_id}/groups"
    current_groups = checked(
        requests.get(memberships_url, headers=headers, timeout=30)
    ).json()
    for group in current_groups:
        if group["name"] not in desired_groups:
            checked(
                requests.delete(
                    f"{memberships_url}/{group['id']}", headers=headers, timeout=30
                )
            )
    for group_id in desired_groups.values():
        checked(
            requests.put(f"{memberships_url}/{group_id}", headers=headers, timeout=30)
        )

    checked(
        requests.put(
            f"{users_url}/{user_id}/execute-actions-email",
            headers=headers,
            params={"lifespan": 86400},
            json=["UPDATE_PASSWORD", "VERIFY_EMAIL"],
            timeout=30,
        )
    )
    return {
        **partner,
        "keycloak_user_id": user_id,
        "keycloak_groups": sorted(desired_groups),
    }


def ensure_nextcloud_partner(partner: dict[str, object]) -> dict[str, object]:
    headers = nextcloud_headers()
    providers = ocs_data(
        requests.get(
            f"{NEXTCLOUD_URL}/ocs/v2.php/apps/user_oidc/api/v1/provider",
            headers=headers,
            auth=NEXTCLOUD_AUTH,
            params={"format": "json"},
            timeout=30,
        )
    )
    provider_id = next(
        provider["id"]
        for provider in providers
        if provider["identifier"] == NEXTCLOUD_OIDC_PROVIDER
    )
    provisioned = ocs_data(
        requests.post(
            f"{NEXTCLOUD_URL}/ocs/v2.php/apps/user_oidc/api/v1/user",
            headers={**headers, "Content-Type": "application/json"},
            auth=NEXTCLOUD_AUTH,
            params={"format": "json"},
            json={
                "providerId": provider_id,
                "userId": partner["partner_username"],
                "displayName": partner["partner_name"],
                "email": partner["partner_email"],
                "quota": "2 GB",
            },
            timeout=30,
        )
    )
    nextcloud_user_id = provisioned["user_id"]
    organization = str(partner["partner_organization"])
    room_path = f"/Partner Rooms/{organization}"
    dav_base = f"{NEXTCLOUD_URL}/remote.php/dav/files/{quote(NEXTCLOUD_OWNER_USER)}"
    for folder in ("/Partner Rooms", room_path):
        response = requests.request(
            "MKCOL",
            f"{dav_base}{quote(folder, safe='/')}",
            headers={"Host": NEXTCLOUD_HOST},
            auth=NEXTCLOUD_OWNER_AUTH,
            timeout=30,
        )
        if response.status_code not in (201, 405):
            response.raise_for_status()

    shares_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares"
    shares = ocs_data(
        requests.get(
            shares_url,
            headers=headers,
            auth=NEXTCLOUD_OWNER_AUTH,
            params={"format": "json", "reshares": "true"},
            timeout=30,
        )
    )
    matching_share = None
    for share in shares:
        if (
            int(share.get("share_type", -1)) != 0
            or share.get("share_with") != nextcloud_user_id
        ):
            continue
        if share.get("path") == room_path:
            matching_share = share
            continue
        ocs_data(
            requests.delete(
                f"{shares_url}/{share['id']}",
                headers=headers,
                auth=NEXTCLOUD_OWNER_AUTH,
                params={"format": "json"},
                timeout=30,
            )
        )
    if matching_share:
        ocs_data(
            requests.put(
                f"{shares_url}/{matching_share['id']}",
                headers=headers,
                auth=NEXTCLOUD_OWNER_AUTH,
                params={"format": "json"},
                data={"permissions": 15},
                timeout=30,
            )
        )
        share_id = matching_share["id"]
    else:
        created_share = ocs_data(
            requests.post(
                shares_url,
                headers=headers,
                auth=NEXTCLOUD_OWNER_AUTH,
                params={"format": "json"},
                data={
                    "path": room_path,
                    "shareType": 0,
                    "shareWith": nextcloud_user_id,
                    "permissions": 15,
                    "note": "Orion partner review workspace",
                },
                timeout=30,
            )
        )
        share_id = created_share["id"]
    return {
        **partner,
        "nextcloud_user_id": nextcloud_user_id,
        "nextcloud_room": room_path,
        "nextcloud_share_id": share_id,
    }


def ensure_workhub_partner(partner: dict[str, object]) -> dict[str, object]:
    headers = redmine_headers()
    email_address = str(partner["partner_email"])
    username = str(partner["partner_username"])
    name_parts = str(partner["partner_name"]).split(maxsplit=1)
    user_payload = {
        "user": {
            "login": username,
            "firstname": name_parts[0],
            "lastname": name_parts[1] if len(name_parts) > 1 else "Partner",
            "mail": email_address,
            "password": partner_password(email_address),
            "must_change_passwd": True,
            "mail_notification": "only_my_events",
        },
        "send_information": False,
    }
    users = checked(
        requests.get(
            f"{REDMINE_URL}/users.json",
            headers=headers,
            auth=REDMINE_AUTH,
            params={"name": email_address, "status": ""},
            timeout=30,
        )
    ).json()["users"]
    exact_user = next(
        (user for user in users if user.get("mail") == email_address), None
    )
    if exact_user:
        redmine_user_id = exact_user["id"]
        checked(
            requests.put(
                f"{REDMINE_URL}/users/{redmine_user_id}.json",
                headers=headers,
                auth=REDMINE_AUTH,
                json=user_payload,
                timeout=30,
            )
        )
    else:
        created_user = checked(
            requests.post(
                f"{REDMINE_URL}/users.json",
                headers=headers,
                auth=REDMINE_AUTH,
                json=user_payload,
                timeout=30,
            )
        ).json()["user"]
        redmine_user_id = created_user["id"]

    project_identifier = re.sub(
        r"[^a-z0-9-]+",
        "-",
        f"partner-{str(partner['partner_organization']).lower().replace(' ', '-')}",
    ).strip("-")
    project_name = f"{partner['partner_organization']} Partner Review"
    project_url = f"{REDMINE_URL}/projects/{project_identifier}.json"
    project_response = requests.get(
        project_url, headers=headers, auth=REDMINE_AUTH, timeout=30
    )
    orion_project = checked(
        requests.get(
            f"{REDMINE_URL}/projects/orion.json",
            headers=headers,
            auth=REDMINE_AUTH,
            timeout=30,
        )
    ).json()["project"]
    trackers = checked(
        requests.get(
            f"{REDMINE_URL}/trackers.json",
            headers=headers,
            auth=REDMINE_AUTH,
            timeout=30,
        )
    ).json()["trackers"]
    support_tracker = next(item for item in trackers if item["name"] == "Support")
    project_payload = {
        "project": {
            "name": project_name,
            "identifier": project_identifier,
            "description": (
                f"Private collaboration space for {partner['partner_organization']} "
                "and the Orion review team."
            ),
            "is_public": False,
            "parent_id": orion_project["id"],
            "inherit_members": False,
            "tracker_ids": [support_tracker["id"]],
            "enabled_module_names": [
                "issue_tracking",
                "documents",
                "files",
                "wiki",
            ],
        }
    }
    if project_response.status_code == 404:
        project = checked(
            requests.post(
                f"{REDMINE_URL}/projects.json",
                headers=headers,
                auth=REDMINE_AUTH,
                json=project_payload,
                timeout=30,
            )
        ).json()["project"]
    else:
        project = checked(project_response).json()["project"]
        checked(
            requests.put(
                project_url,
                headers=headers,
                auth=REDMINE_AUTH,
                json=project_payload,
                timeout=30,
            )
        )

    roles = checked(
        requests.get(
            f"{REDMINE_URL}/roles.json",
            headers=headers,
            auth=REDMINE_AUTH,
            timeout=30,
        )
    ).json()["roles"]
    reporter_role = next(role for role in roles if role["name"] == "Reporter")
    user_detail = checked(
        requests.get(
            f"{REDMINE_URL}/users/{redmine_user_id}.json",
            headers=headers,
            auth=REDMINE_AUTH,
            params={"include": "memberships"},
            timeout=30,
        )
    ).json()["user"]
    target_membership = None
    for membership in user_detail.get("memberships", []):
        if membership["project"]["id"] == project["id"]:
            target_membership = membership
            continue
        checked(
            requests.delete(
                f"{REDMINE_URL}/memberships/{membership['id']}.json",
                headers=headers,
                auth=REDMINE_AUTH,
                timeout=30,
            )
        )
    membership_payload = {"membership": {"role_ids": [reporter_role["id"]]}}
    if target_membership:
        checked(
            requests.put(
                f"{REDMINE_URL}/memberships/{target_membership['id']}.json",
                headers=headers,
                auth=REDMINE_AUTH,
                json=membership_payload,
                timeout=30,
            )
        )
        membership_id = target_membership["id"]
    else:
        membership_payload["membership"]["user_id"] = redmine_user_id
        membership = checked(
            requests.post(
                f"{REDMINE_URL}/projects/{project_identifier}/memberships.json",
                headers=headers,
                auth=REDMINE_AUTH,
                json=membership_payload,
                timeout=30,
            )
        ).json()["membership"]
        membership_id = membership["id"]

    support_users = checked(
        requests.get(
            f"{REDMINE_URL}/users.json",
            headers=headers,
            auth=REDMINE_AUTH,
            params={"name": "support@keplerops.lab", "status": ""},
            timeout=30,
        )
    ).json()["users"]
    support_user = next(
        user for user in support_users if user.get("mail") == "support@keplerops.lab"
    )
    project_memberships = checked(
        requests.get(
            f"{REDMINE_URL}/projects/{project_identifier}/memberships.json",
            headers=headers,
            auth=REDMINE_AUTH,
            params={"limit": 100},
            timeout=30,
        )
    ).json()["memberships"]
    support_membership = next(
        (
            membership
            for membership in project_memberships
            if membership.get("user", {}).get("id") == support_user["id"]
        ),
        None,
    )
    support_payload = {"membership": {"role_ids": [reporter_role["id"]]}}
    if support_membership:
        checked(
            requests.put(
                f"{REDMINE_URL}/memberships/{support_membership['id']}.json",
                headers=headers,
                auth=REDMINE_AUTH,
                json=support_payload,
                timeout=30,
            )
        )
    else:
        support_payload["membership"]["user_id"] = support_user["id"]
        checked(
            requests.post(
                f"{REDMINE_URL}/projects/{project_identifier}/memberships.json",
                headers=headers,
                auth=REDMINE_AUTH,
                json=support_payload,
                timeout=30,
            )
        )
    return {
        **partner,
        "redmine_user_id": redmine_user_id,
        "redmine_project_id": project["id"],
        "redmine_project_identifier": project_identifier,
        "redmine_membership_id": membership_id,
    }


def send_partner_welcome(partner: dict[str, object]) -> None:
    message = EmailMessage()
    message["From"] = "partner-intake@keplerops.lab"
    message["To"] = str(partner["partner_email"])
    message["Subject"] = f"{partner['partner_organization']} Orion access approved"
    message.set_content(
        "Your Orion partner review access is ready.\n\n"
        "Use the account-action email from KeplerOps identity to set your "
        "single sign-on password.\n"
        "Files: https://files.keplerops.lab\n"
        f"WorkHub: https://workhub.keplerops.lab/projects/"
        f"{partner['redmine_project_identifier']}\n"
        f"WorkHub user: {partner['partner_username']}\n"
        f"Temporary WorkHub password: {partner_password(str(partner['partner_email']))}\n"
        "WorkHub will require a new password at first sign-in.\n"
    )
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with smtplib.SMTP(PARTNER_SMTP_HOST, PARTNER_SMTP_PORT, timeout=30) as smtp:
        smtp.starttls(context=context)
        smtp.login(PARTNER_SMTP_USER, PARTNER_SMTP_PASSWORD)
        smtp.send_message(message)


@dag(
    dag_id="orion_partner_intake",
    description="Process partner documents into the Orion review workflow.",
    schedule="*/1 * * * *",
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    is_paused_upon_creation=False,
    max_active_runs=1,
    tags=["operations", "orion", "partner-intake"],
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
            for candidate in sorted(tickets, key=lambda item: item["id"], reverse=True):
                if candidate["group_id"] != group_id:
                    continue
                tags = checked(
                    requests.get(
                        f"{ZAMMAD_URL}/api/v1/tags",
                        params={"object": "Ticket", "o_id": candidate["id"]},
                        headers=headers,
                        auth=ZAMMAD_AUTH,
                        timeout=30,
                    )
                ).json()["tags"]
                if PARTNER_ACCEPTANCE_TAG not in tags:
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
        customer = checked(
            requests.get(
                f"{ZAMMAD_URL}/api/v1/users/{ticket['customer_id']}",
                headers=headers,
                auth=ZAMMAD_AUTH,
                timeout=30,
            )
        ).json()
        partner_email = customer["email"].strip().lower()
        if partner_email.endswith("@keplerops.lab"):
            raise ValueError("partner intake requires an external customer identity")
        display_name = " ".join(
            value.strip()
            for value in (customer.get("firstname", ""), customer.get("lastname", ""))
            if value and value.strip()
        )
        if not display_name:
            display_name = parseaddr(customer.get("email", ""))[0] or partner_email
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
        object_key = (
            f"orion-intake/{partner_identifier(partner_email)}/{digest}/{filename}"
        )
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
            "source_uri": (
                f"zammad://tickets/{ticket['number']}/articles/{article['id']}"
                f"/attachments/{attachment['id']}"
            ),
            "partner_email": partner_email,
            "partner_name": display_name,
            "partner_username": partner_identifier(partner_email),
            "partner_organization": partner_organization(partner_email),
        }

    @task
    def extract_and_index(document: dict[str, object]) -> dict[str, object]:
        content = (
            s3_client()
            .get_object(Bucket=S3_BUCKET, Key=str(document["object_key"]))["Body"]
            .read()
        )
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
                        "source_uri": document["source_uri"],
                        "citation": {
                            "source": document["source_uri"],
                            "title": document["title"],
                            "filename": document["filename"],
                            "sha256": document["sha256"],
                        },
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
                headers={"Authorization": f"Bearer {ORION_AGENT_API_KEY}"},
                timeout=180,
            )
        ).json()
        return {**indexed, "triage": response["response"], "model": response["model"]}

    @task
    def provision_partner_access(result: dict[str, object]) -> dict[str, object]:
        provisioned = ensure_keycloak_partner(result)
        provisioned = ensure_nextcloud_partner(provisioned)
        provisioned = ensure_workhub_partner(provisioned)
        send_partner_welcome(provisioned)
        return provisioned

    @task
    def publish(result: dict[str, object]) -> dict[str, object]:
        redmine_headers = {
            "Host": REDMINE_HOST,
            "X-Redmine-Switch-User": "support.analyst",
        }
        project = checked(
            requests.get(
                f"{REDMINE_URL}/projects/{result['redmine_project_identifier']}.json",
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
        subject = f"{result['partner_organization']} Orion integration profile"
        existing_issues = checked(
            requests.get(
                f"{REDMINE_URL}/issues.json",
                headers=redmine_headers,
                auth=REDMINE_AUTH,
                params={
                    "project_id": result["redmine_project_identifier"],
                    "status_id": "*",
                    "limit": 100,
                },
                timeout=30,
            )
        ).json()["issues"]
        issue = next(
            (item for item in existing_issues if item["subject"] == subject), None
        )
        issue_payload = {
            "issue": {
                "project_id": project["id"],
                "tracker_id": support_tracker["id"],
                "status_id": new_status["id"],
                "subject": subject,
                "description": (
                    f"Source: Zammad ticket {result['ticket_number']}\n"
                    f"Attachment: {result['filename']}\n"
                    f"SHA-256: {result['sha256']}\n"
                    f"Citation: {result['source_uri']}\n"
                    f"Assistant model: {result['model']}\n\n"
                    f"{result['triage']}"
                ),
            }
        }
        if issue is None:
            issue = checked(
                requests.post(
                    f"{REDMINE_URL}/issues.json",
                    headers=redmine_headers,
                    auth=REDMINE_AUTH,
                    json=issue_payload,
                    timeout=30,
                )
            ).json()["issue"]
        else:
            checked(
                requests.put(
                    f"{REDMINE_URL}/issues/{issue['id']}.json",
                    headers=redmine_headers,
                    auth=REDMINE_AUTH,
                    json=issue_payload,
                    timeout=30,
                )
            )

        content = (
            s3_client()
            .get_object(Bucket=S3_BUCKET, Key=str(result["object_key"]))["Body"]
            .read()
        )
        dav_root = (
            f"{NEXTCLOUD_URL}/remote.php/dav/files/{quote(NEXTCLOUD_OWNER_USER)}/"
            f"{quote(str(result['nextcloud_room']).lstrip('/'), safe='/')}"
        )
        folder = requests.request(
            "MKCOL",
            dav_root,
            headers={"Host": NEXTCLOUD_HOST},
            auth=NEXTCLOUD_OWNER_AUTH,
            timeout=30,
        )
        if folder.status_code not in (201, 405):
            folder.raise_for_status()
        remote_name = str(result["filename"])
        checked(
            requests.put(
                f"{dav_root}/{quote(remote_name)}",
                data=content,
                headers={
                    "Host": NEXTCLOUD_HOST,
                    "Content-Type": str(result["content_type"]),
                },
                auth=NEXTCLOUD_OWNER_AUTH,
                timeout=60,
            )
        )
        triage_name = "orion-intake-summary.md"
        checked(
            requests.put(
                f"{dav_root}/{quote(triage_name)}",
                data=(
                    f"# {result['partner_organization']} Orion intake\n\n"
                    f"- WorkHub issue: {issue['id']}\n"
                    f"- SHA-256: `{result['sha256']}`\n"
                    f"- Citation: `{result['source_uri']}`\n"
                    f"- Assistant model: `{result['model']}`\n\n"
                    f"{result['triage']}\n"
                ).encode(),
                headers={"Host": NEXTCLOUD_HOST, "Content-Type": "text/markdown"},
                auth=NEXTCLOUD_OWNER_AUTH,
                timeout=60,
            )
        )

        note = (
            f"Orion partner access provisioned. WorkHub project "
            f"{result['redmine_project_identifier']} and issue #{issue['id']}; "
            f"Nextcloud room {result['nextcloud_room']}; "
            f"Qdrant citation {result['source_uri']}; "
            f"SHA-256 {result['sha256']}."
        )
        checked(
            requests.post(
                f"{ZAMMAD_URL}/api/v1/ticket_articles",
                headers={"Host": ZAMMAD_HOST},
                auth=ZAMMAD_SUPPORT_AUTH,
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
        ticket_states = checked(
            requests.get(
                f"{ZAMMAD_URL}/api/v1/ticket_states",
                headers={"Host": ZAMMAD_HOST},
                auth=ZAMMAD_SUPPORT_AUTH,
                timeout=30,
            )
        ).json()
        closed_state = next(
            state for state in ticket_states if state["name"] == "closed"
        )
        checked(
            requests.put(
                f"{ZAMMAD_URL}/api/v1/tickets/{result['ticket_id']}",
                headers={"Host": ZAMMAD_HOST},
                auth=ZAMMAD_SUPPORT_AUTH,
                json={"state_id": closed_state["id"]},
                timeout=30,
            )
        )
        return {
            "ticket_id": result["ticket_id"],
            "sha256": result["sha256"],
            "qdrant_point": result["point_id"],
            "redmine_issue": issue["id"],
            "redmine_project": result["redmine_project_identifier"],
            "nextcloud_document": remote_name,
            "nextcloud_triage": triage_name,
            "nextcloud_room": result["nextcloud_room"],
            "partner_username": result["partner_username"],
        }

    publish(provision_partner_access(triage(extract_and_index(acquire()))))


orion_partner_intake()
