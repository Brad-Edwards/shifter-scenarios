"""FieldKest preview queue service.

Wraps Gotenberg for document rendering and provides the K10 preview
association, document identity, and queue management routes.
K12: privileged review queue assignment, prepare, and render endpoints.
"""
from __future__ import annotations

import hashlib
import http.client as _hc
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

# K12: in-memory review state (loaded from STATE/reviews/*.json at startup)
_REVIEWS: dict[str, dict] = {}
_REVIEWS_LOCK = threading.Lock()
_REVIEW_NONCES: dict[str, str] = {}  # review_id -> action_nonce

def _load_reviews() -> None:
    reviews_dir = STATE / "reviews"
    if not reviews_dir.is_dir():
        return
    for path in reviews_dir.glob("*.json"):
        try:
            d = json.loads(path.read_text())
            _REVIEWS[d["review_id"]] = dict(d)
        except Exception:
            pass

_load_reviews()


def _render_html_via_gotenberg(html_content: bytes) -> bytes:
    """Send HTML to Gotenberg and return the rendered PDF bytes."""
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="index.html"\r\n'
        f"Content-Type: text/html\r\n\r\n"
    ).encode() + html_content + f"\r\n--{boundary}--\r\n".encode()
    conn = _hc.HTTPConnection("127.0.0.1", GOTENBERG_PORT, timeout=15)
    conn.request("POST", "/forms/chromium/convert/html", body=body,
                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    resp = conn.getresponse()
    result = resp.read()
    conn.close()
    if resp.status != 200:
        raise RuntimeError(f"gotenberg render failed: {resp.status}")
    return result


def _load_protected_document(document_id: str):
    """Load the protected document content and metadata for the given document_id."""
    doc_dir = STATE / "protected" / document_id
    html_path = doc_dir / "document.html"
    meta_path = doc_dir / "meta.json"
    if not html_path.is_file() or not meta_path.is_file():
        return None, None
    return html_path.read_bytes(), json.loads(meta_path.read_text())


def _derive_document_id(source_url: str) -> str:
    """Derive a document identity from the canonicalized source URL.

    Canonicalization: lowercase + strip trailing slash.  This is the K10.2
    vulnerability: two inputs differing only in case or trailing slash
    collapse to the same canonical form and produce the same document identity.
    """
    canonical = source_url.lower().rstrip("/")
    return "DOC-" + hashlib.sha256(canonical.encode()).hexdigest()[:16].upper()


def _load_association(source_id: str) -> dict | None:
    """Load a source attachment association from state."""
    path = STATE / "associations" / f"{source_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())


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
        if path == "/api/preview/association":
            # K10.1: return the association for the supplied source attachment.
            # The lookup does not verify that the caller owns the case — this is
            # the K10.1 vulnerability.
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
                "owner_case": association.get("owner_case", ""),
                "owner": association["owner"],
            }
            append_audit(AUDIT, "preview-associations", {
                "request_id": self.request_id, "principal": USERNAME,
                "source_id": source_id, "document_id": association["document_id"],
                "case_id": association["case_id"], "result_id": result_id, "status": 200,
            })
            RESULTS.mkdir(parents=True, exist_ok=True)
            (RESULTS / f"{result_id}.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
            if source_id == "SUP-K-2841":
                result["flag"] = "FLAG{e79c34cd2ef12e6e}"
            self.send_json(200, result)
        # K12.1: read a stored render result as a review record
        if path.startswith("/api/preview/reviews/") and not path.endswith("/assignment"):
            result_id = path.removeprefix("/api/preview/reviews/")
            if not self._developer():
                self.send_json(401, {"error": "authentication_required"})
                return
            review_path = RESULTS / f"{result_id}.json"
            if not review_path.is_file():
                self.send_json(404, {"error": "review_not_found"})
                return
            review = json.loads(review_path.read_text())
            if review.get("collision_detected"):
                review["flag"] = "FLAG{3073e7ddb80f48ee}"
            self.send_json(200, review)
            return
        # K12.2: get review assignment
        if path.startswith("/api/preview/reviews/") and path.endswith("/assignment"):
            result_id = path.removeprefix("/api/preview/reviews/").removesuffix("/assignment")
            if not self._developer():
                self.send_json(401, {"error": "authentication_required"})
                return
            review_path = RESULTS / f"{result_id}.json"
            if not review_path.is_file():
                self.send_json(404, {"error": "review_not_found"})
                return
            review = json.loads(review_path.read_text())
            if review.get("collision_detected"):
                self.send_json(200, {
                    "schema": "fieldkest.preview-assignment/v1",
                    "result_id": result_id,
                    "owner": review.get("owner", ""),
                    "protected_case_id": review.get("protected_case_id", ""),
                    "protected_source_id": review.get("protected_source_id", ""),
                    "protected_version": review.get("protected_version", ""),
                    "flag": "FLAG{9d14e5b959bb4bb5}",
                })
                return
            self.send_json(422, {"error": "collision_not_detected"})
            return
        # K12.4: get attachment (viewer's document)
        if path.startswith("/attachment/"):
            source_id = path.removeprefix("/attachment/")
            assoc = _load_association(source_id)
            if assoc is None:
                self.send_json(404, {"error": "attachment_not_found"})
                return
            self.send_json(200, {"source_id": source_id, "document_id": assoc["document_id"],
                                  "source_version": assoc["source_version"]})
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if not self._developer():
            self.send_json(401, {"error": "authentication_required"})
            return
        if path == "/api/preview/render":
            # K10.3: participant uploads their document → renderer uses the document_id
            # collision to serve the PROTECTED document's content via real Gotenberg render.
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
            result_id = "REND-" + uuid.uuid4().hex[:10].upper()
            protected_html, protected_meta = _load_protected_document(document_id)
            if protected_html is None:
                # No protected document at this slot → render normally (no collision)
                self.send_json(404, {"error": "protected_document_not_found"})
                return
            # Collision detected: render the protected document via Gotenberg
            try:
                pdf_bytes = _render_html_via_gotenberg(protected_html)
            except (OSError, RuntimeError) as exc:
                self.send_json(503, {"error": f"render_failed: {exc}"})
                return
            render_digest = hashlib.sha256(pdf_bytes).hexdigest()
            protected_version = protected_meta.get("version", "unknown")
            # Emit collision event and protected-content-read audit
            append_audit(AUDIT, "preview-collision", {
                "request_id": self.request_id, "principal": USERNAME,
                "source_id": source_id, "source_url": source_url,
                "document_id": document_id, "canonical_url": source_url.lower().rstrip("/"),
                "protected_source_id": protected_meta.get("source_id", ""),
                "protected_case_id": protected_meta.get("case_id", ""),
                "result_id": result_id, "status": 200,
            })
            append_audit(AUDIT, "protected-content-reads", {
                "request_id": self.request_id, "principal": USERNAME,
                "document_id": document_id,
                "protected_version": protected_version,
                "render_digest": render_digest,
                "result_id": result_id, "status": 200,
            })
            result = {
                "schema": "fieldkest.preview-render-result/v1",
                "result_id": result_id,
                "source_id": source_id,
                "derived_id": source_id,
                "document_id": document_id,
                "collision_detected": True,
                "protected_source_id": protected_meta.get("source_id", ""),
                "protected_case_id": protected_meta.get("case_id", ""),
                "protected_version": protected_version,
                "render_digest": render_digest,
                "render_size_bytes": len(pdf_bytes),
                "owner": protected_meta.get("owner", ""),
            }
            RESULTS.mkdir(parents=True, exist_ok=True)
            (RESULTS / f"{result_id}.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
            result["flag"] = "FLAG{e4c9623c3e3c146c}"
            self.send_json(200, result)
        elif path.startswith("/api/preview/reviews/") and path.endswith("/prepare"):
            # K12.3: prepare custom preview content in the review
            result_id = path.removeprefix("/api/preview/reviews/").removesuffix("/prepare")
            if not self._developer():
                self.send_json(401, {"error": "authentication_required"})
                return
            try:
                body = self.read_json(32_768)
                content_b64 = body.get("content_base64", "")
                if not content_b64:
                    raise ValueError("content_required")
            except (ValueError, TypeError):
                self.send_json(422, {"error": "content_required"})
                return
            review_path = RESULTS / f"{result_id}.json"
            if not review_path.is_file():
                self.send_json(404, {"error": "review_not_found"})
                return
            review = json.loads(review_path.read_text())
            if not review.get("collision_detected"):
                self.send_json(422, {"error": "collision_not_detected"})
                return
            prepare_path = RESULTS / f"prepare-{result_id}.json"
            prepare_id = "PREP-" + uuid.uuid4().hex[:10].upper()
            prepare = {
                "schema": "fieldkest.preview-prepare/v1",
                "prepare_id": prepare_id,
                "result_id": result_id,
                "content_sha256": hashlib.sha256(content_b64.encode()).hexdigest(),
                "flag": "FLAG{7b89fd70e897ed74}",
            }
            prepare_path.write_text(json.dumps(prepare, sort_keys=True, separators=(",", ":")) + "\n")
            append_audit(AUDIT, "preview-prepare", {"request_id": self.request_id, "principal": USERNAME,
                         "result_id": result_id, "prepare_id": prepare_id, "status": 201})
            self.send_json(201, prepare)
            return
        elif path.startswith("/api/preview/release/"):
            # K12.4: complete the preview release chain
            result_id = path.removeprefix("/api/preview/release/")
            if not self._developer():
                self.send_json(401, {"error": "authentication_required"})
                return
            prepare_path = RESULTS / f"prepare-{result_id}.json"
            if not prepare_path.is_file():
                self.send_json(409, {"error": "prepare_required"})
                return
            prepare = json.loads(prepare_path.read_text())
            release_id = "REL-" + uuid.uuid4().hex[:10].upper()
            result = {
                "schema": "fieldkest.preview-release/v1",
                "release_id": release_id,
                "result_id": result_id,
                "prepare_id": prepare.get("prepare_id"),
                "flag": "FLAG{89f65c4ede64fbcc}",
            }
            append_audit(AUDIT, "preview-release", {"request_id": self.request_id, "principal": USERNAME,
                         "result_id": result_id, "release_id": release_id, "status": 201})
            self.send_json(201, result)
            return
        elif path == "/api/preview/documents":
            # K10.2: derive a document identity from the supplied source URL.
            # Canonicalization (lowercase + strip trailing slash) collapses certain
            # pairs of distinct inputs into the same derived identity.
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
            if source_id == "SUP-K-2841":
                result["flag"] = "FLAG{e79c34cd2ef12e6e}"
            elif document_id == "DOC-9BC054D6F95DFA6A":
                result["flag"] = "FLAG{3944ecd601ef90a2}"
            self.send_json(200, result)
        else:
            self.send_json(404, {"error": "not_found"})

    def do_PATCH(self) -> None:
        path = urlsplit(self.path).path
        if not self._developer():
            self.send_json(401, {"error": "authentication_required"})
            return
        # K12.1: PATCH /api/preview/reviews/{review_id}/assignment
        if path.endswith("/assignment") and "/api/preview/reviews/" in path:
            review_id = path.removeprefix("/api/preview/reviews/").removesuffix("/assignment")
            with _REVIEWS_LOCK:
                review = _REVIEWS.get(review_id)
            if review is None:
                self.send_json(404, {"error": "review_not_found"})
                return
            try:
                body = self.read_json(maximum_bytes=4096)
            except Exception:
                self.send_json(400, {"error": "bad_request"})
                return
            queue = body.get("queue", "")
            source_id = body.get("source_id", "")
            # Vulnerability: no ownership check on queue reassignment
            action_nonce = "PRV-NONCE-" + uuid.uuid4().hex[:12].upper()
            with _REVIEWS_LOCK:
                _REVIEWS[review_id] = {**review, "queue": queue, "source_id": source_id, "state": "loaded"}
                _REVIEW_NONCES[review_id] = action_nonce
            append_audit(AUDIT, "review-assignments", {
                "request_id": self.request_id, "review_id": review_id,
                "queue": queue, "source_id": source_id, "principal": USERNAME,
            })
            self.send_json(200, {
                "review_id": review_id, "state": "loaded",
                "queue": queue, "source_id": source_id,
                "action_nonce": action_nonce,
                "flag": "FLAG{3073e7ddb80f48ee}",
            })
            return
        self.send_json(404, {"error": "not_found"})

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            self.send_json(200, {"status": "up"})
            return
        if self.send_client_document():
            return
        if not self._developer():
            self.send_json(401, {"error": "authentication_required"})
            return
        # K10.1: association lookup
        if path == "/api/preview/association":
            query = parse_qs(urlsplit(self.path).query)
            source_id = query.get("source", [None])[0]
            if source_id is None:
                self.send_json(422, {"error": "source_required"})
                return
            assoc_dir = STATE / "associations"
            result_id = "ASSOC-" + uuid.uuid4().hex[:10].upper()
            # Build the document_id from the source (lowercase + strip trailing slash)
            document_id = _derive_document_id(source_id)
            assoc = {
                "schema": "fieldkest.preview-association/v1",
                "result_id": result_id,
                "source_id": source_id,
                "document_id": document_id,
                "case_id": CONFIG.get("case_id", "CAS-MAYA-2841"),
                "owner": "maya.ranscombe",
                "viewer_request": "PRV-771",
                "derived_document_id": document_id,
                "source_version": "cb72f4a8",
            }
            if source_id == "SUP-K-2841":
                assoc["flag"] = "FLAG{e79c34cd2ef12e6e}"
            RESULTS.mkdir(parents=True, exist_ok=True)
            (RESULTS / f"{result_id}.json").write_text(json.dumps(assoc, sort_keys=True, separators=(",", ":")) + "\n")
            append_audit(AUDIT, "preview-associations", {
                "request_id": self.request_id, "source_id": source_id,
                "document_id": document_id, "result_id": result_id, "status": 200,
            })
            self.send_json(200, assoc)
            return
        # K12 review-render: GET /review/{review_id} with bearer="reviewer-worker"
        if path.startswith("/review/"):
            review_id = path.removeprefix("/review/")
            auth = self.headers.get("Authorization", "")
            if auth != "Bearer reviewer-worker":
                self.send_json(403, {"error": "reviewer_worker_required"})
                return
            with _REVIEWS_LOCK:
                review = _REVIEWS.get(review_id)
            if review is None:
                self.send_json(404, {"error": "review_not_found"})
                return
            if review.get("state") != "prepared":
                self.send_json(409, {"error": "review_not_prepared"})
                return
            source_id = review.get("source_id", "")
            # Render via Gotenberg (use simple HTML)
            html = f"<html><body><h1>Review {review_id}</h1><p>Source: {source_id}</p></body></html>".encode()
            try:
                pdf_bytes = _render_html_via_gotenberg(html)
                render_digest = hashlib.sha256(pdf_bytes).hexdigest()
            except Exception:
                render_digest = hashlib.sha256(html).hexdigest()
                pdf_bytes = html
            support_receipt = "PRV-RCPT-" + uuid.uuid4().hex[:8].upper()
            result_id = "RREND-" + uuid.uuid4().hex[:8].upper()
            result = {
                "review_id": review_id,
                "worker_scope": "/review/",
                "renderer_identity": "svc-preview-reviewer",
                "execution_backend": "isolated-container",
                "render_digest": render_digest,
                "source_id": source_id,
                "compatibility_summary": "fieldlink.connector/v3 compatible",
                "support_receipt": support_receipt,
                "original_owner": review.get("owner", "maya.ranscombe"),
            }
            RESULTS.mkdir(parents=True, exist_ok=True)
            (RESULTS / f"{result_id}.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
            append_audit(AUDIT, "review-renders", {
                "request_id": self.request_id, "review_id": review_id,
                "renderer_identity": "svc-preview-reviewer",
                "original_owner": result["original_owner"],
                "source_id": source_id, "render_digest": render_digest,
                "support_receipt": support_receipt, "status": 200,
            })
            result["flag"] = "FLAG{7b89fd70e897ed74}"
            self.send_json(200, result)
            return
        # K12.1: read a stored render result as a review record
        if path.startswith("/api/preview/reviews/") and not path.endswith("/assignment"):
            result_id = path.removeprefix("/api/preview/reviews/")
            review_path = RESULTS / f"{result_id}.json"
            if not review_path.is_file():
                self.send_json(404, {"error": "review_not_found"})
                return
            review = json.loads(review_path.read_text())
            if review.get("collision_detected"):
                review["flag"] = "FLAG{3073e7ddb80f48ee}"
            self.send_json(200, review)
            return
        # K12.2: get review assignment
        if path.startswith("/api/preview/reviews/") and path.endswith("/assignment"):
            result_id = path.removeprefix("/api/preview/reviews/").removesuffix("/assignment")
            review_path = RESULTS / f"{result_id}.json"
            if not review_path.is_file():
                self.send_json(404, {"error": "review_not_found"})
                return
            review = json.loads(review_path.read_text())
            if review.get("collision_detected"):
                self.send_json(200, {
                    "schema": "fieldkest.preview-assignment/v1",
                    "result_id": result_id,
                    "owner": review.get("owner", ""),
                    "protected_case_id": review.get("protected_case_id", ""),
                    "protected_source_id": review.get("protected_source_id", ""),
                    "protected_version": review.get("protected_version", ""),
                    "flag": "FLAG{9d14e5b959bb4bb5}",
                })
                return
            self.send_json(422, {"error": "collision_not_detected"})
            return
        # K12.4: viewer attachment
        if path.startswith("/attachment/"):
            source_id = path.removeprefix("/attachment/")
            assoc = _load_association(source_id)
            if assoc is None:
                self.send_json(404, {"error": "attachment_not_found"})
                return
            self.send_json(200, {"source_id": source_id, "document_id": assoc.get("document_id", ""),
                                  "source_version": assoc.get("source_version", "")})
            return
        self.send_json(404, {"error": "not_found"})


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    serve_tls(PreviewHandler, port=int(os.environ.get("PORT", "443")))


if __name__ == "__main__":
    main()
