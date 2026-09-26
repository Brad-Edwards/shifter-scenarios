"""FieldKest support service for retained conversations and report handovers."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from http_support import KeplerHandler, append_audit, serve_tls


STATE = Path("/var/lib/fieldkest-support")
AUDIT = STATE / "audit"
HANDOVER = Path("/var/lib/fieldkest-handover/current.json")
CONFIG = json.loads((STATE / "config/opening.json").read_text())
SESSION = CONFIG["sessions"][0]
CONVERSATION = json.loads((STATE / "conversations/SUP-2841.json").read_text())


class SupportHandler(KeplerHandler):
    def _authorized(self) -> bool:
        cookies = {}
        for item in self.headers.get("Cookie", "").split(";"):
            name, separator, value = item.strip().partition("=")
            if separator:
                cookies[name] = value
        return cookies.get("fieldkest_support") == SESSION["session_id"]

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if not self._authorized():
            self.send_json(403, {"error": "session_denied"})
            return
        if path == "/api/conversations/SUP-2841":
            append_audit(AUDIT, "conversation", {"request_id": self.request_id, "principal": SESSION["principal"], "conversation_id": "SUP-2841", "revision": CONVERSATION["revision"], "status": 200})
            self.send_json(200, CONVERSATION)
        elif path == "/api/handovers/current":
            if not HANDOVER.is_file():
                self.send_json(404, {"error": "handover_not_available"})
                return
            value = json.loads(HANDOVER.read_text())
            append_audit(AUDIT, "handover", {"request_id": self.request_id, "principal": SESSION["principal"], "job_id": value["job_id"], "report_sha256": value["report_sha256"], "status": 200})
            self.send_json(200, value)
        else:
            self.send_json(404, {"error": "not_found"})


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    serve_tls(SupportHandler)


if __name__ == "__main__":
    main()
