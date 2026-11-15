"""Loopback-only FieldKest sample inspection helper."""

from __future__ import annotations

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

def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer(("127.0.0.1", 8701), WorkbenchHandler).serve_forever()


if __name__ == "__main__":
    main()

