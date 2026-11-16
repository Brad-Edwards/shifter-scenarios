"""k-assistant-api: Custom assistant API wrapping AnythingLLM for K21-K24.

K21.1: /api/config — public, exposes context and collection identifiers.
K21.2 (K23.1): /api/contexts — returns workspace contexts including deleted conversations.
       /api/conversations/{conv_id} — returns retained conversation with deleted_from_ui.
K21.3: /api/answers — proxies answer requests to real AnythingLLM/Ollama retrieval.
"""

from __future__ import annotations

import json
import os
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
import socketserver
import ssl
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from http_support import KeplerHandler, append_audit, serve_tls
from credentials import credential

STATE = Path(os.environ.get("FIELDKEST_STATE_ROOT", "/var/lib/fieldkest-assistant-api"))
AUDIT = STATE / "audit"
CONVERSATIONS = json.loads((STATE / "conversations.json").read_text())
CONTEXTS = json.loads((STATE / "contexts.json").read_text())

ANYLLM_BASE = os.environ.get("ANYLLM_BASE", "http://fieldlink-assistant:3001")
ANYLLM_TOKEN = credential("assistant_tool_session")

OPERATORS = {
    credential("support_rowan_session"): "rowan.ito",
    credential("support_reviewer_session"): "talia.mornac",
    credential("assistant_tool_session"): "svc-fieldlink-assistant",
}


def _get_session(cookie_header: str) -> str | None:
    """Return the authenticated username from the support session cookie."""
    cookies = SimpleCookie()
    try:
        cookies.load(cookie_header)
        for name in ("fieldkest_support", "OSTSESSID"):
            if name in cookies:
                return OPERATORS.get(cookies[name].value)
    except CookieError:
        pass
    return None


class AssistantApiHandler(KeplerHandler):
    def do_GET(self) -> None:
        path = urlsplit(self.path).path

        if path == "/health":
            self.send_json(200, {"status": "up"})
            return

        # K23.1: contexts endpoint — public, returns workspace context list.
        if path == "/api/contexts":
            self.send_json(200, {"contexts": CONTEXTS})
            return

        # K21.2: conversation endpoint — requires support session, returns retained conversations.
        if path.startswith("/api/conversations/"):
            conv_id = path.removeprefix("/api/conversations/")
            cookie = self.headers.get("Cookie", "")
            user = _get_session(cookie)
            if user is None:
                self.send_json(403, {"error": "session_required"})
                return
            conv = CONVERSATIONS.get(conv_id)
            if conv is None:
                self.send_json(404, {"error": "conversation_not_found"})
                return
            append_audit(AUDIT, "conversation-read", {
                "action": "read", "conversation_id": conv_id, "user": user,
            })
            self.send_json(200, conv)
            return

        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path

        # K21.3: answers endpoint — proxies to real AnythingLLM/Ollama retrieval.
        if path == "/api/answers":
            cookie = self.headers.get("Cookie", "")
            user = _get_session(cookie)
            if user is None:
                self.send_json(403, {"error": "session_required"})
                return
            try:
                body = self.read_json(maximum_bytes=65536)
            except Exception:
                self.send_json(400, {"error": "bad_request"})
                return
            context_id = body.get("context_id", "")
            question = body.get("question", "")
            conversation_id = body.get("conversation_id", "")
            # Map context_id to AnythingLLM workspace slug
            workspace_map = {c["context_id"]: c.get("workspace_slug") for c in CONTEXTS}
            workspace_slug = workspace_map.get(context_id)
            if not workspace_slug:
                self.send_json(404, {"error": "context_not_found"})
                return
            # Find the real AnythingLLM thread for this conversation
            thread_map = {c["context_id"]: c.get("answer_thread") for c in CONTEXTS}
            thread_slug = thread_map.get(context_id, "default")
            # Proxy to real AnythingLLM chat
            chat_url = f"{ANYLLM_BASE}/api/workspace/{workspace_slug}/thread/{thread_slug}/chat"
            chat_body = json.dumps({"message": question, "mode": "query"}).encode()
            req = Request(chat_url, data=chat_body, headers={
                "Authorization": f"Bearer {ANYLLM_TOKEN}",
                "Content-Type": "application/json",
            })
            try:
                with urlopen(req, timeout=120) as r:
                    result = json.load(r)
                    answer = result.get("textResponse", "")
                    sources = result.get("sources", [])
            except Exception as e:
                self.send_json(502, {"error": "retrieval_failed"})
                return
            append_audit(AUDIT, "answer-request", {
                "action": "answer", "context_id": context_id, "user": user,
                "conversation_id": conversation_id,
            })
            self.send_json(200, {
                "answer": answer,
                "sources": sources,
                "context_id": context_id,
                "conversation_id": conversation_id,
            })
            return

        self.send_json(404, {"error": "not_found"})


if __name__ == "__main__":
    serve_tls(AssistantApiHandler)
