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
DEV_USER = "rowan.ito"
DEV_TOKEN = "kpl_rowan_7X4mQ9vN2cL6"


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
        token = self.headers.get("Authorization", "").removeprefix("Bearer ")
        developer = self.basic_or_bearer(DEV_USER, DEV_TOKEN)
        if path == "/api/workspaces/current/token-exchange":
            if not developer:
                return self.send_json(403, {"error": "developer_session_required"})
            value = {"workspace": "WS-ROWAN-2026-09-G1", "subject": "svc-fieldlink-workload", "issuer": "https://workload.keplerops.test", "audience": "fieldkest-build-records", "fixture_token": "workload-oidc-wrong-aud"}
            append_audit(AUDIT, "workspace-exchange", {"request_id": self.request_id, "principal": DEV_USER, "status": 200})
            return self.send_json(200, value)
        if path == "/api/build-records/BLD-1842" and token == "workload-session":
            value = {"build_id": "BLD-1842", "principal": "svc-fieldlink-workload", "revision": "c37effd7cc86ae4d44f18e95f899b7557d65e0a9", "dossier": "BLD-REL-742"}
            append_audit(AUDIT, "build-records", {"request_id": self.request_id, "principal": value["principal"], "build_id": value["build_id"], "status": 200})
            return self.send_json(200, value)
        if path == "/api/trust-records/TRUST-FLX-04" and token == "workload-session":
            value = {"trust_id": "TRUST-FLX-04", "issuer": "https://workload.keplerops.test", "subject": "svc-fieldlink-workload", "accepted_audiences": ["fieldkest-cloud-policy"], "role": "role/support-export-editor"}
            append_audit(AUDIT, "trust-records", {"request_id": self.request_id, "principal": "svc-fieldlink-workload", "status": 200})
            return self.send_json(200, value)
        if path == "/api/roles/support-export-editor" and token == "support-export-role":
            value = {"role": "role/support-export-editor", "tenant": "keplerops", "resources": ["exports/EXP-2841", "schedules/SCH-SUP-2841", "workloads/$own/*"]}
            append_audit(AUDIT, "role-records", {"request_id": self.request_id, "principal": value["role"], "status": 200})
            return self.send_json(200, value)
        if path == "/api/build-records/BLD-REL-742" and developer:
            value = {"build_id": "BLD-REL-742", "release_principal": "release-reader", "exchange_handle": "release-reader-handle", "package_interfaces": ["fieldkest.connector/v2", "fieldkest.connector/v3"]}
            append_audit(AUDIT, "build-records", {"request_id": self.request_id, "principal": DEV_USER, "build_id": value["build_id"], "status": 200})
            return self.send_json(200, value)
        if path == "/api/build-records/BLD-REC-021" and token in {"workload-session", "support-export-role"}:
            value = {"build_id": "BLD-REC-021", "principal": "svc-history-recovery", "backup": "BAK-2026-021", "allowed": "restore", "source_database": "denied", "session": "history-recovery-session"}
            append_audit(AUDIT, "build-records", {"request_id": self.request_id, "principal": token, "build_id": value["build_id"], "status": 200})
            return self.send_json(200, value)
        if path == "/api/policies/fieldlink-maintenance" and (token in {"support-export-role", "ci-maintenance-worker"} or worker is not None):
            value = {"policy_id": "fieldlink-maintenance", "management_caller": "svc-fieldkest-runner", "scheduler": "fieldkest-scheduler", "runtime_identity": "svc-fieldlink-maintenance", "required_label": {"workload.class": "maintenance"}, "whoami": "svc-fieldkest-runner"}
            append_audit(AUDIT, "maintenance-policy", {"request_id": self.request_id, "principal": token or worker["principal"], "status": 200})
            return self.send_json(200, value)
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

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/workspaces/current/token-exchange":
            if not self.basic_or_bearer(DEV_USER, DEV_TOKEN):
                return self.send_json(403, {"error": "developer_session_required"})
            value = {"principal": "svc-fieldlink-workload", "access_token": "workload-session", "audience": "fieldkest-build-records", "expires_in": 600}
            append_audit(AUDIT, "workspace-exchange", {"request_id": self.request_id, "principal": DEV_USER, "issued_principal": value["principal"], "status": 201})
            return self.send_json(201, value)
        if path == "/api/token-exchange/support-export-editor":
            if self.headers.get("Authorization") != "Bearer workload-oidc-wrong-aud":
                return self.send_json(403, {"error": "workload_token_required"})
            value = {"principal": "role/support-export-editor", "access_token": "support-export-role", "audience": "fieldkest-cloud-policy", "expires_in": 600, "accepted_input_audience": "fieldkest-build-records"}
            append_audit(AUDIT, "role-exchange", {"request_id": self.request_id, "principal": "svc-fieldlink-workload", "role": value["principal"], "status": 201})
            return self.send_json(201, value)
        self.send_json(404, {"error": "not_found"})


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    serve_tls(CloudAPIHandler)


if __name__ == "__main__":
    main()
