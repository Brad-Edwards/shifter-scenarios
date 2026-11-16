"""k-staff: staff directory, note, and preview service for K18.

K18.1: staff.directory and staff.note routes. Auth is dev bearer.
       Notes are real osTicket internal notes queried from the support DB.
K18.2-K18.3: staff.note-preview SSRF path (deferred — not in this revision).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pymysql
import pymysql.cursors

from http_support import KeplerHandler, append_audit, serve_tls
from credentials import credential

STATE = Path(os.environ.get("FIELDKEST_STATE_ROOT", "/var/lib/fieldkest-staff"))
AUDIT = STATE / "audit"
CONFIG = json.loads((STATE / "config/staff.json").read_text())

USERNAME = CONFIG["developer"]["username"]
TOKEN = credential("developer_token")

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


if __name__ == "__main__":
    serve_tls(StaffHandler)
