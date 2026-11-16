"""FieldKest preview queue service.

Wraps Gotenberg for document rendering and provides the K10 preview
association, document identity, and queue management routes.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
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
                "owner": association["owner"],
            }
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

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if not self._developer():
            self.send_json(401, {"error": "authentication_required"})
            return
        if path == "/api/preview/documents":
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
            self.send_json(200, result)
        else:
            self.send_json(404, {"error": "not_found"})


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    serve_tls(PreviewHandler, port=int(os.environ.get("PORT", "443")))


if __name__ == "__main__":
    main()
