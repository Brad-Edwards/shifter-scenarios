"""k-staff: staff directory, note, and preview service for K18.

K18.1: staff.directory and staff.note routes. Auth is dev bearer.
       Notes are real osTicket internal notes queried from the support DB.
K18.2-K18.3: staff.note-preview SSRF path. Validates raw /notes/ prefix before
       URL-decoding, then makes an outbound request to the resolved target using
       the staff_preview_service bearer. The traversal reaches the identity
       registration endpoint.
"""
from __future__ import annotations

import json
import os
import posixpath
import ssl
from pathlib import Path
from urllib.parse import unquote, urlsplit
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
PREVIEW_SERVICE_TOKEN = credential("staff_preview_service")
IDENTITY_HOST = CONFIG.get("identity_host", "identity.keplerops.test")

_CA_CERT = Path(os.environ.get("FIELDKEST_CA_CERT", "/run/fieldkest-tls/ca.crt"))


def _outbound_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=str(_CA_CERT))
    return ctx

SUPPORT_DB_HOST = CONFIG.get("support_db_host", "fieldlink-support-db")
SUPPORT_DB_PORT = int(CONFIG.get("support_db_port", 3306))
SUPPORT_DB_NAME = CONFIG.get("support_db", "fieldlink_support")
SUPPORT_DB_USER = CONFIG.get("support_db_user", "fieldlink_support")
_SUPPORT_DB_PASSWORD_FILE = Path(
    os.environ.get("SUPPORT_DB_PASSWORD_FILE", "/run/fieldkest-staff/support_db_password")
)

NOTES = CONFIG.get("notes", {})


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
            }
            append_audit(AUDIT, "note", {"action": "read", "note_id": note_id, "peer": self.client_address[0]})
            self.send_json(200, note)
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
            req = Request(target_url, method=method)
            req.add_header("Authorization", f"Bearer {PREVIEW_SERVICE_TOKEN}")
            if method == "PATCH":
                req.add_header("Content-Length", "0")
            try:
                status, data = open_json(req, _outbound_ctx(), timeout=10)
            except UpstreamUnavailable:
                self.send_json(502, {"error": "identity_unavailable"})
                return
            append_audit(AUDIT, "note-preview", {
                "action": "proxy", "source_path": source_path,
                "resolved": resolved, "target": target_url, "method": method,
                "peer": self.client_address[0],
            })
            self.send_json(status, data)
            return

        self.send_json(404, {"error": "not_found"})


if __name__ == "__main__":
    serve_tls(StaffHandler)
