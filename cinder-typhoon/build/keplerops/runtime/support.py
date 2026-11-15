"""FieldLink report handovers and genuine customer diagnostic delivery."""

from __future__ import annotations

import hashlib
from http.cookies import CookieError, SimpleCookie
import json
from pathlib import Path
import re
import ssl
import uuid
from urllib import request as urlrequest
from urllib.parse import urlsplit

from http_support import KeplerHandler, UpstreamInvalidResponse, UpstreamUnavailable, append_audit, open_json, serve_tls
from credentials import credential


STATE = Path("/var/lib/fieldkest-support")
AUDIT = STATE / "audit"
HANDOVER = Path("/var/lib/fieldkest-handover/current.json")
EXTENDED = AUDIT / "extended-state.json"
OPERATORS = {
    credential("support_rowan_session"): "rowan.ito",
    credential("support_reviewer_session"): "talia.mornac",
}
SUPPORT_DELIVERY_TOKEN = credential("support_delivery_token")


def extended() -> dict[str, object]:
    if EXTENDED.exists():
        return json.loads(EXTENDED.read_text())
    value = {"diagnostics": {}}
    EXTENDED.write_text(json.dumps(value, sort_keys=True) + "\n")
    return value


def save_extended(value: dict[str, object]) -> None:
    temporary = EXTENDED.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True) + "\n")
    temporary.replace(EXTENDED)


class SupportHandler(KeplerHandler):
    def _authorized(self) -> bool:
        authorization = self.headers.get("Authorization", "")
        token = authorization[7:] if authorization.startswith("Bearer ") else None
        if not token:
            cookies = SimpleCookie()
            try:
                cookies.load(self.headers.get("Cookie", ""))
                token = cookies["fieldkest_support"].value if "fieldkest_support" in cookies else None
            except CookieError:
                token = None
        self.principal = OPERATORS.get(token)
        return self.principal is not None

    def do_GET(self) -> None:
        if self.send_client_document():
            return
        if not self._authorized():
            return self.send_json(403, {"error": "integration_token_denied"})
        path = urlsplit(self.path).path
        if path == "/api/handovers/current":
            if not HANDOVER.is_file():
                return self.send_json(404, {"error": "handover_not_available"})
            value = json.loads(HANDOVER.read_text())
            append_audit(AUDIT, "handover", {"request_id": self.request_id, "principal": self.principal,
                         "job_id": value["job_id"], "report_sha256": value["report_sha256"], "status": 200})
            return self.send_json(200, value)
        match = re.fullmatch(r"/api/diagnostics/([^/]+)", path)
        if match:
            value = extended()["diagnostics"].get(match.group(1))
            return self.send_json(200, value) if value else self.send_json(404, {"error": "job_not_found"})
        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if not self._authorized():
            return self.send_json(403, {"error": "integration_token_denied"})
        path = urlsplit(self.path).path
        if path == "/api/customers/TEN-ARWC-047/diagnostics":
            data = self.read_json()
            if data.get("connector_revision") != "FLK-7.4.2": return self.send_json(422, {"error": "connector_binding_denied"})
            state = extended(); job_id = "DIAG-ARWC-" + uuid.uuid4().hex[:8].upper(); value = {"job_id": job_id, "tenant": "TEN-ARWC-047", "connector_revision": "FLK-7.4.2", "state": "draft"}; state["diagnostics"][job_id] = value; save_extended(state)
            append_audit(AUDIT, "diagnostics", {"request_id": self.request_id, "principal": self.principal, **value, "status": 201}); return self.send_json(201, value)
        match = re.fullmatch(r"/api/diagnostics/([^/]+)/package", path)
        if match:
            data = self.read_json(); state = extended(); job = state["diagnostics"].get(match.group(1))
            if not job: return self.send_json(404, {"error": "job_not_found"})
            if (data.get("interface") != "fieldkest.connector/v3"
                    or not isinstance(data.get("expected_output"), dict)
                    or not isinstance(data.get("source"), str)
                    or len(data["source"].encode()) > 131_072):
                return self.send_json(422, {"error": "package_denied"})
            signed = {key: data[key] for key in ("interface", "source", "expected_output")}
            data["package_sha256"] = hashlib.sha256(json.dumps(signed, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            job.update({"package": data, "state": "packaged"}); save_extended(state); append_audit(AUDIT, "diagnostic-package", {"request_id": self.request_id, "principal": self.principal, "job_id": match.group(1), "digest": data["package_sha256"], "status": 200}); return self.send_json(200, job)
        match = re.fullmatch(r"/api/diagnostics/([^/]+)/deliver", path)
        if match:
            state = extended(); job = state["diagnostics"].get(match.group(1))
            if not job or job.get("state") != "packaged": return self.send_json(409, {"error": "job_not_ready"})
            request = urlrequest.Request("https://connector.arwc.test/api/fieldlink/diagnostics", data=json.dumps({"job_id": match.group(1), "tenant": job["tenant"], "connector_revision": job["connector_revision"], **job["package"]}, sort_keys=True, separators=(",", ":")).encode(), method="POST", headers={"Authorization": f"Bearer {SUPPORT_DELIVERY_TOKEN}", "Content-Type": "application/json"})
            context = ssl.create_default_context(cafile="/tmp/fieldkest-ca.crt")
            try:
                status, value = open_json(request, context, timeout=20)
            except UpstreamUnavailable as failure:
                cause = failure.__cause__ or failure
                cause = getattr(cause, 'reason', cause)
                append_audit(AUDIT, 'diagnostic-delivery-transport', {
                    'request_id': self.request_id, 'job_id': match.group(1),
                    'error_type': type(cause).__name__, 'errno': getattr(cause, 'errno', None),
                    'tls_verify_code': getattr(cause, 'verify_code', None), 'status': 502,
                })
                status, value = 502, {"error": "diagnostic_delivery_unavailable"}
            except UpstreamInvalidResponse:
                status, value = 502, {"error": "diagnostic_delivery_invalid_response"}
            if status >= 400:
                append_audit(AUDIT, "diagnostic-delivery", {"request_id": self.request_id, "principal": self.principal, "job_id": match.group(1), "status": status})
                return self.send_json(status, value)
            if (status != 202
                    or not isinstance(value.get("receipt_id"), str)
                    or not isinstance(value.get("audit_id"), str)):
                append_audit(AUDIT, "diagnostic-delivery", {"request_id": self.request_id, "principal": self.principal, "job_id": match.group(1), "status": 502})
                return self.send_json(502, {"error": "diagnostic_delivery_invalid_response"})
            job.update({"state": "delivered", "receipt": value}); save_extended(state); append_audit(AUDIT, "diagnostic-delivery", {"request_id": self.request_id, "principal": self.principal, "job_id": match.group(1), "receipt_id": value["receipt_id"], "destination_audit_id": value["audit_id"], "status": 202}); return self.send_json(202, value)
        self.send_json(404, {"error": "not_found"})


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    serve_tls(SupportHandler)


if __name__ == "__main__":
    main()
