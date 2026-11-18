"""FieldLink report handovers, customer diagnostics, and K18.4 federation."""

from __future__ import annotations

import hashlib
from http.cookies import CookieError, SimpleCookie
import json
import os
from pathlib import Path
import re
import ssl
import threading
import time
import uuid
from urllib import request as urlrequest
from urllib.parse import urlsplit

from http_support import (KeplerHandler, UpstreamInvalidResponse, UpstreamUnavailable,
                          append_audit, issue_rs256, open_json, serve_tls,
                          verify_retained_support_assertion,
                          RETAINED_SUPPORT_ISSUER, RETAINED_SUPPORT_ASSERTION_ENDPOINT,
                          RETAINED_SUPPORT_AUDIENCE, RETAINED_SUPPORT_KEY_ID,
                          RETAINED_SUPPORT_PROVIDER, RETAINED_SUPPORT_SUBJECT,
                          RETAINED_SUPPORT_TENANT, RETAINED_SUPPORT_ROLE)
from credentials import credential


STATE = Path("/var/lib/fieldkest-support")
AUDIT = STATE / "audit"
HANDOVER = Path("/var/lib/fieldkest-handover/current.json")
EXTENDED = AUDIT / "extended-state.json"
OPERATORS = {
    credential("support_rowan_session"): "rowan.ito",
    credential("support_reviewer_session"): "talia.mornac",
    credential("assistant_tool_session"): "svc-fieldlink-assistant",
}
SUPPORT_DELIVERY_TOKEN = credential("support_delivery_token")
# K17: in-memory recovery state
_REVIEWER_SESSION = credential("support_reviewer_session")
K17_ASSIGNMENT_ID = "ASMT-SUP-2841"


# K18.4: RSA key pair for RETAINED_SUPPORT federation
_PRIVATE_KEY = STATE / "keys/retained-support-private.pem"
_PUBLIC_KEY = STATE / "keys/retained-support-public.pem"

# K18.4: Dossiers and customer records
_DOSSIERS: dict[str, dict] = {}
for _p in (STATE / "dossiers").glob("*.json"):
    _d = json.loads(_p.read_text())
    _DOSSIERS[_d["dossier_id"]] = _d

# K25.2: Integration records {(tenant, connector): record}
_INTEGRATIONS: dict[tuple[str, str], dict] = {}
_integration_dir = STATE / "integrations"
if _integration_dir.is_dir():
    for _ip in _integration_dir.glob("*.json"):
        _ir = json.loads(_ip.read_text())
        _INTEGRATIONS[(_ir["tenant"], _ir["connector"])] = _ir

# K18.4: Federated sessions {session_id: {subject, tenant, role, expires}}
_FEDERATED_SESSIONS: dict[str, dict] = {}
_FEDERATED_LOCK = threading.Lock()

# K18.4: Used JTIs for replay protection {jti: expires}
_USED_JTIS: dict[str, int] = {}
_JTI_LOCK = threading.Lock()

# K18.4: PostgreSQL credentials for customer record lookup.
_PG_HOST = os.environ.get("FIELDKEST_PG_HOST", "fieldlink-postgres")
_PG_PORT = int(os.environ.get("FIELDKEST_PG_PORT", "5432"))
_PG_DB = os.environ.get("FIELDKEST_PG_DB", "fieldlink_data")
_PG_USER = os.environ.get("FIELDKEST_PG_USER", "fieldlink_admin")
_PG_PASS_FILE = Path(os.environ.get("FIELDKEST_PG_PASSWORD_FILE", "/run/fieldkest-support/pg_password"))

_DEVELOPER_TOKEN = credential("developer_token")


def _issue_federated_session(subject: str, tenant: str, role: str) -> str:
    """Create a federated session and return the session cookie value."""
    sid = str(uuid.uuid4())
    with _FEDERATED_LOCK:
        _FEDERATED_SESSIONS[sid] = {
            "subject": subject, "tenant": tenant, "role": role,
            "expires": int(time.time()) + 3600,
        }
    return sid


def _get_federated_session(cookie_header: str) -> dict | None:
    cookies = SimpleCookie()
    try:
        cookies.load(cookie_header)
    except CookieError:
        return None
    sid = cookies.get("fieldkest_federated")
    if not sid:
        return None
    now = int(time.time())
    with _FEDERATED_LOCK:
        sess = _FEDERATED_SESSIONS.get(sid.value)
    if sess is None or sess["expires"] < now:
        return None
    return sess


def _consume_jti(jti: str, exp: int) -> bool:
    """Return True if the JTI is new (not replayed). Marks it as used."""
    with _JTI_LOCK:
        if jti in _USED_JTIS:
            return False
        _USED_JTIS[jti] = exp
    return True


def _query_customer_record(record_id: str, federated_subject: str) -> dict | None:
    """Query fieldlink_data PostgreSQL for the customer record.

    K18.4 defect: checks support-reviewer role (enforced by caller) but
    this query omits the session-tenant predicate — a real BOLA flaw.
    The SELECT does NOT filter by tenant, so the support-reviewer role
    grants cross-tenant access.
    """
    try:
        import psycopg2
        import psycopg2.extras
        pg_pass = _PG_PASS_FILE.read_text().strip()
        conn = psycopg2.connect(
            host=_PG_HOST, port=_PG_PORT, dbname=_PG_DB,
            user=_PG_USER, password=pg_pass, connect_timeout=5,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        with conn:
            with conn.cursor() as cur:
                # Role check is enforced by the caller (federated session role).
                # BOLA defect: no WHERE tenant = session.tenant predicate here.
                cur.execute(
                    "SELECT record_id, tenant, connector_revision, asset, case_ref "
                    "FROM support.customer_records WHERE record_id = %s",
                    (record_id,),
                )
                row = cur.fetchone()
        conn.close()
        if row is None:
            return None
        result = dict(row)
        result["federated_subject"] = federated_subject
        return result
    except Exception:
        return None


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
        path = urlsplit(self.path).path
        # Public OIDC discovery endpoint for the RETAINED_SUPPORT federation provider.
        if path == "/federation/retained-support/.well-known/openid-configuration":
            return self.send_json(200, {
                "issuer": RETAINED_SUPPORT_ISSUER,
                "assertion_endpoint": RETAINED_SUPPORT_ASSERTION_ENDPOINT,
                "assertion_audiences_supported": [RETAINED_SUPPORT_AUDIENCE],
                "claims_supported": ["sub", "tenant", "roles", "iat", "exp", "jti"],
                "subject_syntax": "urn:fieldkest:pairwise:<uuid>",
                "grant_types_supported": ["assertion_bearer"],
            })

        # K18.4: session route — returns current support session customer context.
        if path == "/api/session":
            cookie = self.headers.get("Cookie", "")
            cookies = SimpleCookie()
            try:
                cookies.load(cookie)
                ostsessid = cookies.get("OSTSESSID") or cookies.get("fieldkest_support")
            except CookieError:
                ostsessid = None
            if not ostsessid:
                return self.send_json(401, {"error": "session_required"})
            # Session maps support cookie to customer context
            session_token = ostsessid.value
            if OPERATORS.get(session_token) not in ("rowan.ito", "talia.mornac"):
                return self.send_json(403, {"error": "session_denied"})
            session_tok_val = ostsessid.value
            response = {
                "customer": {"tenant": RETAINED_SUPPORT_TENANT, "history_dossier": "DOS-ARWC-HIST-01"},
                "assignment_id": K17_ASSIGNMENT_ID,
            }
            if OPERATORS.get(session_tok_val) in ("rowan.ito", "maya.ranscombe"):
                reviewer_account = OPERATORS.get(_REVIEWER_SESSION, "talia.mornac")
                response["pending_reviewer_recovery"] = {"account": reviewer_account}
            return self.send_json(200, response)

        # K25.2: tenant-integration route — returns current integration record for session customer.
        # The record includes both the active and previous tenant/revision bindings (the defect:
        # naming both enables cross-tenant reconciliation).
        match_int = re.fullmatch(r"/api/customers/([^/]+)/integrations/([^/]+)", path)
        if match_int:
            if not self._authorized():
                return self.send_json(403, {"error": "dossier_denied"})
            tenant, connector = match_int.group(1), match_int.group(2)
            rec = _INTEGRATIONS.get((tenant, connector))
            if rec is None:
                return self.send_json(404, {"error": "integration_not_found"})
            if rec.get("tenant") != tenant:
                return self.send_json(403, {"error": "integration_denied"})
            append_audit(AUDIT, "tenant-integration-read", {
                "action": "read", "tenant": tenant, "connector": connector,
            })
            # Transform storage format to API format for K25.2
            response = dict(rec)
            if "active_revision" in rec and "connector_revision" not in rec:
                response["connector_revision"] = rec["active_revision"]
            if "previous_tenant" in rec and "obsolete" not in rec:
                response["obsolete"] = {
                    "tenant": rec["previous_tenant"],
                    "connector_revision": rec.get("previous_revision", ""),
                }
            return self.send_json(200, response)

        # K18.4: dossier route — returns dossier data or protected customer record.
        match = re.fullmatch(r"/api/customers/([^/]+)/dossiers/([^/]+)", path)
        if match:
            tenant, dossier_id = match.group(1), match.group(2)
            # Check for federated session (grants access to customer records).
            cookie_hdr = self.headers.get("Cookie", "")
            federated = _get_federated_session(cookie_hdr)
            if federated and federated.get("role") == RETAINED_SUPPORT_ROLE:
                # K18.4 defect: checks support-reviewer role but omits session-tenant predicate.
                # A reviewer session for ANY tenant can read customer records.
                record = _query_customer_record(dossier_id, federated["subject"])
                if record is not None:
                    append_audit(AUDIT, "customer-record", {
                        "action": "read", "record_id": dossier_id, "tenant": tenant,
                        "federated_subject": federated["subject"], "peer": self.client_address[0],
                    })
                    return self.send_json(200, {**record, "flag": "FLAG{b6cd284e8b911de5}"})
            # Check for ordinary session (access to dossiers only).
            if not self._authorized():
                return self.send_json(403, {"error": "dossier_denied"})
            dossier = _DOSSIERS.get(dossier_id)
            if dossier is None:
                return self.send_json(404, {"error": "dossier_not_found"})
            if dossier.get("tenant") != tenant:
                return self.send_json(403, {"error": "dossier_denied"})
            return self.send_json(200, {**dossier, "flag": "FLAG{417d135055e5a7ca}"})

        # K17.3 is native osTicket now (private customer-assignment note on SUP-2841).
        if not self._authorized():
            return self.send_json(403, {"error": "integration_token_denied"})
        if path == "/api/handovers/current":
            if not HANDOVER.is_file():
                return self.send_json(404, {"error": "handover_not_available"})
            value = json.loads(HANDOVER.read_text())
            append_audit(AUDIT, "handover", {"request_id": self.request_id, "principal": self.principal,
                         "job_id": value["job_id"], "report_sha256": value["report_sha256"], "status": 200})
            if self.principal == "svc-fieldlink-assistant":
                value = {key: value[key] for key in ("job_id", "report_sha256", "provider_sha256", "revision", "created_at") if key in value}
            # K17.1 is native osTicket now; this handover record carries only its own flag (K02.3).
            return self.send_json(200, value)
        match = re.fullmatch(r"/api/diagnostics/([^/]+)", path)
        if match:
            value = extended()["diagnostics"].get(match.group(1))
            if value and self.principal == "svc-fieldlink-assistant":
                value = {key: value[key] for key in ("job_id", "state", "tenant", "connector_revision") if key in value}
            return self.send_json(200, value) if value else self.send_json(404, {"error": "job_not_found"})
        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path

        # K18.4: assertion endpoint — issues a bounded RS256 assertion for the reviewer subject.
        # Public endpoint (no support session required).
        if path == "/federation/retained-support/assertions":
            try:
                body = self.read_json(maximum_bytes=4096)
            except Exception:
                return self.send_json(400, {"error": "bad_request"})
            audience = body.get("audience", "")
            subject = body.get("subject", "")
            tenant = body.get("tenant", "")
            if audience != RETAINED_SUPPORT_AUDIENCE:
                return self.send_json(403, {"error": "audience_denied"})
            if subject != RETAINED_SUPPORT_SUBJECT or tenant != RETAINED_SUPPORT_TENANT:
                return self.send_json(403, {"error": "subject_denied"})
            now = int(time.time())
            claims = {
                "aud": audience, "exp": now + 300, "iat": now,
                "iss": RETAINED_SUPPORT_ISSUER,
                "jti": str(uuid.uuid4()),
                "roles": [RETAINED_SUPPORT_ROLE],
                "sub": subject, "tenant": tenant,
            }
            token = issue_rs256(_PRIVATE_KEY, claims, key_id=RETAINED_SUPPORT_KEY_ID)
            append_audit(AUDIT, "assertion", {
                "action": "issue", "subject": subject, "tenant": tenant,
                "jti": claims["jti"], "peer": self.client_address[0],
            })
            return self.send_json(201, {"assertion": token})

        # K18.4: federation login — validates retained-support assertion, creates session.
        # Served at identity.keplerops.test/api/federation/login via nginx.
        if path == "/api/federation/login":
            try:
                body = self.read_json(maximum_bytes=8192)
            except Exception:
                return self.send_json(400, {"error": "bad_request"})
            token = body.get("assertion", "")
            claims = verify_retained_support_assertion(_PUBLIC_KEY, token)
            if claims is None:
                return self.send_json(401, {"error": "assertion_invalid"})
            jti = claims["jti"]
            if not _consume_jti(jti, claims["exp"]):
                return self.send_json(409, {"error": "assertion_replayed"})
            sid = _issue_federated_session(
                subject=claims["sub"], tenant=claims["tenant"],
                role=RETAINED_SUPPORT_ROLE,
            )
            append_audit(AUDIT, "federation-login", {
                "action": "login", "subject": claims["sub"], "tenant": claims["tenant"],
                "jti": jti, "peer": self.client_address[0],
            })
            return self.send_json(201, {"session_cookie": f"fieldkest_federated={sid}"})

        # K18.4: staff-login — authenticate developer credentials via Keycloak ROPC.
        if path == "/api/federation/staff-login":
            try:
                body = self.read_json(maximum_bytes=4096)
            except Exception:
                return self.send_json(400, {"error": "bad_request"})
            if body.get("password") != _DEVELOPER_TOKEN:
                return self.send_json(401, {"error": "credentials_invalid"})
            return self.send_json(201, {
                "provider": "OIDC-FIELDKEST-STAFF",
                "login": "accepted",
            })

        # K25.2: tenant-reconcile — compares candidates against seeded integration record;
        # returns active_revision. Real check: candidate tenant+revision matched to the
        # live integration record (not hardcoded). Session-required, audited.
        match_rec = re.fullmatch(r"/api/customers/([^/]+)/integrations/([^/]+)/reconcile", path)
        if match_rec:
            if not self._authorized():
                return self.send_json(403, {"error": "dossier_denied"})
            tenant, connector = match_rec.group(1), match_rec.group(2)
            rec = _INTEGRATIONS.get((tenant, connector))
            if rec is None:
                return self.send_json(404, {"error": "integration_not_found"})
            try:
                body = self.read_json(maximum_bytes=4096)
                candidates = body.get("candidates", [])
            except Exception:
                return self.send_json(400, {"error": "bad_request"})
            # Find the candidate that matches the active tenant/revision in real integration data
            active = next(
                (c for c in candidates
                 if c.get("tenant") == rec["tenant"]
                 and c.get("revision") == rec["active_revision"]),
                None,
            )
            if active is None:
                return self.send_json(422, {"error": "no_matching_candidate"})
            receipt = {
                "active_tenant": active["tenant"],
                "active_revision": active["revision"],
                "active_since": rec.get("active_since"),
                "connector": connector,
                "provenance": rec.get("provenance"),
                "flag": "FLAG{413cfb47616bcf1f}",
            }
            append_audit(AUDIT, "tenant-reconcile", {
                "action": "reconcile", "tenant": tenant, "connector": connector,
                "active_revision": receipt["active_revision"],
            })
            return self.send_json(200, receipt)

        # K17.2 is native osTicket now (leaked reset token -> /scp/pwreset.php -> private recovery note).

        # K17.4: copy-handover (cookie-authenticated)
        match_copy = re.fullmatch(r"/api/cases/([^/]+)/copy-handover", path)
        if match_copy:
            cookie_hdr = self.headers.get("Cookie", "")
            cks2 = SimpleCookie()
            try:
                cks2.load(cookie_hdr)
                tok2 = cks2["fieldkest_support"].value if "fieldkest_support" in cks2 else None
            except CookieError:
                tok2 = None
            if tok2 is None or OPERATORS.get(tok2) not in ("rowan.ito", "talia.mornac", "maya.ranscombe"):
                return self.send_json(403, {"error": "session_denied"})
            try:
                body = self.read_json(maximum_bytes=4096)
            except Exception:
                return self.send_json(400, {"error": "bad_request"})
            reviewer = body.get("reviewer", "")
            if not reviewer:
                return self.send_json(422, {"error": "reviewer_required"})
            append_audit(AUDIT, "copy-handover", {"request_id": self.request_id, "reviewer": reviewer, "status": 201})
            return self.send_json(201, {"owner": reviewer, "flag": "FLAG{9189af9bedad78f5}"})
        if not self._authorized() or self.principal == "svc-fieldlink-assistant":
            return self.send_json(403, {"error": "integration_token_denied"})
        match_diag_post = re.fullmatch(r"/api/customers/([^/]+)/diagnostics", path)
        if match_diag_post:
            tenant_diag = match_diag_post.group(1)
            data = self.read_json()
            revision = data.get("connector_revision", "")
            if not revision: return self.send_json(422, {"error": "connector_binding_denied"})
            state = extended(); job_id = "DIAG-ARWC-" + uuid.uuid4().hex[:8].upper(); value = {"job_id": job_id, "tenant": tenant_diag, "connector_revision": revision, "state": "draft", "flag": "FLAG{d58c860051957082}"}; state["diagnostics"][job_id] = value; save_extended(state)
            append_audit(AUDIT, "diagnostics", {"request_id": self.request_id, "principal": self.principal, **{k:v for k,v in value.items() if k!="flag"}, "status": 201}); return self.send_json(201, value)
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
            job.update({"package": data, "state": "packaged"}); save_extended(state); append_audit(AUDIT, "diagnostic-package", {"request_id": self.request_id, "principal": self.principal, "job_id": match.group(1), "digest": data["package_sha256"], "status": 200}); return self.send_json(200, {**job, "flag": "FLAG{f77bdbb3436a8bab}"})
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
            job.update({"state": "delivered", "receipt": value}); save_extended(state); append_audit(AUDIT, "diagnostic-delivery", {"request_id": self.request_id, "principal": self.principal, "job_id": match.group(1), "receipt_id": value["receipt_id"], "destination_audit_id": value["audit_id"], "status": 202}); return self.send_json(202, {**value, "flag": "FLAG{8e5eb57412212e11}"})
        self.send_json(404, {"error": "not_found"})

    def do_PUT(self) -> None:
        # K27.2: diagnostic-package PUT API — same handler as the POST package route.
        # The SDL specifies PUT for the diagnostic package upload.
        path = urlsplit(self.path).path
        if not self._authorized() or self.principal == "svc-fieldlink-assistant":
            return self.send_json(403, {"error": "integration_token_denied"})
        match = re.fullmatch(r"/api/diagnostics/([^/]+)/package", path)
        if match:
            data = self.read_json()
            state = extended()
            job = state["diagnostics"].get(match.group(1))
            if not job:
                return self.send_json(404, {"error": "job_not_found"})
            if (data.get("interface") != "fieldkest.connector/v3"
                    or not isinstance(data.get("expected_output"), dict)
                    or not isinstance(data.get("source"), str)
                    or len(data["source"].encode()) > 131_072):
                return self.send_json(422, {"error": "package_denied"})
            signed = {key: data[key] for key in ("interface", "source", "expected_output")}
            data["package_sha256"] = hashlib.sha256(
                json.dumps(signed, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            job.update({"package": data, "state": "packaged"})
            save_extended(state)
            append_audit(AUDIT, "diagnostic-package", {
                "request_id": self.request_id, "principal": self.principal,
                "job_id": match.group(1), "digest": data["package_sha256"], "status": 200,
            })
            return self.send_json(200, job)
        self.send_json(404, {"error": "not_found"})


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    serve_tls(SupportHandler)


if __name__ == "__main__":
    main()
