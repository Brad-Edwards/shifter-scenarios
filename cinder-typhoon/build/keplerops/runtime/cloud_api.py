"""FieldKest cloud build-record surface used by the isolated CI worker."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from http_support import KeplerHandler, append_audit, serve_tls, validate_worker_token
from credentials import credential


STATE = Path("/var/lib/fieldkest-cloud-api")
AUDIT = STATE / "audit"
CONFIG = json.loads((STATE / "config/runner-foundation.json").read_text())
WORKER_SECRET = Path("/tmp/worker-hmac.key").read_bytes()
DEV_USER = "rowan.ito"
DEV_TOKEN = credential("developer_token")
WORKLOAD_FIXTURE_TOKEN = credential("cloud_workload_fixture_token")
WORKLOAD_SESSION = credential("cloud_workload_session")
SUPPORT_EXPORT_ROLE = credential("cloud_support_export_role")
RELEASE_READER_TOKEN = credential("release_reader_token")
HISTORY_RECOVERY_SESSION = credential("cloud_history_recovery_session")
import threading as _threading
_RECOVERY_NAMESPACES = {}
_RECOVERY_LOCK = _threading.Lock()
_ARWC_MIGRATION_HISTORY = {
    "schema": "fieldkest.customer-migration-history/v1", "backup_id": "BAK-2026-021",
    "records": [{"tenant_id": "TEN-ARWC-019", "current_tenant": "TEN-ARWC-047",
                 "migration_date": "2026-08-15", "connector": "fieldlink",
                 "connector_revision": "FLK-7.4.2", "reason": "tenant-consolidation-2026"}],
}

MAINTENANCE_WORKER = credential("ci_maintenance_worker")
MAINTENANCE_RUNTIME = credential("cloud_maintenance_runtime")
CREDENTIAL_PRINCIPALS = {
    WORKLOAD_SESSION: "svc-fieldlink-workload",
    SUPPORT_EXPORT_ROLE: "role/support-export-editor",
    MAINTENANCE_WORKER: "svc-fieldkest-runner",
}
MAINTENANCE_COMMAND = ["maintenance-summary", "--archive", "FIELD-CRR-2026-09"]
MAINTENANCE_LABEL = {"workload.class": "maintenance"}
_WORKLOAD_EXECUTIONS = {}
_WORKLOAD_LOCK = __import__("threading").Lock()
FIELD_ARCHIVE_CALIBRATION = "CRR-OG2-CAL-2026-09-18"
MAINTENANCE_ARCHIVE_HEADERS = {
    "workload_class": "X-Workload-Class",
    "scheduler_attestation": "X-Scheduler-Attestation",
}


def credential_principal(value: str) -> str:
    return CREDENTIAL_PRINCIPALS.get(value, "unrecognized")


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
        if self.send_client_document():
            return
        path = urlsplit(self.path).path
        worker = self._worker()
        token = self.headers.get("Authorization", "").removeprefix("Bearer ")
        developer = self.basic_or_bearer(DEV_USER, DEV_TOKEN)
        if path == "/api/workspaces/current/token-exchange":
            if not developer:
                return self.send_json(403, {"error": "developer_session_required"})
            value = {"workspace": "WS-ROWAN-2026-09-G1", "subject": "svc-fieldlink-workload", "issuer": "https://workload.keplerops.test", "audience": "fieldkest-build-records", "fixture_token": WORKLOAD_FIXTURE_TOKEN, "trust_record": "TRUST-FLX-04"}
            append_audit(AUDIT, "workspace-exchange", {"request_id": self.request_id, "principal": DEV_USER, "status": 200})
            return self.send_json(200, value)
        if path == "/api/build-records/BLD-1842" and token == WORKLOAD_SESSION:
            value = {"build_id": "BLD-1842", "principal": "svc-fieldlink-workload", "revision": "c37effd7cc86ae4d44f18e95f899b7557d65e0a9", "dossier": "BLD-REL-742", "flag": "FLAG{0b9877c3539fbcfa}"}
            append_audit(AUDIT, "build-records", {"request_id": self.request_id, "principal": value["principal"], "build_id": value["build_id"], "status": 200})
            return self.send_json(200, value)
        if path == "/api/trust-records/TRUST-FLX-04" and token == WORKLOAD_SESSION:
            value = {"trust_id": "TRUST-FLX-04", "issuer": "https://workload.keplerops.test", "subject": "svc-fieldlink-workload", "accepted_audiences": ["fieldkest-cloud-policy"], "role": "role/support-export-editor", "flag": "FLAG{c1e0dbfdffe75425}"}
            append_audit(AUDIT, "trust-records", {"request_id": self.request_id, "principal": "svc-fieldlink-workload", "status": 200})
            return self.send_json(200, value)
        if path == "/api/roles/support-export-editor" and token == SUPPORT_EXPORT_ROLE:
            value = {"role": "role/support-export-editor", "tenant": "keplerops", "resources": ["exports/EXP-2841", "schedules/SCH-SUP-2841", "workloads/$own/*"]}
            append_audit(AUDIT, "role-records", {"request_id": self.request_id, "principal": value["role"], "status": 200})
            return self.send_json(200, value)
        if path == "/api/build-records/BLD-REL-742" and developer:
            value = {"build_id": "BLD-REL-742", "release_principal": "release-reader", "exchange_handle": RELEASE_READER_TOKEN, "package_interfaces": ["fieldkest.connector/v2", "fieldkest.connector/v3"]}
            append_audit(AUDIT, "build-records", {"request_id": self.request_id, "principal": DEV_USER, "build_id": value["build_id"], "status": 200})
            return self.send_json(200, value)
        if path.endswith("/whoami") and "/api/workloads/" in path:
            tok_b = self.headers.get("Authorization","").removeprefix("Bearer ")
            if tok_b != MAINTENANCE_WORKER:
                return self.send_json(401, {"error": "maintenance_worker_required"})
            with _WORKLOAD_LOCK: ex = _WORKLOAD_EXECUTIONS.get("MAINT-FLK-01")
            if ex is None: return self.send_json(404, {"error": "no_execution_found"})
            return self.send_json(200, {"workload_id": "MAINT-FLK-01", "runtime_identity": "svc-fieldlink-maintenance", "attestation": ex["attestation"]})
        if path == "/api/field-archive/FIELD-CRR-2026-09":
            tok_b = self.headers.get("Authorization","").removeprefix("Bearer ")
            if tok_b != MAINTENANCE_RUNTIME: return self.send_json(401, {"error": "maintenance_runtime_required"})
            wc = self.headers.get("X-Workload-Class","")
            att = self.headers.get("X-Scheduler-Attestation","")
            if wc != "maintenance": return self.send_json(403, {"error": "workload_class_mismatch"})
            with _WORKLOAD_LOCK: known = any(e.get("attestation")==att for e in _WORKLOAD_EXECUTIONS.values())
            if not known: return self.send_json(403, {"error": "attestation_invalid"})
            append_audit(AUDIT, "field-archive", {"request_id": self.request_id, "archive_id": "FIELD-CRR-2026-09", "status": 200})
            return self.send_json(200, {"archive_id": "FIELD-CRR-2026-09", "runtime_identity": "svc-fieldlink-maintenance", "calibration_revision": FIELD_ARCHIVE_CALIBRATION, "asset": "CRR-OG2"})
        if path == "/api/backups/BAK-2026-021":
            self._backup_catalog(); return
        if path.startswith("/api/recovery/") and path.endswith("/customer-migration-history"):
            self._recovery_history(path.removeprefix("/api/recovery/").removesuffix("/customer-migration-history")); return
        if path == "/api/build-records/BLD-REC-021" and token in {WORKLOAD_SESSION, SUPPORT_EXPORT_ROLE, RELEASE_READER_TOKEN}:
            value = {"build_id": "BLD-REC-021", "principal": "svc-history-recovery", "backup": "BAK-2026-021", "allowed": "restore", "source_database": "denied", "session": HISTORY_RECOVERY_SESSION}
            append_audit(AUDIT, "build-records", {"request_id": self.request_id, "principal": credential_principal(token), "build_id": value["build_id"], "status": 200})
            return self.send_json(200, value)
        if path.startswith("/api/maintenance/") and path != "/api/maintenance":
            tok_a = self.headers.get("Authorization","").removeprefix("Bearer ")
            if tok_a != MAINTENANCE_WORKER:
                return self.send_json(401, {"error": "maintenance_worker_required"})
            job_part = path.removeprefix("/api/maintenance/")
            if job_part.endswith("/probe"):
                job_id = job_part[:-len("/probe")]
                if job_id != "MAINT-FLK-01":
                    return self.send_json(403, {"error": "out_of_scope_workload"})
                import uuid as _u2
                rid = "K31-1-" + _u2.uuid4().hex[:10].upper()
                result = {"card": "K31.1", "receipt_id": rid, "workload_id": "MAINT-FLK-01", "runtime_identity": "svc-fieldlink-maintenance", "management_caller": "svc-fieldkest-runner", "identity_distinction": "runtime_identity != management_caller", "label_check": "passed", "required_label": MAINTENANCE_LABEL}
                append_audit(AUDIT, "maintenance-probe", {"request_id": self.request_id, "workload_id": "MAINT-FLK-01", "receipt_id": rid, "status": 201})
                return self.send_json(201, result)
            if job_part != "MAINT-FLK-01":
                return self.send_json(403, {"error": "out_of_scope_workload"})
            result = {"workload_id": "MAINT-FLK-01", "runtime_identity": "svc-fieldlink-maintenance", "management_caller": "svc-fieldkest-runner", "required_label": MAINTENANCE_LABEL, "label_check": "passed"}
            append_audit(AUDIT, "maintenance-job-read", {"request_id": self.request_id, "workload_id": "MAINT-FLK-01", "status": 200})
            return self.send_json(200, result)
        if path == "/api/maintenance" and token in {SUPPORT_EXPORT_ROLE, WORKLOAD_SESSION, MAINTENANCE_WORKER}:
            # Maintenance management index the runner reads (see runner-operations.md):
            # the policy, the managed workload, the field archive, and the worker
            # and runtime credentials the scheduler issues for maintenance jobs.
            value = {
                "policy_id": "fieldlink-maintenance", "workload_id": "MAINT-FLK-01",
                "field_archive": "FIELD-CRR-2026-09", "archive_asset": "CRR-OG2",
                "workload_class": "maintenance", "worker_credential": MAINTENANCE_WORKER,
                "runtime_credential": MAINTENANCE_RUNTIME,
            }
            append_audit(AUDIT, "maintenance-index", {"request_id": self.request_id, "principal": credential_principal(token), "status": 200})
            return self.send_json(200, value)
        if path == "/api/policies/fieldlink-maintenance" and token in {SUPPORT_EXPORT_ROLE, MAINTENANCE_WORKER}:
            value = {
                "policy_id": "fieldlink-maintenance", "management_caller": "svc-fieldkest-runner",
                "scheduler": "fieldkest-scheduler", "runtime_identity": "svc-fieldlink-maintenance",
                "command": MAINTENANCE_COMMAND, "required_label": MAINTENANCE_LABEL,
                "archive_request": {"headers": MAINTENANCE_ARCHIVE_HEADERS},
                "whoami": "svc-fieldkest-runner",
            }
            append_audit(AUDIT, "maintenance-policy", {"request_id": self.request_id, "principal": credential_principal(token) if token else worker["principal"], "status": 200})
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
            value = {"principal": "svc-fieldlink-workload", "access_token": WORKLOAD_SESSION, "audience": "fieldkest-build-records", "expires_in": 600}
            append_audit(AUDIT, "workspace-exchange", {"request_id": self.request_id, "principal": DEV_USER, "issued_principal": value["principal"], "status": 201})
            return self.send_json(201, value)
        if path == "/api/backups/BAK-2026-021/restores":
            if self.headers.get("Authorization","").removeprefix("Bearer ") != HISTORY_RECOVERY_SESSION:
                return self.send_json(401, {"error": "recovery_session_required"})
            import uuid as _uuid
            ns = "NS-REC-" + _uuid.uuid4().hex[:10].upper()
            with _RECOVERY_LOCK: _RECOVERY_NAMESPACES[ns] = {"backup_id": "BAK-2026-021"}
            append_audit(AUDIT, "backup-restore", {"request_id": self.request_id, "namespace_id": ns, "status": 201})
            return self.send_json(201, {"namespace_id": ns, "backup_id": "BAK-2026-021"})
        if path == "/api/token-exchange/support-export-editor":
            if self.headers.get("Authorization") != f"Bearer {WORKLOAD_FIXTURE_TOKEN}":
                return self.send_json(403, {"error": "workload_token_required"})
            value = {"principal": "role/support-export-editor", "access_token": SUPPORT_EXPORT_ROLE, "audience": "fieldkest-cloud-policy", "expires_in": 600, "accepted_input_audience": "fieldkest-build-records", "flag": "FLAG{244cd323590694f6}"}
            append_audit(AUDIT, "role-exchange", {"request_id": self.request_id, "principal": "svc-fieldlink-workload", "role": value["principal"], "status": 201})
            return self.send_json(201, value)
        self.send_json(404, {"error": "not_found"})


    def _recovery_session_check(self):
        return self.headers.get("Authorization","").removeprefix("Bearer ") == HISTORY_RECOVERY_SESSION

    def _backup_catalog(self):
        if not self._recovery_session_check():
            return self.send_json(401, {"error": "recovery_session_required"})
        append_audit(AUDIT, "backup-catalog", {"request_id": self.request_id, "backup_id": "BAK-2026-021", "status": 200})
        self.send_json(200, {"schema": "fieldkest.backup-catalog/v1", "backup_id": "BAK-2026-021",
                              "source_database": "denied", "restore_allowed": True,
                              "contents": ["customer-migration-history"], "created_at": "2026-08-20T00:00:00Z"})

    def _recovery_history(self, namespace_id):
        if not self._recovery_session_check():
            return self.send_json(401, {"error": "recovery_session_required"})
        with _RECOVERY_LOCK: ns = _RECOVERY_NAMESPACES.get(namespace_id)
        if ns is None: return self.send_json(404, {"error": "namespace_not_found"})
        import copy as _copy
        result = _copy.deepcopy(_ARWC_MIGRATION_HISTORY); result["namespace_id"] = namespace_id
        append_audit(AUDIT, "recovery-history", {"request_id": self.request_id, "namespace_id": namespace_id, "status": 200})
        self.send_json(200, result)


    def do_PATCH(self) -> None:
        path = __import__('urllib.parse', fromlist=['urlsplit']).urlsplit(self.path).path
        if path == "/api/workloads/MAINT-FLK-01":
            tok_c = self.headers.get("Authorization","").removeprefix("Bearer ")
            if tok_c != MAINTENANCE_WORKER: return self.send_json(401, {"error": "maintenance_worker_required"})
            try: body = self.read_json(4096)
            except: return self.send_json(400, {"error": "bad_request"})
            if body.get("command") != MAINTENANCE_COMMAND or body.get("labels") != MAINTENANCE_LABEL:
                return self.send_json(422, {"error": "command_or_label_mismatch"})
            import uuid as _u3
            att2 = "ATTEST-" + _u3.uuid4().hex[:16].upper()
            with _WORKLOAD_LOCK: _WORKLOAD_EXECUTIONS["MAINT-FLK-01"] = {"attestation": att2}
            append_audit(AUDIT, "workload-patch", {"request_id": self.request_id, "workload_id": "MAINT-FLK-01", "status": 200})
            return self.send_json(200, {"workload_id": "MAINT-FLK-01", "last_execution": {"execution_backend": "isolated-container"}, "runtime_identity": "svc-fieldlink-maintenance"})
        self.send_json(404, {"error": "not_found"})


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    serve_tls(CloudAPIHandler)


if __name__ == "__main__":
    main()
