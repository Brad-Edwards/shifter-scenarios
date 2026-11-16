"""FieldKest preview queue service.

Wraps Gotenberg for document rendering and provides the K10 preview
association, document identity, and queue management routes.
"""
from __future__ import annotations

import hashlib
import http.client as _hc
import http.server
import json
import os
from pathlib import Path
import threading
import uuid
from urllib.parse import urlsplit, parse_qs

from http_support import KeplerHandler, append_audit, serve_tls
from credentials import credential

STATE = Path(os.environ.get("FIELDKEST_STATE_ROOT", "/var/lib/fieldkest-preview"))
AUDIT = STATE / "audit"
RESULTS = STATE / "results"
CONFIG = json.loads((STATE / "config/preview.json").read_text())

USERNAME = CONFIG["developer"]["username"]
TOKEN = credential("developer_token")
GOTENBERG_PORT = int(os.environ.get("GOTENBERG_PORT", "3000"))
INTERNAL_PORT = int(os.environ.get("INTERNAL_PORT", "9000"))

# Track which document_ids were accessed by Chromium via the internal server
_internal_access_log: dict[str, list[dict]] = {}
_internal_access_lock = threading.Lock()


class InternalPreviewHandler(http.server.BaseHTTPRequestHandler):
    """Internal-only HTTP server reachable by Chromium but not by participants directly.

    Serves:
    - GET /protected-preview/{document_id} — K10.3: protected document content (SSRF)
    - GET /review-session/{review_id} — K12.2: review session page that postMessages
      the action_nonce without validating the recipient's origin (the vulnerability)

    Participants cannot reach this server directly (loopback only, not published by Docker).
    Only Chromium running inside the container can reach 127.0.0.1:{INTERNAL_PORT}.
    """
    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path.startswith("/protected-preview/"):
            self._serve_protected_preview(path.removeprefix("/protected-preview/"))
        elif path.startswith("/review-session/"):
            self._serve_review_session(path.removeprefix("/review-session/"))
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_protected_preview(self, document_id: str) -> None:
        protected_html, protected_meta = _load_protected_document(document_id)
        if protected_html is None:
            self.send_response(404)
            self.end_headers()
            return
        access_id = str(uuid.uuid4())
        with _internal_access_lock:
            if document_id not in _internal_access_log:
                _internal_access_log[document_id] = []
            _internal_access_log[document_id].append({
                "access_id": access_id,
                "protected_source_id": protected_meta.get("source_id"),
                "protected_case_id": protected_meta.get("case_id"),
                "owner": protected_meta.get("owner"),
                "version": protected_meta.get("version"),
            })
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(protected_html)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(protected_html)

    def _serve_review_session(self, review_id: str) -> None:
        """K12.2 vulnerability: postMessage sends action_nonce without origin validation.

        In the in-world narrative, the privileged reviewer's browser session hosts
        this page. It sends the per-review action nonce to any parent frame via
        postMessage with targetOrigin="*" — no sender-origin check. A same-origin
        frame (the participant's crafted content from K12.1) can intercept it.
        """
        review = _load_review(review_id)
        if review is None or not review.get("action_nonce"):
            self.send_response(404)
            self.end_headers()
            return
        nonce = review["action_nonce"]
        # The vulnerability: postMessage with targetOrigin="*" — any parent receives it
        session_html = f"""<!DOCTYPE html>
<html><head><title>Privileged Review Session</title></head>
<body>
<p>Privileged reviewer session: {review_id}</p>
<script>
// Sends the per-review action nonce to the parent frame without validating the recipient origin.
// Any same-origin parent frame that hosts this page as an iframe will receive this message.
window.parent.postMessage({{ action_nonce: "{nonce}", review_id: "{review_id}" }}, "*");
</script>
</body></html>""".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(session_html)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(session_html)

    def log_message(self, *args: object) -> None:
        pass


def _start_internal_server() -> None:
    """Start the internal-only HTTP server in a background thread."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", INTERNAL_PORT), InternalPreviewHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()


def _derive_document_id(source_url: str) -> str:
    """Derive a document identity from the canonicalized source URL.

    Canonicalization: lowercase + strip trailing slash.  This is the K10.2
    vulnerability: two inputs differing only in case or trailing slash collapse
    to the same form and produce the same document identity.
    """
    canonical = source_url.lower().rstrip("/")
    return "DOC-" + hashlib.sha256(canonical.encode()).hexdigest()[:16].upper()


def _load_association(source_id: str) -> dict | None:
    """Load a source attachment association from state."""
    path = STATE / "associations" / f"{source_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def _load_review(review_id: str) -> dict | None:
    """Load a preview review record from state."""
    path = STATE / "reviews" / f"{review_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def _save_review(review_id: str, record: dict) -> None:
    """Persist an updated review record."""
    (STATE / "reviews").mkdir(parents=True, exist_ok=True)
    path = STATE / "reviews" / f"{review_id}.json"
    path.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _load_protected_document(document_id: str):
    """Load the protected document content and metadata for the given document_id."""
    doc_dir = STATE / "protected" / document_id
    html_path = doc_dir / "document.html"
    meta_path = doc_dir / "meta.json"
    if not html_path.is_file() or not meta_path.is_file():
        return None, None
    return html_path.read_bytes(), json.loads(meta_path.read_text())


def _render_html_via_gotenberg(html_content: bytes) -> bytes:
    """Send HTML to Gotenberg and return the rendered PDF bytes."""
    boundary = uuid.uuid4().hex
    body = (
        b"--" + boundary.encode() + b"\r\n"
        b'Content-Disposition: form-data; name="files"; filename="index.html"\r\n'
        b"Content-Type: text/html\r\n\r\n"
        + html_content +
        b"\r\n--" + boundary.encode() + b"\r\n"
        b'Content-Disposition: form-data; name="waitForExpression"\r\n\r\n'
        b"window._renderComplete === true"
        b"\r\n--" + boundary.encode() + b"--\r\n"
    )
    conn = _hc.HTTPConnection("127.0.0.1", GOTENBERG_PORT, timeout=20)
    conn.request("POST", "/forms/chromium/convert/html", body=body,
                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    resp = conn.getresponse()
    result = resp.read()
    conn.close()
    if resp.status != 200:
        raise RuntimeError(f"gotenberg render failed: {resp.status}: {result[:200]!r}")
    return result


def _action_nonce_bearer(handler: "PreviewHandler") -> str | None:
    """Extract the Bearer token from Authorization header (action nonce, not developer token)."""
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


class PreviewHandler(KeplerHandler):
    def _developer(self) -> bool:
        return self.basic_or_bearer(USERNAME, TOKEN)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/.well-known/fieldkest-client":
            inventory = json.loads(Path("/opt/fieldkest-preview/client_documents.json").read_text())
            self.send_json(200, inventory["documents"]["preview.keplerops.test"])
            return
        if path == "/health":
            self.send_json(200, {"status": "up", "queue": "ready"})
            return
        if not self._developer():
            self.send_json(401, {"error": "authentication_required"})
            return
        query = parse_qs(urlsplit(self.path).query)
        # GET /api/preview/reviews/{review_id} — read review state (evidence for K12.1)
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "preview"] and parts[2] == "reviews":
            review_id = parts[3]
            review = _load_review(review_id)
            if review is None:
                self.send_json(404, {"error": "review_not_found"})
                return
            self.send_json(200, review)
            return
        if path == "/api/preview/association":
            source_id = query.get("source", [""])[0]
            if not source_id:
                self.send_json(422, {"error": "source_required"})
                return
            association = _load_association(source_id)
            if association is None:
                self.send_json(404, {"error": "association_not_found"})
                return
            result_id = "ASSOC-" + uuid.uuid4().hex[:10].upper()
            result = {
                "schema": "fieldkest.preview-association/v1",
                "result_id": result_id,
                "source_id": source_id,
                "document_id": association["document_id"],
                "source_version": association["source_version"],
                "case_id": association["case_id"],
                "owner": association["owner"],
            }
            if "viewer_request" in association:
                result["viewer_request"] = association["viewer_request"]
            append_audit(AUDIT, "preview-associations", {
                "request_id": self.request_id, "principal": USERNAME,
                "source_id": source_id, "document_id": association["document_id"],
                "case_id": association["case_id"], "result_id": result_id, "status": 200,
            })
            RESULTS.mkdir(parents=True, exist_ok=True)
            (RESULTS / f"{result_id}.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
            self.send_json(200, result)
        else:
            self.send_json(404, {"error": "not_found"})

    def do_PATCH(self) -> None:
        path = urlsplit(self.path).path
        if not self._developer():
            self.send_json(401, {"error": "authentication_required"})
            return
        # K12.1: vulnerable assignment route.
        # The queue ownership check omits submitter on reassignment — the service
        # does not verify that the requesting principal owns the review. Any
        # authenticated developer can place their content into the privileged queue.
        parts = path.strip("/").split("/")
        if len(parts) == 5 and parts[:2] == ["api", "preview"] and parts[2] == "reviews" and parts[4] == "assignment":
            review_id = parts[3]
            try:
                body = self.read_json(32_768)
                queue = str(body.get("queue", ""))
                source_id = str(body.get("source_id", ""))
                if queue != "privileged-review" or not source_id:
                    raise ValueError("queue_and_source_required")
            except (ValueError, TypeError, KeyError):
                self.send_json(422, {"error": "queue_and_source_required"})
                return
            review = _load_review(review_id)
            if review is None:
                self.send_json(404, {"error": "review_not_found"})
                return
            # Vulnerability: no ownership check — the participant can reassign
            # a review they do not own to the privileged queue.
            action_nonce = uuid.uuid4().hex
            review["queue"] = queue
            review["source_id"] = source_id
            review["state"] = "loaded"
            review["action_nonce"] = action_nonce
            review["assigned_by"] = USERNAME
            _save_review(review_id, review)
            # Real audit: the participant made a BOLA assignment — no reviewer
            # worker exists yet; the evidence is the persisted review state.
            append_audit(AUDIT, "review-assignments", {
                "request_id": self.request_id, "principal": USERNAME,
                "review_id": review_id, "source_id": source_id,
                "queue": queue, "action_nonce_sha256": hashlib.sha256(action_nonce.encode()).hexdigest(),
                "document_id": review.get("document_id"),
                "original_owner": review.get("owner"),
                "status": 200,
            })
            # Do NOT return action_nonce in the PATCH response.
            # The nonce is a protected browser-context value delivered only via
            # the review session page's postMessage (K12.2 interception target).
            result = {
                "schema": "fieldkest.preview-review-assignment/v1",
                "review_id": review_id,
                "source_id": source_id,
                "queue": queue,
                "state": "loaded",
                "document_id": review.get("document_id"),
            }
            RESULTS.mkdir(parents=True, exist_ok=True)
            result_id = "RVWLD-" + uuid.uuid4().hex[:10].upper()
            (RESULTS / f"{result_id}.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
            self.send_json(200, result)
        else:
            self.send_json(404, {"error": "not_found"})

    def _handle_prepare(self, path: str) -> bool:
        """K12.2: protected prepare action authenticated by action_nonce Bearer token.

        The action_nonce is a one-use value from the K12.1 assignment response.
        In the in-world narrative, the nonce is delivered to same-origin preview
        frames via a postMessage handler that does not validate sender origin.
        The participant captures it via their crafted content and uses it here.
        The prepare action is NOT accessible with the developer credential — only
        the action_nonce (a per-review one-use token) is accepted.
        """
        parts = path.strip("/").split("/")
        if not (len(parts) == 5 and parts[:2] == ["api", "preview"]
                and parts[2] == "reviews" and parts[4] == "prepare"):
            return False
        review_id = parts[3]
        nonce = _action_nonce_bearer(self)
        if not nonce:
            self.send_json(401, {"error": "action_nonce_required"})
            return True
        review = _load_review(review_id)
        if review is None:
            self.send_json(404, {"error": "review_not_found"})
            return True
        stored_nonce = review.get("action_nonce")
        if not stored_nonce or review.get("state") == "prepared":
            # Nonce already consumed or review not in an assignable state
            self.send_json(403, {"error": "nonce_consumed_or_invalid"})
            return True
        if nonce != stored_nonce:
            self.send_json(403, {"error": "invalid_action_nonce"})
            return True
        # Consume nonce and transition review to prepared state
        review["action_nonce"] = None
        review["state"] = "prepared"
        _save_review(review_id, review)
        result_id = "PRVPRP-" + uuid.uuid4().hex[:10].upper()
        result = {
            "schema": "fieldkest.preview-preparation/v1",
            "result_id": result_id,
            "review_id": review_id,
            "source_id": review.get("source_id"),
            "queue": review.get("queue"),
            "prepared": True,
        }
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / f"{result_id}.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
        append_audit(AUDIT, "review-preparations", {
            "request_id": self.request_id,
            "review_id": review_id, "result_id": result_id,
            "source_id": review.get("source_id"),
            "queue": review.get("queue"),
            "nonce_sha256": hashlib.sha256(nonce.encode()).hexdigest(),
            "original_owner": review.get("owner"),
            "status": 200,
        })
        self.send_json(200, result)
        return True

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        # K12.2: prepare action authenticated by action_nonce, not developer token
        if self._handle_prepare(path):
            return
        if not self._developer():
            self.send_json(401, {"error": "authentication_required"})
            return
        if path == "/api/preview/render":
            # K10.3: participant submits crafted HTML. Gotenberg/Chromium renders it.
            # If the HTML makes Chromium fetch the internal protected preview endpoint
            # (http://127.0.0.1:{INTERNAL_PORT}/protected-preview/{document_id}),
            # the internal server records the boundary crossing.
            # The participant cannot reach this endpoint directly — only Chromium can.
            try:
                body = self.read_json(131_072)
                html_content = str(body.get("html", "")).encode("utf-8")
                source_id = str(body.get("source_id", ""))
                document_id = str(body.get("document_id", ""))
                if not html_content:
                    raise ValueError("html_required")
            except (ValueError, TypeError, KeyError):
                self.send_json(422, {"error": "html_and_source_id_required"})
                return
            # Inject the render-complete signal into the participant's HTML
            # (Gotenberg waits for window._renderComplete === true)
            inject = b"\n<script>setTimeout(function(){window._renderComplete=true;}, 2000);</script>"
            if b"</body>" in html_content:
                html_content = html_content.replace(b"</body>", inject + b"</body>")
            else:
                html_content = html_content + inject
            # Clear any previous access log for this document_id
            with _internal_access_lock:
                _internal_access_log.pop(document_id, None)
            # Submit to Gotenberg
            try:
                pdf_bytes = _render_html_via_gotenberg(html_content)
            except (OSError, RuntimeError) as exc:
                self.send_json(503, {"error": f"render_failed: {exc}"})
                return
            render_digest = hashlib.sha256(pdf_bytes).hexdigest()
            result_id = "REND-" + uuid.uuid4().hex[:10].upper()
            # Check if the internal server was accessed (SSRF boundary crossing)
            with _internal_access_lock:
                accesses = _internal_access_log.pop(document_id, [])
            ssrf_confirmed = len(accesses) > 0
            protected_access = accesses[0] if accesses else None
            if ssrf_confirmed and protected_access:
                append_audit(AUDIT, "preview-ssrf-access", {
                    "request_id": self.request_id, "principal": USERNAME,
                    "source_id": source_id, "document_id": document_id,
                    "protected_source_id": protected_access["protected_source_id"],
                    "protected_case_id": protected_access["protected_case_id"],
                    "access_id": protected_access["access_id"],
                    "result_id": result_id, "status": 200,
                })
                append_audit(AUDIT, "protected-content-reads", {
                    "request_id": self.request_id, "principal": USERNAME,
                    "document_id": document_id,
                    "protected_version": protected_access["version"],
                    "render_digest": render_digest,
                    "result_id": result_id, "status": 200,
                })
            result = {
                "schema": "fieldkest.preview-render-result/v1",
                "result_id": result_id,
                "source_id": source_id,
                "document_id": document_id,
                "ssrf_confirmed": ssrf_confirmed,
                "protected_source_id": protected_access["protected_source_id"] if ssrf_confirmed else None,
                "protected_case_id": protected_access["protected_case_id"] if ssrf_confirmed else None,
                "protected_version": protected_access["version"] if ssrf_confirmed else None,
                "owner": protected_access["owner"] if ssrf_confirmed else None,
                "render_digest": render_digest,
                "render_size_bytes": len(pdf_bytes),
            }
            RESULTS.mkdir(parents=True, exist_ok=True)
            (RESULTS / f"{result_id}.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
            self.send_json(200, result)
        elif path == "/api/preview/documents":
            try:
                body = self.read_json(32_768)
                source_url = str(body.get("source", ""))
                source_id = str(body.get("source_id", ""))
                if not source_url:
                    raise ValueError("source_required")
            except (ValueError, TypeError, KeyError):
                self.send_json(422, {"error": "source_required"})
                return
            document_id = _derive_document_id(source_url)
            result_id = "DOCP-" + uuid.uuid4().hex[:10].upper()
            result = {
                "schema": "fieldkest.preview-document/v1",
                "result_id": result_id,
                "source_url": source_url,
                "source_id": source_id,
                "document_id": document_id,
                "canonical_url": source_url.lower().rstrip("/"),
            }
            append_audit(AUDIT, "preview-documents", {
                "request_id": self.request_id, "principal": USERNAME,
                "source_url": source_url, "source_id": source_id,
                "document_id": document_id, "result_id": result_id, "status": 200,
            })
            RESULTS.mkdir(parents=True, exist_ok=True)
            (RESULTS / f"{result_id}.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
            self.send_json(200, result)
        else:
            self.send_json(404, {"error": "not_found"})


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    _start_internal_server()
    serve_tls(PreviewHandler, port=int(os.environ.get("PORT", "443")))


if __name__ == "__main__":
    main()
