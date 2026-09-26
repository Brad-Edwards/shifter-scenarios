"""Loopback-only FieldKest inspection, reconstruction and callback helper."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from http_support import KeplerHandler, append_audit, canonical_bytes, utc_now
from http.server import ThreadingHTTPServer


CONFIG = json.loads(Path("/opt/fieldkest-workbench/config/opening.json").read_text())
AUDIT = Path(CONFIG["audit_directory"])


class WorkbenchHandler(KeplerHandler):
    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == CONFIG["inspection_summary"]["route"]:
            self._inspection()
        elif path == CONFIG["reconstruction"]["route"]:
            self._reconstruction()
        elif path == CONFIG["callback_collection"]["route"]:
            self._callback()
        else:
            self.send_json(404, {"error": "not_found"})

    def _inspection(self) -> None:
        try:
            raw = self.read_upload("sample", 262_144)
            sample = json.loads(raw.decode("utf-8"))
        except (ValueError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(422, {"error": "invalid_sample"})
            return
        contract = CONFIG["inspection_summary"]
        if (
            hashlib.sha256(raw).hexdigest() != contract["sample_sha256"]
            or sample.get("schema") != contract["accepted_schema"]
            or sample.get("sample_id") != contract["sample_id"]
            or sample.get("asset_id") != contract["asset_id"]
            or sample.get("connector_revision") != contract["connector_revision"]
        ):
            self.send_json(422, {"error": "sample_binding_mismatch"})
            return
        summary = {
            "schema": "fieldkest.inspection-summary/v1",
            "sample_id": sample["sample_id"],
            "asset_id": sample["asset_id"],
            "connector_revision": sample["connector_revision"],
            "captured_at": sample["captured_at"],
            "observations": sample["observations"],
        }
        output_sha = hashlib.sha256(canonical_bytes(summary)).hexdigest()
        receipt = {
            **summary,
            "receipt_id": "INS-" + self.request_id,
            "observed_at": utc_now(),
            "input_sha256": hashlib.sha256(raw).hexdigest(),
            "output_sha256": output_sha,
        }
        append_audit(AUDIT, "inspection", {"request_id": self.request_id, "sample_id": sample["sample_id"], "asset_id": sample["asset_id"], "connector_revision": sample["connector_revision"], "input_sha256": receipt["input_sha256"], "output_sha256": output_sha, "status": 201})
        self.send_json(201, receipt)

    def _reconstruction(self) -> None:
        try:
            raw = self.read_upload("bundle", 524_288)
            request = json.loads(raw.decode("utf-8"))
            script = base64.b64decode(request["script_base64"], validate=True)
            instructions = base64.b64decode(request["instructions_base64"], validate=True)
        except (ValueError, KeyError, TypeError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(422, {"error": "invalid_reconstruction"})
            return
        contract = CONFIG["reconstruction"]
        script_digest = hashlib.sha256(script).hexdigest()
        instructions_digest = hashlib.sha256(instructions).hexdigest()
        valid = (
            request.get("schema") == contract["accepted_schema"]
            and request.get("collection_id") == contract["collection_id"]
            and script_digest == contract["script_sha256"]
            and instructions_digest == contract["instructions_sha256"]
        )
        if not valid:
            append_audit(AUDIT, "reconstruction", {"request_id": self.request_id, "collection_id": request.get("collection_id"), "script_sha256": script_digest, "instructions_sha256": instructions_digest, "status": 422})
            self.send_json(422, {"error": "reconstruction_mismatch"})
            return
        receipt = {
            "schema": "fieldkest.reconstruction-receipt/v1",
            "receipt_id": "REC-" + self.request_id,
            "collection_id": contract["collection_id"],
            "script_sha256": script_digest,
            "instructions_sha256": instructions_digest,
            "endpoint_id": contract["endpoint_id"],
            "callback_integrity": contract["callback_integrity"],
            "executed": False,
        }
        append_audit(AUDIT, "reconstruction", {"request_id": self.request_id, **{key: receipt[key] for key in ("collection_id", "script_sha256", "instructions_sha256", "endpoint_id", "callback_integrity")}, "status": 201})
        self.send_json(201, receipt)

    def _callback(self) -> None:
        try:
            request = self.read_json(65_536)
        except (ValueError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "invalid_request"})
            return
        contract = CONFIG["callback_collection"]
        fields = ("endpoint_id", "collection_id", "integrity")
        if not isinstance(request, dict) or any(request.get(field) != contract[field] for field in fields):
            append_audit(AUDIT, "callback", {"request_id": self.request_id, "endpoint_id": request.get("endpoint_id") if isinstance(request, dict) else None, "collection_id": request.get("collection_id") if isinstance(request, dict) else None, "status": 403})
            self.send_json(403, {"error": "callback_binding_denied"})
            return
        record = contract["record"]
        append_audit(AUDIT, "callback", {"request_id": self.request_id, "endpoint_id": request["endpoint_id"], "collection_id": request["collection_id"], "ticket_reference": record["ticket_reference"], "status": 200})
        self.send_json(200, record)


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer(("127.0.0.1", 8701), WorkbenchHandler).serve_forever()


if __name__ == "__main__":
    main()

