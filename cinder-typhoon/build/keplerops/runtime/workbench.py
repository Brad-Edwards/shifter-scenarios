"""Loopback-only FieldKest sample inspection helper."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import uuid
from urllib.parse import urlsplit

from http_support import KeplerHandler, append_audit, canonical_bytes, utc_now
from http.server import ThreadingHTTPServer


CONFIG = json.loads(Path("/opt/fieldkest-workbench/config/opening.json").read_text())
AUDIT = Path(CONFIG["audit_directory"])
RESULTS = Path(CONFIG.get("results_directory", "/var/lib/fieldkest-workbench/results"))


class WorkbenchHandler(KeplerHandler):
    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == CONFIG["inspection_summary"]["route"]:
            self._inspection()
        elif "predecessor_desk" in CONFIG and path == CONFIG["predecessor_desk"]["route"]:
            self._predecessor_desk()
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
        receipt["flag"] = "FLAG{b333bddf473ffe8c}"
        self.send_json(201, receipt)

    def _predecessor_desk(self) -> None:
        """K03.1 grader: bind staging attachment digest to collection identifier.

        Takes {attachment_sha256, collection}.
        Verifies attachment_sha256 matches staging-FKCOL-2841.bin and collection == FKCOL-2841.
        """
        contract = CONFIG["predecessor_desk"]
        try:
            body = self.read_json(131_072)
            attachment_sha256 = body.get("attachment_sha256", "")
            collection = body.get("collection", "")
            if not (attachment_sha256 and collection):
                raise ValueError("attachment_sha256_collection_required")
        except (ValueError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(422, {"error": "invalid_k03_1_submission"})
            return
        if attachment_sha256.lower() != contract["attachment_sha256"]:
            self.send_json(422, {"error": "attachment_digest_mismatch"})
            return
        if collection != contract["collection"]:
            self.send_json(422, {"error": "collection_binding_denied"})
            return
        RESULTS.mkdir(parents=True, exist_ok=True)
        receipt_path = RESULTS / "k03-1-complete.json"
        if receipt_path.is_file():
            cached = json.loads(receipt_path.read_text())
            cached["flag"] = "FLAG{dc079e33f8c31fc3}"
            self.send_json(200, cached)
            return
        receipt_id = "K03-1-" + uuid.uuid4().hex[:10].upper()
        result = {
            "schema": "fieldkest.k03-1-receipt/v1",
            "receipt_id": receipt_id,
            "card": "K03.1",
            "collection": contract["collection"],
            "attachment_path": contract["attachment_path"],
            "attachment_sha256": contract["attachment_sha256"],
            "odt_path": contract["odt_path"],
            "observed_at": utc_now(),
        }
        result["flag"] = "FLAG{dc079e33f8c31fc3}"
        receipt_path.write_text(json.dumps({k: v for k,v in result.items() if k != "flag"}, sort_keys=True, separators=(",", ":")) + "\n")
        append_audit(AUDIT, "k03-1-predecessor-desk", {
            "request_id": self.request_id,
            "receipt_id": receipt_id,
            "collection": contract["collection"],
            "attachment_sha256": contract["attachment_sha256"],
            "status": 201,
        })
        self.send_json(201, result)


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer(("127.0.0.1", 8701), WorkbenchHandler).serve_forever()


if __name__ == "__main__":
    main()

