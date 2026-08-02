from __future__ import annotations

import hashlib
import json
import math
import re
import smtplib
import ssl
import xmlrpc.client
import uuid
from contextlib import contextmanager
from http.cookies import SimpleCookie
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

import boto3
import httpx
from botocore.config import Config

from .config import Settings


class NativeServiceError(RuntimeError):
    pass


def checked(response: httpx.Response) -> httpx.Response:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = response.text[:1000]
        raise NativeServiceError(
            f"{response.request.method} {response.request.url} returned "
            f"{response.status_code}: {body}"
        ) from exc
    return response


def response_ids(response: httpx.Response, fallback: str) -> list[str]:
    values = [
        response.headers.get("x-request-id"),
        response.headers.get("x-correlation-id"),
        response.headers.get("location"),
    ]
    found = [value for value in values if value]
    return found or [fallback]


def feature_vector(text: str, size: int = 16) -> list[float]:
    vector = [0.0] * size
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        bucket = int.from_bytes(digest[:4], "big") % size
        vector[bucket] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def correlation_headers(request_id: str, trace_id: str) -> dict[str, str]:
    w3c_trace_id = hashlib.sha256(trace_id.encode()).hexdigest()[:32]
    parent_id = hashlib.sha256(f"{trace_id}:{request_id}".encode()).hexdigest()[:16]
    return {
        "X-Request-ID": request_id,
        "X-Keplerops-Trace-ID": trace_id,
        "traceparent": f"00-{w3c_trace_id}-{parent_id}-01",
    }


class NativeClients:
    def __init__(self, settings: Settings):
        self.settings = settings
        Path(settings.evidence_directory).mkdir(parents=True, exist_ok=True)

    def opa_decide(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = checked(
            httpx.post(
                f"{self.settings.opa_url}/v1/data/keplerops/business/decision",
                json={"input": payload},
                timeout=15,
            )
        )
        result = response.json().get("result")
        if not isinstance(result, dict) or result.get("allow") is not True:
            raise PermissionError("OPA denied the bounded business action")
        return result

    def release_risk_predict(
        self, text: str, request_id: str, trace_id: str
    ) -> dict[str, Any]:
        base = self.settings.release_risk_url.rstrip("/")
        model = self.settings.release_risk_model
        headers = correlation_headers(request_id, trace_id)
        try:
            metadata = checked(
                httpx.get(f"{base}/v1/models/{model}", headers=headers, timeout=20)
            ).json()
            response = checked(
                httpx.post(
                    f"{base}/v1/models/{model}:predict",
                    headers=headers,
                    json={"instances": [{"text": text}]},
                    timeout=60,
                )
            )
        except httpx.HTTPError as exc:
            raise NativeServiceError("Orion Release Risk is unavailable") from exc
        body = response.json()
        predictions = body.get("predictions")
        labels = metadata.get("labels")
        if not isinstance(predictions, list) or len(predictions) != 1:
            raise NativeServiceError("Orion Release Risk returned no single prediction")
        prediction = predictions[0]
        if not isinstance(prediction, dict) or not isinstance(labels, list):
            raise NativeServiceError("Orion Release Risk returned malformed metadata")
        probabilities = prediction.get("probabilities")
        class_index = prediction.get("class_index")
        label = prediction.get("label")
        if (
            not isinstance(probabilities, list)
            or len(probabilities) != len(labels)
            or not isinstance(class_index, int)
            or class_index < 0
            or class_index >= len(labels)
            or labels[class_index] != label
        ):
            raise NativeServiceError(
                "Orion Release Risk returned an invalid class vector"
            )
        model_sha256 = str(
            body.get("model_sha256") or metadata.get("model_sha256") or ""
        )
        if model_sha256 != self.settings.release_risk_model_digest.removeprefix(
            "sha256:"
        ):
            raise NativeServiceError(
                "Orion Release Risk does not match the active signed model digest"
            )
        return {
            "model": str(body.get("model_name") or metadata.get("name") or model),
            "model_version": f"release-{body.get('model_version', 'active')}",
            "inference_id": f"risk-{uuid.uuid4().hex}",
            "label": str(label),
            "class_index": class_index,
            "probabilities": [float(value) for value in probabilities],
            "model_sha256": model_sha256,
            "raw_digest": "sha256:"
            + hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }

    def assistant_infer(
        self,
        prompt: str,
        actor: str,
        conversation_id: str,
        request_id: str,
        trace_id: str,
    ) -> dict[str, Any]:
        headers = {
            **correlation_headers(request_id, trace_id),
            "Authorization": f"Bearer {self.settings.assistant_api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = checked(
                httpx.post(
                    f"{self.settings.assistant_url.rstrip('/')}/v1/chat",
                    headers=headers,
                    json={
                        "prompt": prompt,
                        "user": actor,
                        "conversation_id": conversation_id,
                        "metadata": {"request_id": request_id},
                    },
                    timeout=150,
                )
            )
        except httpx.HTTPError as exc:
            raise NativeServiceError("Orion Assistant is unavailable") from exc
        body = response.json()
        if body.get("request_id") != request_id or body.get("trace_id") != hashlib.sha256(
            trace_id.encode()
        ).hexdigest()[:32]:
            raise NativeServiceError(
                "Orion Assistant did not preserve the business request trace identity"
            )
        answer = body.get("response")
        if not isinstance(answer, str) or not answer.strip():
            raise NativeServiceError("Orion Assistant returned no grounded response")
        citations = body.get("citations") or []
        if not isinstance(citations, list):
            raise NativeServiceError("Orion Assistant returned malformed citations")
        citation_ids = [
            str(item.get("source_id") or item.get("point_id") or "source")
            for item in citations
            if isinstance(item, dict)
        ]
        if not citation_ids:
            raise NativeServiceError(
                "Orion Assistant returned no approved WorkHub source citation"
            )
        return {
            "model": str(body.get("model") or "orion-assistant"),
            "model_version": "assistant-v1",
            "inference_id": str(
                body.get("workflow_id") or f"assistant-{uuid.uuid4().hex}"
            ),
            "conversation_id": str(body.get("conversation_id") or conversation_id),
            "response": answer.strip(),
            "citations": citation_ids,
            "raw_digest": "sha256:"
            + hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }

    def unleash_feature(self, feature: str) -> dict[str, Any]:
        url = (
            f"{self.settings.unleash_url}/api/admin/projects/"
            f"{self.settings.unleash_project}/features/{feature}"
        )
        return checked(
            httpx.get(
                url,
                headers={"Authorization": self.settings.unleash_token},
                timeout=20,
            )
        ).json()

    def unleash_enabled(self, feature: str) -> bool:
        body = self.unleash_feature(feature)
        environment = next(
            item
            for item in body.get("environments", [])
            if item.get("name") == self.settings.unleash_environment
        )
        return bool(environment["enabled"])

    def unleash_toggle(self, feature: str, enabled: bool) -> list[str]:
        state = "on" if enabled else "off"
        url = (
            f"{self.settings.unleash_url}/api/admin/projects/"
            f"{self.settings.unleash_project}/features/{feature}/environments/"
            f"{self.settings.unleash_environment}/{state}"
        )
        response = checked(
            httpx.post(
                url,
                headers={"Authorization": self.settings.unleash_token},
                timeout=20,
            )
        )
        return response_ids(response, feature)

    def _odoo_uid(self) -> int:
        common = xmlrpc.client.ServerProxy(
            f"{self.settings.odoo_url}/xmlrpc/2/common", allow_none=True
        )
        uid = common.authenticate(
            self.settings.odoo_database,
            self.settings.odoo_user,
            self.settings.odoo_password,
            {},
        )
        if not uid:
            raise NativeServiceError("Odoo authentication failed")
        return int(uid)

    def odoo_call(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        models = xmlrpc.client.ServerProxy(
            f"{self.settings.odoo_url}/xmlrpc/2/object", allow_none=True
        )
        return models.execute_kw(
            self.settings.odoo_database,
            self._odoo_uid(),
            self.settings.odoo_password,
            model,
            method,
            args,
            kwargs or {},
        )

    def odoo_one(self, model: str, domain: list[Any]) -> int:
        ids = self.odoo_call(model, "search", [domain], {"limit": 2})
        if len(ids) != 1:
            raise NativeServiceError(
                f"Odoo expected one {model} record for {domain}; found {len(ids)}"
            )
        return int(ids[0])

    def odoo_partner_state(self, partner_id: int) -> dict[str, Any]:
        record = self.odoo_call(
            "res.partner",
            "read",
            [[partner_id]],
            {"fields": ["id", "name", "ref", "credit", "debit"]},
        )[0]
        return {
            "id": record["id"],
            "name": record["name"],
            "ref": record["ref"],
            "credit": float(record["credit"]),
            "debit": float(record["debit"]),
        }

    def odoo_post_adjustment(
        self, request_id: str, move_type: str, amount: float, reference: str
    ) -> tuple[int, dict[str, Any], list[str]]:
        partner_id = self.odoo_one("res.partner", [["ref", "=", "KAI-CUSTOMER-001"]])
        product_id = self.odoo_one(
            "product.product", [["default_code", "=", "ORION-SERVICE-CREDIT"]]
        )
        move_id = int(
            self.odoo_call(
                "account.move",
                "create",
                [
                    {
                        "move_type": move_type,
                        "partner_id": partner_id,
                        "ref": reference,
                        "invoice_origin": request_id,
                        "invoice_line_ids": [
                            [
                                0,
                                0,
                                {
                                    "product_id": product_id,
                                    "name": "Orion service adjustment",
                                    "quantity": 1.0,
                                    "price_unit": amount,
                                },
                            ]
                        ],
                    }
                ],
            )
        )
        self.odoo_call("account.move", "action_post", [[move_id]])
        move = self.odoo_call(
            "account.move",
            "read",
            [[move_id]],
            {
                "fields": [
                    "id",
                    "name",
                    "move_type",
                    "state",
                    "amount_total",
                    "partner_id",
                    "line_ids",
                    "ref",
                ]
            },
        )[0]
        if move["state"] != "posted" or float(move["amount_total"]) != amount:
            raise NativeServiceError("Odoo did not post the expected adjustment")
        pdf_path = self._odoo_pdf(move_id, request_id)
        return move_id, move, [move["name"], str(pdf_path)]

    def _odoo_pdf(self, move_id: int, request_id: str) -> Path:
        with httpx.Client(timeout=60) as client:
            checked(
                client.post(
                    f"{self.settings.odoo_url}/web/session/authenticate",
                    json={
                        "jsonrpc": "2.0",
                        "params": {
                            "db": self.settings.odoo_database,
                            "login": self.settings.odoo_user,
                            "password": self.settings.odoo_password,
                        },
                    },
                )
            )
            response = checked(
                client.get(
                    f"{self.settings.odoo_url}/report/pdf/"
                    f"account.report_invoice/{move_id}"
                )
            )
        if not response.content.startswith(b"%PDF"):
            raise NativeServiceError("Odoo invoice report was not a PDF")
        path = Path(self.settings.evidence_directory) / f"{request_id}-credit-note.pdf"
        path.write_bytes(response.content)
        return path

    @contextmanager
    def ghost_session(self) -> Iterator[httpx.Client]:
        with httpx.Client(
            base_url=self.settings.ghost_url,
            headers={
                "Host": self.settings.ghost_host,
                "Origin": self.settings.ghost_origin,
                "Accept-Version": "v5.0",
                "X-Forwarded-Host": self.settings.ghost_host,
                "X-Forwarded-Proto": "https",
            },
            timeout=30,
        ) as client:
            login = checked(
                client.post(
                    "/ghost/api/admin/session/",
                    json={
                        "username": self.settings.ghost_user,
                        "password": self.settings.ghost_password,
                    },
                )
            )
            cookies = SimpleCookie()
            for value in login.headers.get_list("set-cookie"):
                cookies.load(value)
            session = cookies.get("ghost-admin-api-session")
            if session is None:
                raise NativeServiceError("Ghost did not issue an authenticated session")
            client.headers["Cookie"] = f"{session.key}={session.value}"
            yield client

    def ghost_post(self, slug: str) -> dict[str, Any]:
        with self.ghost_session() as client:
            body = checked(
                client.get(
                    "/ghost/api/admin/posts/",
                    params={"filter": f"slug:{slug}", "formats": "html"},
                )
            ).json()
        posts = body.get("posts", [])
        if len(posts) != 1:
            raise NativeServiceError(f"Ghost expected one post for slug {slug}")
        return posts[0]

    def ghost_update(
        self, post_id: str, updated_at: str, fields: dict[str, Any]
    ) -> tuple[dict[str, Any], list[str]]:
        with self.ghost_session() as client:
            response = checked(
                client.put(
                    f"/ghost/api/admin/posts/{post_id}/",
                    params={"source": "html"},
                    json={
                        "posts": [{"id": post_id, "updated_at": updated_at, **fields}]
                    },
                )
            )
        post = response.json()["posts"][0]
        return post, response_ids(response, post_id)

    def mautic_request(
        self, method: str, path: str, *, data: dict[str, Any] | None = None
    ) -> httpx.Response:
        return checked(
            httpx.request(
                method,
                f"{self.settings.mautic_url}/api{path}",
                auth=(self.settings.mautic_user, self.settings.mautic_password),
                json=data,
                timeout=60,
            )
        )

    def mautic_named(self, resource: str, search: str, key: str) -> dict[str, Any]:
        body = self.mautic_request(
            "GET", f"/{resource}?search={quote(search)}&limit=100"
        ).json()
        values = body.get(key, {})
        items = list(values.values()) if isinstance(values, dict) else values
        exact = [
            item
            for item in items
            if item.get("alias") == search or item.get("name") == search
        ]
        if len(exact) != 1:
            raise NativeServiceError(
                f"Mautic expected one {resource} record named {search}"
            )
        return exact[0]

    def mautic_contact(self, email: str) -> dict[str, Any]:
        body = self.mautic_request(
            "GET", f"/contacts?search={quote(email)}&limit=100"
        ).json()
        values = body.get("contacts", {})
        items = list(values.values()) if isinstance(values, dict) else values
        exact = [
            item
            for item in items
            if item.get("fields", {}).get("core", {}).get("email", {}).get("value")
            == email
        ]
        if len(exact) != 1:
            raise NativeServiceError(f"Mautic expected one contact with email {email}")
        return exact[0]

    def zammad_request(
        self, method: str, path: str, *, data: dict[str, Any] | None = None
    ) -> httpx.Response:
        return checked(
            httpx.request(
                method,
                f"{self.settings.zammad_url}/api/v1{path}",
                headers={"Host": self.settings.zammad_host},
                auth=(self.settings.zammad_user, self.settings.zammad_password),
                json=data,
                timeout=30,
            )
        )

    def zammad_ticket_by_title(self, title: str) -> dict[str, Any]:
        tickets = self.zammad_request("GET", "/tickets?per_page=100").json()
        exact = [item for item in tickets if item.get("title") == title]
        if len(exact) != 1:
            raise NativeServiceError(
                f"Zammad expected one ticket titled {title}; found {len(exact)}"
            )
        return exact[0]

    def redmine_request(
        self, method: str, path: str, *, data: dict[str, Any] | None = None
    ) -> httpx.Response:
        return checked(
            httpx.request(
                method,
                f"{self.settings.redmine_url}{path}",
                headers={"Host": self.settings.redmine_host},
                auth=(self.settings.redmine_user, self.settings.redmine_password),
                json=data,
                timeout=30,
            )
        )

    def redmine_issue_by_subject(self, subject: str) -> dict[str, Any]:
        issues = self.redmine_request(
            "GET", "/issues.json?project_id=orion&status_id=*&limit=100"
        ).json()["issues"]
        exact = [item for item in issues if item.get("subject") == subject]
        if len(exact) != 1:
            raise NativeServiceError(
                f"Redmine expected one issue titled {subject}; found {len(exact)}"
            )
        return self.redmine_request("GET", f"/issues/{exact[0]['id']}.json").json()[
            "issue"
        ]

    def nextcloud(
        self, method: str, path: str, content: bytes | None = None
    ) -> httpx.Response:
        url = (
            f"{self.settings.nextcloud_url}/remote.php/dav/files/"
            f"{quote(self.settings.nextcloud_user)}/{quote(path, safe='/')}"
        )
        response = httpx.request(
            method,
            url,
            headers={"Host": self.settings.nextcloud_host},
            auth=(self.settings.nextcloud_user, self.settings.nextcloud_password),
            content=content,
            timeout=60,
        )
        return checked(response)

    def nextcloud_exists(self, path: str) -> bool:
        url = (
            f"{self.settings.nextcloud_url}/remote.php/dav/files/"
            f"{quote(self.settings.nextcloud_user)}/{quote(path, safe='/')}"
        )
        response = httpx.request(
            "HEAD",
            url,
            headers={"Host": self.settings.nextcloud_host},
            auth=(self.settings.nextcloud_user, self.settings.nextcloud_password),
            timeout=30,
        )
        if response.status_code == 404:
            return False
        checked(response)
        return True

    def rabbitmq_request(
        self, method: str, path: str, *, data: dict[str, Any]
    ) -> httpx.Response:
        return checked(
            httpx.request(
                method,
                f"{self.settings.rabbitmq_url}/api{path}",
                auth=(self.settings.rabbitmq_user, self.settings.rabbitmq_password),
                json=data,
                timeout=20,
            )
        )

    def qdrant_request(
        self, method: str, path: str, *, data: dict[str, Any] | None = None
    ) -> httpx.Response:
        return checked(
            httpx.request(
                method,
                f"{self.settings.qdrant_url}{path}",
                json=data,
                timeout=30,
            )
        )

    def lakefs_s3(self):
        return boto3.client(
            "s3",
            endpoint_url=self.settings.lakefs_url,
            aws_access_key_id=self.settings.lakefs_access_key,
            aws_secret_access_key=self.settings.lakefs_secret_key,
            region_name="us-east-1",
            config=Config(s3={"addressing_style": "path"}),
        )

    def lakefs_commit(self, branch: str, message: str, metadata: dict[str, str]) -> str:
        response = checked(
            httpx.post(
                f"{self.settings.lakefs_url}/api/v1/repositories/"
                f"{self.settings.lakefs_repository}/branches/{branch}/commits",
                auth=(self.settings.lakefs_access_key, self.settings.lakefs_secret_key),
                json={"message": message, "metadata": metadata},
                timeout=30,
            )
        )
        return str(response.json()["id"])

    def send_mail(self, sender: str, recipient: str, subject: str, body: str) -> str:
        message_id = f"<{hashlib.sha256((recipient + subject).encode()).hexdigest()[:24]}@keplerops.lab>"
        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject
        message["Message-ID"] = message_id
        message.set_content(body)
        credentials = {
            "billing@keplerops.lab": (
                self.settings.smtp_billing_user,
                self.settings.smtp_billing_password,
            ),
            "support@keplerops.lab": (
                self.settings.smtp_support_user,
                self.settings.smtp_support_password,
            ),
        }
        if sender not in credentials:
            raise NativeServiceError(f"no bounded SMTP identity for sender {sender}")
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with smtplib.SMTP(
            self.settings.smtp_host, self.settings.smtp_port, timeout=30
        ) as client:
            client.starttls(context=context)
            client.login(*credentials[sender])
            client.send_message(message)
        return message_id
