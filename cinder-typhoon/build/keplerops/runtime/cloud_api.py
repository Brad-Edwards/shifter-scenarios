"""FieldKest cloud build-record surface used by the isolated CI worker."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from http_support import KeplerHandler, append_audit, serve_tls, validate_worker_token


STATE = Path("/var/lib/fieldkest-cloud-api")
AUDIT = STATE / "audit"
CONFIG = json.loads((STATE / "config/k09.json").read_text())
WORKER_SECRET = Path("/tmp/worker-hmac.key").read_bytes()


class CloudAPIHandler(KeplerHandler):
    def _worker(self) -> dict[str, object] | None:
        return validate_worker_token(
            self.headers.get("Authorization", ""),
            WORKER_SECRET,
            "build-records",
            self.client_address[0],
            origin_network=CONFIG["worker_status"]["accepted_origin"],
        )

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        worker = self._worker()
        if worker is None:
            append_audit(AUDIT, "build-records", {
                "request_id": self.request_id,
                "peer_address": self.client_address[0],
                "path": path,
                "authorization": "denied",
                "status": 403,
            })
            self.send_json(403, {"error": "worker_authentication_required"})
            return
        base_audit = {
            "request_id": self.request_id,
            "peer_address": self.client_address[0],
            "principal": worker["principal"],
            "run_id": worker["run_id"],
            "lease_id": worker["lease_id"],
            "token_id": worker["jti"],
            "path": path,
        }
        if path == "/api/build-records/worker-status":
            append_audit(AUDIT, "build-records", {**base_audit, "status": 200})
            self.send_json(200, {
                "schema": "fieldkest.worker-status/v1",
                "availability": CONFIG["worker_status"]["availability"],
                "principal": worker["principal"],
                "run_id": worker["run_id"],
                "request_id": self.request_id,
            })
            return
        if path == "/api/build-records":
            append_audit(AUDIT, "build-records", {**base_audit, "operation": "index", "status": 200})
            self.send_json(200, {
                "schema": "fieldkest.build-record-index/v1",
                "records": [
                    {"build_id": key, "href": f"/api/build-records/{key}"}
                    for key in sorted(CONFIG["records"])
                ],
            })
            return
        if path.startswith("/api/build-records/"):
            build_id = path.removeprefix("/api/build-records/")
            record = CONFIG["records"].get(build_id)
            if record is not None:
                append_audit(AUDIT, "build-records", {**base_audit, "build_id": build_id, "status": 200})
                self.send_json(200, {"schema": "fieldkest.build-record-reference/v1", "build_id": build_id, **record})
                return
        self.send_json(404, {"error": "build_record_not_found"})


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    serve_tls(CloudAPIHandler)


if __name__ == "__main__":
    main()
