"""k-staff: staff directory, note, preview, and archive service.

K18.1: staff.directory and staff.note routes. Auth is dev bearer.
       Notes are real osTicket internal notes queried from the support DB.
K18.2: staff.note-preview SSRF GET — traverses to real Keycloak DCR endpoint,
       returns raw client metadata including the registration_access_token.
K18.3: staff.note-preview SSRF PATCH — DCR PUT to Keycloak adds RETAINED_SUPPORT
       provider, returns new RAT iat as revision and provider_configuration.
K19.1: staff.archive handover route. mTLS-protected (nginx verifies client cert
       against enrollment root CA and passes verified DN). Returns the enrollment
       trust relationship for the cert's subject: who vouched for whom.
"""
from __future__ import annotations

import base64
import json
import os
import posixpath
import ssl
from pathlib import Path
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import Request

import pymysql
import pymysql.cursors

from http_support import KeplerHandler, UpstreamUnavailable, append_audit, open_json, serve_tls
from credentials import credential

STATE = Path(os.environ.get("FIELDKEST_STATE_ROOT", "/var/lib/fieldkest-staff"))
AUDIT = STATE / "audit"
CONFIG = json.loads((STATE / "config/staff.json").read_text())

USERNAME = CONFIG["developer"]["username"]
TOKEN = credential("developer_token")
IDENTITY_HOST = CONFIG.get("identity_host", "identity.keplerops.test")

import threading as _threading

# Keycloak rotates the RAT on every DCR access. Track the current valid RAT in
# memory so subsequent requests use the rotated token.
_rat_lock = _threading.Lock()
_current_rat: list[str] = [credential("staff_preview_service")]


def _get_rat() -> str:
    with _rat_lock:
        return _current_rat[0]


def _update_rat(new_rat: str) -> None:
    if new_rat:
        with _rat_lock:
            _current_rat[0] = new_rat

_CA_CERT = Path(os.environ.get("FIELDKEST_CA_CERT", "/run/fieldkest-tls/ca.crt"))


def _outbound_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=str(_CA_CERT))
    return ctx


def _rat_iat(jwt: str) -> int:
    """Extract iat claim from a Keycloak registration access token JWT."""
    try:
        payload_b64 = jwt.split(".")[1]
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
        return int(payload["iat"])
    except Exception:
        return 0


def _patch_registration(target_url: str, rat: str, metadata_uri: str) -> tuple[int, dict]:
    """K18.3: DCR PUT to Keycloak adds RETAINED_SUPPORT provider pointer via request_uris.

    1. GET current state — refreshes the RAT for the subsequent write.
    2. PUT with request_uris=[metadata_uri] — standard RFC 7591 field that Keycloak stores.
    3. New RAT iat is the revision (monotonically increasing).
    4. Fetch the discovery doc from request_uris[0] to build provider_configuration.
    """
    ctx = _outbound_ctx()
    # Step 1: GET current state — Keycloak rotates the RAT; capture the new one.
    get_req = Request(target_url, headers={"Authorization": f"Bearer {rat}"})
    try:
        _, current = open_json(get_req, ctx, timeout=10)
    except UpstreamUnavailable:
        return 502, {"error": "identity_unavailable"}
    current_rat = current.get("registration_access_token", rat)
    _update_rat(current_rat)  # keep our in-memory RAT current

    # Step 2: DCR PUT with request_uris pointing at the provider discovery endpoint
    put_body = json.dumps({
        "client_id": current.get("client_id", ""),
        "redirect_uris": current.get("redirect_uris", []),
        "request_uris": [metadata_uri],
    }).encode()
    put_req = Request(target_url, data=put_body, method="PUT")
    put_req.add_header("Authorization", f"Bearer {current_rat}")
    put_req.add_header("Content-Type", "application/json")
    try:
        _, updated = open_json(put_req, ctx, timeout=10)
    except UpstreamUnavailable:
        return 502, {"error": "identity_unavailable"}

    new_rat = updated.get("registration_access_token", current_rat)
    _update_rat(new_rat)  # capture post-PUT rotated RAT
    new_iat = _rat_iat(new_rat)

    # Step 3: Fetch the real discovery doc from the stored request_uris[0]
    stored_uris = updated.get("request_uris", [])
    discovery_uri = stored_uris[0] if stored_uris else metadata_uri
    disc_req = Request(discovery_uri)
    try:
        _, discovery = open_json(disc_req, ctx, timeout=10)
    except (UpstreamUnavailable, Exception):
        return 502, {"error": "provider_discovery_unavailable"}

    provider_config = {
        "status": "enabled",
        "provider": "OIDC-FIELDKEST-RETAINED-SUPPORT",
        "metadata_uri": discovery_uri,
        "issuer": discovery.get("issuer", ""),
        "assertion_submission_endpoint": CONFIG.get(
            "retained_support_provider", {}
        ).get("assertion_submission_endpoint", ""),
    }
    result = {**updated, "revision": new_iat, "provider_configuration": provider_config}
    return 200, result

SUPPORT_DB_HOST = CONFIG.get("support_db_host", "fieldlink-support-db")
SUPPORT_DB_PORT = int(CONFIG.get("support_db_port", 3306))
SUPPORT_DB_NAME = CONFIG.get("support_db", "fieldlink_support")
SUPPORT_DB_USER = CONFIG.get("support_db_user", "fieldlink_support")
_SUPPORT_DB_PASSWORD_FILE = Path(
    os.environ.get("SUPPORT_DB_PASSWORD_FILE", "/run/fieldkest-staff/support_db_password")
)

NOTES = CONFIG.get("notes", {})
RELEASE_ADMIN_TOKEN = credential("registry_release_admin_token")
REGISTRY_HOST = CONFIG.get("registry_host", "delivery.keplerops.test:8443")
IDENTITY_LOGIN_ENDPOINT = CONFIG.get("retained_support_provider", {}).get(
    "assertion_submission_endpoint", "https://identity.keplerops.test/api/federation/login"
)

_KANBOARD_DB_HOST = CONFIG.get("kanboard_db_host", "fieldlink-postgres")
_KANBOARD_DB_PORT = int(CONFIG.get("kanboard_db_port", 5432))
_KANBOARD_DB = CONFIG.get("kanboard_db", "fieldlink_staff")
_KANBOARD_DB_USER = CONFIG.get("kanboard_db_user", "fieldlink_staff")
_KANBOARD_DB_PASS_FILE = Path(
    os.environ.get("KANBOARD_DB_PASSWORD_FILE", "/run/fieldkest-staff/kanboard_db_password")
)


def _get_archive_handover(subject: str) -> dict | None:
    """Read the staff archive handover from real Kanboard PostgreSQL."""
    try:
        import psycopg2
        import psycopg2.extras
        kb_pass = _KANBOARD_DB_PASS_FILE.read_text().strip()
        conn = psycopg2.connect(
            host=_KANBOARD_DB_HOST, port=_KANBOARD_DB_PORT, dbname=_KANBOARD_DB,
            user=_KANBOARD_DB_USER, password=kb_pass, connect_timeout=5,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT subject, provisioner, provisioner_type, idp, idp_config, "
                    "issued_by, template, template_eku, grant_name AS grant, "
                    "archive_ref AS archive, vouched_by, delegation_spn, service_relation "
                    "FROM staff_archive_handovers WHERE subject = %s",
                    (subject,),
                )
                row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def _support_db_password() -> str:
    return _SUPPORT_DB_PASSWORD_FILE.read_text().strip()


def _get_note_body(osticket_title: str) -> str | None:
    try:
        conn = pymysql.connect(
            host=SUPPORT_DB_HOST,
            port=SUPPORT_DB_PORT,
            db=SUPPORT_DB_NAME,
            user=SUPPORT_DB_USER,
            password=_support_db_password(),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
        )
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT et.body FROM ost_thread_entry et
                    JOIN ost_thread t ON et.thread_id = t.id
                    JOIN ost_ticket tk
                      ON t.object_id = tk.ticket_id AND t.object_type = 'T'
                    WHERE et.type = 'N'
                      AND et.title = %s
                    ORDER BY et.id DESC LIMIT 1
                    """,
                    (osticket_title,),
                )
                row = cur.fetchone()
        return row["body"] if row else None
    except Exception:
        return None


class StaffHandler(KeplerHandler):
    def _developer(self) -> bool:
        return self.basic_or_bearer(USERNAME, TOKEN)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path

        if path == "/health":
            self.send_json(200, {"status": "up"})
            return

        if path == "/.well-known/fieldkest-client":
            docs = json.loads(Path("/opt/fieldkest/client_documents.json").read_text())
            self.send_json(200, docs["documents"]["staff.keplerops.test"])
            return

        if path == "/api/service-directory":
            if not self._developer():
                self.send_json(401, {"error": "unauthorized"})
                return
            directory = {
                "restricted_note": CONFIG["restricted_note"],
                "support_registration": CONFIG["support_registration"],
            }
            append_audit(AUDIT, "directory", {"action": "read", "peer": self.client_address[0]})
            self.send_json(200, directory)
            return

        if path.startswith("/api/notes/"):
            note_id = path.removeprefix("/api/notes/")
            if not self._developer():
                self.send_json(401, {"error": "unauthorized"})
                return
            meta = NOTES.get(note_id)
            if not meta:
                self.send_json(404, {"error": "not_found"})
                return
            body = _get_note_body(meta["osticket_title"])
            if body is None:
                self.send_json(503, {"error": "note_unavailable"})
                return
            note = {
                "note_id": note_id,
                "consumer": meta["consumer"],
                "status": meta["status"],
                "restricted": meta["restricted"],
                "content": body,
                "flag": "FLAG{3177559b5e2a80d8}",
            }
            append_audit(AUDIT, "note", {"action": "read", "note_id": note_id, "peer": self.client_address[0]})
            self.send_json(200, note)
            return

        # K19.1: mTLS-protected archive handover route.
        # nginx has verified the client cert against the enrollment root CA
        # and passes the verified DN as a header. k-staff binds to the cert subject.
        if path.startswith("/api/archive/handovers/"):
            subject = path.removeprefix("/api/archive/handovers/")
            if not subject or "/" in subject:
                self.send_json(400, {"error": "invalid_subject"})
                return
            client_verified = self.headers.get("X-Client-Cert-Verified", "")
            client_dn = self.headers.get("X-Client-Cert-DN", "")
            if client_verified != "SUCCESS":
                self.send_json(401, {"error": "client_cert_required"})
                return
            # Extract CN from the verified DN (e.g. "CN=rowan.ito@keplerops.test")
            import re as _re
            cn_match = _re.search(r"(?:^|,|/)CN=([^,/]+)", client_dn)
            cert_cn = cn_match.group(1).strip() if cn_match else ""
            if not cert_cn or cert_cn != subject:
                self.send_json(403, {"error": "subject_mismatch"})
                return
            handover = _get_archive_handover(subject)
            if handover is None:
                self.send_json(404, {"error": "handover_not_found"})
                return
            append_audit(AUDIT, "archive-handover", {
                "action": "read", "subject": subject, "cert_dn": client_dn,
                "peer": self.client_address[0],
            })
            self.send_json(200, handover)
            return


        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path

        if path == "/api/note-preview":
            if not self._developer():
                self.send_json(401, {"error": "unauthorized"})
                return
            try:
                body = self.read_json(maximum_bytes=4096)
            except Exception:
                self.send_json(400, {"error": "bad_request"})
                return
            source_path = body.get("source_path", "")
            method = body.get("method", "GET")
            if method not in ("GET", "PATCH"):
                self.send_json(400, {"error": "unsupported_method"})
                return
            # Validate raw path starts with /notes/ before any decoding.
            if not source_path.startswith("/notes/"):
                self.send_json(400, {"error": "invalid_source_path"})
                return
            # Decode and normalize — allows %2e%2e traversal out of /notes/.
            resolved = posixpath.normpath(unquote(source_path))
            # First segment names the target service; remainder is the path.
            # /identity/api/... → identity.keplerops.test/api/...
            parts = resolved.lstrip("/").split("/", 1)
            if len(parts) < 2 or not parts[0] or not parts[1]:
                self.send_json(400, {"error": "invalid_resolved_path"})
                return
            service_host = parts[0] + ".keplerops.test"
            service_path = "/" + parts[1]
            target_url = f"https://{service_host}{service_path}"
            if method == "PATCH":
                # K18.3: participant supplies provider.metadata_uri in the body.
                # k-staff DCR PUTs request_uris=[metadata_uri] to Keycloak using the RAT.
                metadata_uri = body.get("provider", {}).get("metadata_uri", "")
                if not metadata_uri:
                    self.send_json(400, {"error": "provider_metadata_uri_required"})
                    return
                status, data = _patch_registration(target_url, _get_rat(), metadata_uri)
            else:
                req = Request(target_url, method=method)
                req.add_header("Authorization", f"Bearer {_get_rat()}")
                try:
                    status, data = open_json(req, _outbound_ctx(), timeout=10)
                except UpstreamUnavailable:
                    self.send_json(502, {"error": "identity_unavailable"})
                    return
                # Capture rotated RAT from Keycloak GET response
                if "registration_access_token" in data:
                    _update_rat(data["registration_access_token"])
            append_audit(AUDIT, "note-preview", {
                "action": "proxy", "source_path": source_path,
                "resolved": resolved, "target": target_url, "method": method,
                "peer": self.client_address[0],
            })
            self.send_json(status, data)
            return

        # K20.2: SPNEGO-protected managed-identity session route.
        # k-staff-spnego verifies the SPNEGO token and passes the authenticated
        # Kerberos principal via X-Negotiated-Principal header.
        if path.startswith("/api/managed-identities/") and path.endswith("/session"):
            service_id = path.removeprefix("/api/managed-identities/").removesuffix("/session")
            if not service_id or "/" in service_id:
                self.send_json(400, {"error": "invalid_service_id"})
                return
            negotiated_principal = self.headers.get("X-Negotiated-Principal", "")
            if not negotiated_principal:
                self.send_json(401, {"error": "spnego_required"})
                return
            # ACL: check caller's service_relation but NOT the requested managed identity (the flaw)
            caller_email = negotiated_principal.replace("@KEPLEROPS.TEST", "@keplerops.test")
            caller_relation = _get_archive_handover(caller_email)
            if caller_relation is None or caller_relation.get("service_relation") != service_id:
                self.send_json(403, {"error": "managed_identity_denied"})
                return
            admin_url = f"https://{REGISTRY_HOST}/api/release-administration/session"
            session = {
                "principal": service_id,
                "audience": "registry-release-administration",
                "token": RELEASE_ADMIN_TOKEN,
                "administration": admin_url,
            }
            append_audit(AUDIT, "managed-session", {
                "action": "issue", "service_id": service_id,
                "principal": negotiated_principal, "peer": self.client_address[0],
            })
            self.send_json(201, session)
            return

        # K19.3: mTLS-protected archive delegation probe.
        # Accepts an mTLS-authenticated user (evan's cert) and issues a Kerberos
        # credential cache for the requested SPN.
        # Flaw: allowlist checks service CLASS only, not host — arbitrary host ticket.
        if path == "/api/archive/delegation/probe":
            client_verified = self.headers.get("X-Client-Cert-Verified", "")
            client_dn = self.headers.get("X-Client-Cert-DN", "")
            if client_verified != "SUCCESS":
                self.send_json(401, {"error": "client_cert_required"})
                return
            try:
                body = self.read_json(maximum_bytes=4096)
            except Exception:
                self.send_json(400, {"error": "bad_request"})
                return
            spn = body.get("spn", "")
            if not spn:
                self.send_json(400, {"error": "spn_required"})
                return
            # Allowlist: only checks service class (the flaw — omits host).
            allowed_classes = CONFIG.get("kerberos_allowed_service_classes", ["HTTP"])
            service_class = spn.split("/")[0] if "/" in spn else ""
            if service_class not in allowed_classes:
                self.send_json(403, {"error": "spn_class_denied"})
                return
            # Extract subject from cert CN to identify the Kerberos principal.
            import re as _re
            cn_match = _re.search(r"(?:^|,|/)CN=([^,/]+)", client_dn)
            user_email = cn_match.group(1).strip() if cn_match else ""
            kerberos_principal = user_email.replace("@keplerops.test", "") + "@" + CONFIG.get("kerberos_realm", "KEPLEROPS.TEST")
            # Get user password from kerberos.json (operator file, not participant-readable).
            try:
                import json as _json
                _kb_file = Path(os.environ.get("KERBEROS_USERS_FILE", "/run/fieldkest-staff/kerberos-users.json"))
                _kb_users = _json.loads(_kb_file.read_text())
                user_name = kerberos_principal.split("@")[0]
                user_password = _kb_users.get("users", {}).get(user_name, "")
            except Exception:
                self.send_json(503, {"error": "credential_unavailable"})
                return
            if not user_password:
                self.send_json(403, {"error": "user_not_found"})
                return
            # kinit + kvno using subprocess inside the container.
            import subprocess, tempfile, base64 as _b64
            with tempfile.NamedTemporaryFile(suffix=".ccache", delete=False) as ccache_f:
                ccache_path = ccache_f.name
            try:
                kinit = subprocess.run(
                    ["kinit", "-c", ccache_path, kerberos_principal],
                    input=user_password.encode(), capture_output=True, timeout=10,
                )
                if kinit.returncode != 0:
                    self.send_json(502, {"error": "kerberos_auth_failed"})
                    return
                kvno = subprocess.run(
                    ["kvno", "-c", ccache_path, spn],
                    capture_output=True, timeout=10,
                )
                if kvno.returncode != 0:
                    self.send_json(502, {"error": "ticket_request_failed"})
                    return
                ccache_data = Path(ccache_path).read_bytes()
            except Exception:
                self.send_json(502, {"error": "delegation_failed"})
                return
            finally:
                try:
                    Path(ccache_path).unlink(missing_ok=True)
                except Exception:
                    pass
            append_audit(AUDIT, "archive-delegation", {
                "action": "delegate", "user": kerberos_principal, "spn": spn,
                "cert_dn": client_dn, "peer": self.client_address[0],
            })
            self.send_json(201, {
                "authentication": "SPNEGO",
                "credential_cache": _b64.b64encode(ccache_data).decode(),
            })
            return

        self.send_json(404, {"error": "not_found"})


if __name__ == "__main__":
    serve_tls(StaffHandler)
