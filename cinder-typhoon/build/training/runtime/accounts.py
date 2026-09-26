#!/usr/bin/env python3
"""Identity desk service for the Training segment."""

from __future__ import annotations

from collections import defaultdict, deque
from http.cookies import SimpleCookie
import json
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import urlsplit

from http_support import TrainingHandler, append_audit, rooted, serve, utc_now


PUBLIC = rooted("/srv/cinder-accounts/public")
PRIVATE = rooted("/var/lib/cinder-accounts")
AUDIT = PRIVATE / "audit"
SESSIONS = PRIVATE / "sessions"
REDEEMED = SESSIONS / "redeemed.json"
SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
LOCK = threading.Lock()
LOOKUPS: dict[str, deque[float]] = defaultdict(deque)

STATIC = {
    "/": (PUBLIC / "index.md", "text/markdown; charset=utf-8"),
    "/candidates.md": (PUBLIC / "candidates.md", "text/markdown; charset=utf-8"),
    "/directory/": (PUBLIC / "directory/index.json", "application/json"),
    "/directory/app.js": (PUBLIC / "directory/app.js", "text/javascript; charset=utf-8"),
    "/api/directory/staff": (PUBLIC / "directory/index.json", "application/json"),
}


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


class AccountsHandler(TrainingHandler):
    def do_HEAD(self) -> None:
        parsed = urlsplit(self.path)
        item = STATIC.get(parsed.path)
        if item and parsed.path != "/api/directory/staff":
            self.send_file(*item)
        elif item:
            self.method_not_allowed(("GET",))
        else:
            self.send_json(404, {"error": "not_found"})

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        item = STATIC.get(path)
        if item:
            self.send_file(*item)
            return
        if path.startswith("/api/directory/staff/") and path.endswith("/assignment"):
            self._directory_assignment(path)
            return
        if path == "/api/handover":
            self._handover()
            return
        if path == "/api/assignments":
            self._assignments()
            return
        if path.startswith("/api/assignments/") and path.endswith("/brief"):
            self._assignment_brief(path)
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/recovery/lookup":
            self._lookup()
            return
        if path == "/api/recovery/redeem":
            self._redeem()
            return
        self.send_json(404, {"error": "not_found"})

    def do_PUT(self) -> None:
        self.method_not_allowed(("GET", "HEAD", "POST"))

    def do_DELETE(self) -> None:
        self.do_PUT()

    def _json_body(self, fields: set[str]) -> dict[str, object] | None:
        try:
            value = json.loads(self.read_body().decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, OverflowError):
            return None
        if not isinstance(value, dict) or set(value) != fields:
            return None
        return value

    def _directory_assignment(self, path: str) -> None:
        staff_id = path.removeprefix("/api/directory/staff/").removesuffix("/assignment")
        revision = None
        if staff_id == "STF-204":
            status = 200
            response = read_json(PRIVATE / "directory/assignment-STF-204.json")
            revision = response["staff_record_revision"]
        elif staff_id == "STF-317":
            status, response = 403, {"error": "directory_detail_denied"}
        else:
            status, response = 404, {"error": "staff_not_found"}
        append_audit(AUDIT, "directory", {"staff_id": staff_id, "staff_record_revision": revision, "status": status})
        self.send_json(status, response)

    def _lookup(self) -> None:
        body = self._json_body({"account"})
        if body is None or not isinstance(body["account"], str):
            self.send_json(400, {"error": "invalid_request"})
            return
        now = time.monotonic()
        client = self.client_address[0]
        with LOCK:
            recent = LOOKUPS[client]
            while recent and recent[0] <= now - 60:
                recent.popleft()
            if len(recent) >= 6:
                self.send_json(429, {"error": "rate_limited"})
                return
            recent.append(now)
        account = body["account"]
        if account == "rhea.moss":
            status, response, response_class = 200, {"account": account, "state": "active", "case_fragment": "CASE-7Q4M"}, "active"
        elif account == "mina.cho":
            status, response, response_class = 410, {"account": account, "state": "inactive"}, "inactive"
        else:
            status, response, response_class = 404, {"state": "unknown"}, "unknown"
        append_audit(AUDIT, "lookup", {"submitted_account": account, "response_class": response_class, "status": status})
        self.send_json(status, response)

    def _redeem(self) -> None:
        body = self._json_body({"account", "case_fragment", "staff_detail"})
        if body is None or not all(isinstance(value, str) for value in body.values()):
            self.send_json(400, {"error": "invalid_request"})
            return
        matches = [body["account"], body["case_fragment"], body["staff_detail"]] == ["rhea.moss", "CASE-7Q4M", "Blue cabinet 17"]
        subject = None
        token = None
        with LOCK:
            if not matches:
                status, response = 403, {"error": "recovery_denied"}
            elif REDEEMED.exists():
                status, response = 409, {"error": "already_redeemed"}
            else:
                token = secrets.token_urlsafe(32)
                subject = "rhea.moss"
                write_json_atomic(SESSIONS / f"{token}.json", {"subject": subject, "created_at": utc_now()})
                write_json_atomic(REDEEMED, {"account": subject, "redeemed_at": utc_now()})
                status, response = 201, {"subject": subject, "session": token}
        append_audit(AUDIT, "recovery", {"account": body["account"], "factor_match": matches, "session_subject": subject, "status": status})
        headers = None
        if token:
            headers = {"Set-Cookie": f"CINDER_REHEARSAL_SESSION={token}; Path=/; HttpOnly; SameSite=Strict"}
        self.send_json(status, response, headers=headers)

    def _session_subject(self) -> str | None:
        token = None
        authorization = self.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ")
        else:
            cookie = SimpleCookie()
            cookie.load(self.headers.get("Cookie", ""))
            if "CINDER_REHEARSAL_SESSION" in cookie:
                token = cookie["CINDER_REHEARSAL_SESSION"].value
        if not token or not SESSION_PATTERN.fullmatch(token):
            return None
        path = SESSIONS / f"{token}.json"
        if not path.is_file():
            return None
        value = read_json(path)
        return value.get("subject") if isinstance(value, dict) else None

    def _handover(self) -> None:
        subject = self._session_subject()
        if subject is None:
            self.send_json(401, {"error": "session_required"})
            return
        if subject != "rhea.moss":
            status = 403
            self.send_json(status, {"error": "handover_denied"})
        else:
            status = 200
            self.send_file(PRIVATE / "handovers/rhea.moss.md", "text/markdown; charset=utf-8")
        append_audit(AUDIT, "handover", {"session_subject": subject, "document_subject": "rhea.moss", "status": status})

    def _assignments(self) -> None:
        subject = self._session_subject()
        if subject is None:
            self.send_json(401, {"error": "session_required"})
            return
        rows = []
        for path in sorted((PRIVATE / "assignments").glob("*.json")):
            value = read_json(path)
            if value["owner"] == subject:
                rows.append({key: value[key] for key in ("assignment_id", "owner", "revision", "title", "paired_assignment_id") if key in value})
        self.send_json(200, {"assignments": rows})

    def _assignment_brief(self, path: str) -> None:
        subject = self._session_subject()
        if subject is None:
            self.send_json(401, {"error": "session_required"})
            return
        assignment_id = path.removeprefix("/api/assignments/").removesuffix("/brief")
        selected = PRIVATE / "assignments" / f"{assignment_id}.json"
        if not selected.is_file() or assignment_id not in ("ASG-204", "ASG-317"):
            status, response, revision = 404, {"error": "assignment_not_found"}, None
        else:
            status, response = 200, read_json(selected)
            revision = response["revision"]
        append_audit(AUDIT, "assignments", {"session_subject": subject, "assignment_id": assignment_id, "document_revision": revision, "status": status})
        self.send_json(status, response)


def main() -> None:
    SESSIONS.mkdir(parents=True, exist_ok=True, mode=0o700)
    AUDIT.mkdir(parents=True, exist_ok=True, mode=0o700)
    serve(AccountsHandler, [8080])


if __name__ == "__main__":
    main()
