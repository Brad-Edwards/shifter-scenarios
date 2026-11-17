"""k-cloud-api: thin workspace token-exchange front for the K3s workload identity.

K13.4: the participant exchanges developer credentials for a real K3s service-account
token (svc-fieldlink-workload) and uses it to read the protected build record.
RBAC is enforced by real K3s — not by Python if-statements in this service.
"""
from __future__ import annotations

import base64
import hashlib
import http.client as _hc
import json
import os
from pathlib import Path
import secrets
import ssl
import tempfile
from urllib.parse import urlsplit

from http_support import KeplerHandler, append_audit, serve_tls
from credentials import credential

STATE = Path(os.environ.get("FIELDKEST_STATE_ROOT", "/var/lib/fieldkest-cloud-api"))
AUDIT = STATE / "audit"
RESULTS = STATE / "results"
CONFIG = json.loads((STATE / "config/cloud-api.json").read_text())

USERNAME = CONFIG["developer"]["username"]
TOKEN = credential("developer_token")
RELEASE_READER_TOKEN = credential("release_reader_token")  # K29.1 exchange handle
HISTORY_RECOVERY_SESSION = credential("cloud_history_recovery_session")  # K30.1 recovery session
WORKLOAD_SESSION = credential("cloud_workload_session")  # K13.4 workload path
NAMESPACE = CONFIG.get("namespace", "fieldlink")
WORKLOAD_SA = CONFIG.get("workload_sa", "svc-fieldlink-workload")

# K3s connection credentials (from cloud-api-k3s.json mounted at startup)
_K3S_CRED_PATH = Path(os.environ.get("K3S_CREDENTIALS_FILE", "/etc/cloud-api/k3s.json"))


def _validate_partition_binding(export_id: str, tenant: str,
                                partition: str, connector_revision: str) -> bool:
    """K15.4: validate partition binding against real PostgreSQL export.partition_bindings.

    Queries: SELECT 1 FROM export.partition_bindings WHERE export_id=? AND tenant=?
             AND partition_id=? AND connector_revision=? AND is_current=true
    Returns True if found (valid binding), False otherwise.
    """
    try:
        import psycopg2
        import os
        pg_host = CONFIG.get("postgres_host", "data.keplerops.test")
        pg_port = int(CONFIG.get("postgres_port", 5432))
        pg_db = CONFIG.get("postgres_db", "fieldlink_data")
        pg_user = CONFIG.get("postgres_user", "rowan_data")
        pg_pass_file = Path(os.environ.get("POSTGRES_PASSWORD_FILE",
                                           "/etc/cloud-api/pgpass"))
        if pg_pass_file.is_file():
            pg_pass = pg_pass_file.read_text().strip()
        else:
            pg_pass = os.environ.get("PGPASSWORD", "")
        conn = psycopg2.connect(
            host=pg_host, port=pg_port, dbname=pg_db,
            user=pg_user, password=pg_pass,
            connect_timeout=5,
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM export.partition_bindings "
            "WHERE export_id=%s AND tenant=%s AND partition_id=%s "
            "AND connector_revision=%s AND is_current=true",
            (export_id, tenant, partition, connector_revision),
        )
        found = cur.fetchone() is not None
        conn.close()
        return found
    except Exception:
        return False


def _write_export_object(export_id: str, destination: str,
                         collection_key: str, payload: bytes) -> tuple[bool, str]:
    """K15.4: write a versioned export object to real SeaweedFS S3.

    Uses the svc-fieldlink-export credentials to write to fieldkest-exports bucket.
    Returns (success, error_message).
    """
    try:
        cred_file = Path(os.environ.get("EXPORT_CREDENTIALS_FILE",
                                        "/etc/cloud-api/export-credentials"))
        if not cred_file.is_file():
            return False, "export_credentials_missing"
        lines = cred_file.read_text().splitlines()
        access_key = next((l.split("=", 1)[1].strip() for l in lines
                           if l.startswith("aws_access_key_id")), "")
        secret_key = next((l.split("=", 1)[1].strip() for l in lines
                           if l.startswith("aws_secret_access_key")), "")
        s3_endpoint = CONFIG.get("s3_endpoint", "http://fieldlink-objects:8333")
        s3_host, s3_port_str = s3_endpoint.removeprefix("http://").split(":")
        s3_port = int(s3_port_str)
        # Build S3 PUT request (unsigned for simplicity — SeaweedFS accepts unsigned if credentials match)
        # Use AWS Signature V4 via subprocess aws command
        import subprocess
        bucket = "fieldkest-exports"
        s3_key = f"{export_id}/{collection_key}"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            f.write(payload); tmp_path = f.name
        env = {**os.environ,
               "AWS_ACCESS_KEY_ID": access_key,
               "AWS_SECRET_ACCESS_KEY": secret_key,
               "AWS_DEFAULT_REGION": "us-east-1"}
        result = subprocess.run(
            ["aws", "--endpoint-url", s3_endpoint,
             "s3", "cp", tmp_path, f"s3://{bucket}/{s3_key}"],
            capture_output=True, text=True, env=env, timeout=10
        )
        os.unlink(tmp_path)
        if result.returncode == 0:
            return True, ""
        return False, result.stderr[:200]
    except Exception as exc:
        return False, str(exc)


def _load_k3s_creds() -> dict:
    return json.loads(_K3S_CRED_PATH.read_text())


def _k3s_request(method: str, path: str, body: object = None,
                 bearer: str | None = None) -> tuple[int, dict]:
    """Make a request to the K3s API server."""
    creds = _load_k3s_creds()
    ca_data = base64.b64decode(creds["ca"])
    server = creds["server"]  # e.g. https://10.77.52.60:6443
    host, port = server.removeprefix("https://").split(":")
    token = bearer if bearer else creds["token"]
    with tempfile.NamedTemporaryFile(suffix=".crt", delete=True) as ca_file:
        ca_file.write(ca_data)
        ca_file.flush()
        ctx = ssl.create_default_context(cafile=ca_file.name)
        conn = _hc.HTTPSConnection(host, int(port), context=ctx, timeout=10)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        encoded = json.dumps(body).encode() if body is not None else None
        conn.request(method, path, body=encoded, headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
    try:
        return resp.status, json.loads(data) if data else {}
    except (ValueError, json.JSONDecodeError):
        return resp.status, {}


class CloudApiHandler(KeplerHandler):
    def _developer(self) -> bool:
        return self.basic_or_bearer(USERNAME, TOKEN)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/.well-known/fieldkest-client":
            docs = json.loads(Path("/opt/fieldkest/client_documents.json").read_text())
            self.send_json(200, docs["documents"]["cloud-api.keplerops.test"])
            return
        if path == "/health":
            self.send_json(200, {"status": "up"})
            return
        # /api/build-records/{id}: two paths depending on the build record type.
        # K29.1: BLD-REL-742 is developer-authenticated and returns the release exchange handle.
        #   The flaw: checks project membership (developer token) but omits release-dossier
        #   entitlement check before returning the exchange handle.
        # K13.4: all other build records require a K3s workload SA token (enforced by K3s RBAC).
        if path.startswith("/api/build-records/"):
            build_id = path.removeprefix("/api/build-records/")
            if build_id == "BLD-REL-742":
                self._build_record_release_dossier(build_id)
            elif build_id == "BLD-REC-021":
                self._build_record_history_recovery(build_id)
            else:
                self._build_record_via_workload(build_id)
            return
        # /api/trust-records/{id}: K14.1 — authenticated by workload SA token.
        # The trust record is a real K3s ConfigMap containing the token's trust context.
        if path.startswith("/api/trust-records/"):
            trust_id = path.removeprefix("/api/trust-records/")
            self._trust_record_via_workload(trust_id)
            return
        # /api/policies/{id}: K14.2 — authenticated by export SA token.
        # Reads the protected role record via K3s ConfigMap using the export SA token.
        if path.startswith("/api/policies/"):
            policy_id = path.removeprefix("/api/policies/")
            self._policy_via_export_token(policy_id)
            return
        # /api/data/exports/{id}: K14.3 — authenticated by export SA token.
        # Returns export S3 credentials for svc-fieldlink-export.
        # Proves SeaweedFS bucket policy boundary: developer denied, export role allowed.
        if path.startswith("/api/data/exports/"):
            export_id = path.removeprefix("/api/data/exports/")
            self._export_credentials(export_id)
            return
        # /api/exports/{id}/definition: K15.2 — authenticated by export SA token.
        # Reads the K3s ConfigMap for the export definition. The detail route checks
        # tenant visibility but omits job ownership (the K15.2 ownership gap).
        if path.endswith("/definition") and "/api/exports/" in path:
            export_id = path.removeprefix("/api/exports/").removesuffix("/definition")
            self._export_definition(export_id)
            return
        # /api/schedules/{id}/context: K16.3 — returns the execution identity.
        if path.endswith("/context") and "/api/schedules/" in path:
            schedule_id = path.removeprefix("/api/schedules/").removesuffix("/context")
            self._schedule_context(schedule_id)
            return
        # /api/schedules/{id}: K16.1 — authenticated by export SA token.
        # Reads the real K3s CronJob spec for the support schedule.
        if path.startswith("/api/schedules/"):
            schedule_id = path.removeprefix("/api/schedules/")
            self._schedule_summary(schedule_id)
            return
        # /api/exports/{id}: K15.1 — authenticated by export SA token.
        # Reads the real K3s Job spec for the export job and returns job summary.
        if path.startswith("/api/exports/"):
            export_id = path.removeprefix("/api/exports/")
            self._export_job_summary(export_id)
            return
        if not self._developer():
            self.send_json(401, {"error": "authentication_required"})
            return
        if path == "/api/workspaces/current/token-exchange":
            self._workspace_exchange()
            return
        self.send_json(404, {"error": "not_found"})

    def _patch_schedule(self, schedule_id: str) -> None:
        """K16.2: patch the CronJob startup behavior to add Cinder's marker.

        Uses real K3s strategic merge patch on CronJob sched-2841.
        Only the MARKER env var is added — ASSIGNMENT, PROFILE, STARTUP_CONFIG
        (the support output) remain unchanged (immutable). The patch persists and
        takes effect on the next Job run from the CronJob.
        RBAC: svc-fieldlink-export has patch rights on CronJob sched-2841.
        """
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json(401, {"error": "export_token_required"})
            return
        sa_token = auth[7:].strip()
        try:
            body = self.read_json(32_768)
            marker = str(body.get("marker", ""))
            if not marker:
                raise ValueError("marker_required")
        except (ValueError, TypeError):
            self.send_json(422, {"error": "marker_required"})
            return
        cronjob_name = schedule_id.lower()
        # Verify CronJob exists and get current spec before patching
        s_get, cj = _k3s_request(
            "GET", f"/apis/batch/v1/namespaces/{NAMESPACE}/cronjobs/{cronjob_name}",
            bearer=sa_token,
        )
        if s_get == 403:
            self.send_json(403, {"error": "k3s_rbac_denied"})
            return
        if s_get != 200:
            self.send_json(404, {"error": "schedule_not_found"})
            return
        # Strategic merge patch — adds MARKER to container env, immutable fields unchanged
        patch = {
            "spec": {
                "jobTemplate": {
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [{
                                    "name": "exporter",
                                    "env": [{"name": "MARKER", "value": marker}],
                                }]
                            }
                        }
                    }
                }
            }
        }
        s_patch, patch_result = _k3s_request(
            "PATCH",
            f"/apis/batch/v1/namespaces/{NAMESPACE}/cronjobs/{cronjob_name}",
            body=patch, bearer=sa_token,
        )
        if s_patch == 403:
            self.send_json(403, {"error": "k3s_rbac_denied"})
            return
        if s_patch not in (200, 201):
            self.send_json(502, {"error": f"k3s_patch_failed: {s_patch}"})
            return
        result = {
            "schema": "fieldkest.schedule-patch/v1",
            "schedule_id": schedule_id.upper(),
            "marker": marker,
            "patched": True,
        }
        append_audit(AUDIT, "schedule-patches", {
            "request_id": self.request_id, "schedule_id": schedule_id.upper(),
            "marker": marker, "status": 200,
        })
        self.send_json(200, result)

    def do_PATCH(self) -> None:
        """K15.3: PATCH the export destination using the export SA token.

        Delegated patch rights allow svc-fieldlink-export to change the destination
        field. The cloud-api validates the token and only patches the destination
        (not owner/tenant/partition_bindings — those are immutable). The K3s PATCH
        is real: it updates the ConfigMap data field for 'destination'.
        """
        path = urlsplit(self.path).path
        # /api/exports/{id}/destination: K15.3 — authenticated by export SA token
        # /api/schedules/{id}: K16.2 — PATCH the CronJob startup behavior
        if path.startswith("/api/schedules/") and not path.endswith("/runs"):
            schedule_id = path.removeprefix("/api/schedules/")
            self._patch_schedule(schedule_id)
            return
        if path.endswith("/destination") and "/api/exports/" in path:
            export_id = path.removeprefix("/api/exports/").removesuffix("/destination")
            self._patch_destination(export_id)
            return
        self.send_json(404, {"error": "not_found"})

    def _patch_destination(self, export_id: str) -> None:
        """K15.3: redirect the export handover destination.

        Uses real K3s strategic merge patch on the exp-2841-definition ConfigMap.
        Only the destination field is updated — owner, tenant, partition_bindings
        are immutable and not touched. The Job spec (batch/v1 Job) is not changed.
        RBAC: svc-fieldlink-export has patch rights on exp-2841-definition.
        """
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json(401, {"error": "export_token_required"})
            return
        sa_token = auth[7:].strip()
        try:
            body = self.read_json(32_768)
            new_destination = str(body.get("destination", ""))
            if not new_destination:
                raise ValueError("destination_required")
        except (ValueError, TypeError):
            self.send_json(422, {"error": "destination_required"})
            return
        configmap_name = f"{export_id.lower()}-definition"
        # Compute new revision: read current revision, increment
        get_status, cm_data = _k3s_request(
            "GET",
            f"/api/v1/namespaces/{NAMESPACE}/configmaps/{configmap_name}",
            bearer=sa_token,
        )
        if get_status == 403:
            self.send_json(403, {"error": "k3s_rbac_denied"})
            return
        if get_status != 200:
            self.send_json(502, {"error": f"k3s_returned_{get_status}"})
            return
        current_data = cm_data.get("data", {})
        old_destination = current_data.get("destination", "")
        try:
            current_rev = int(current_data.get("revision", 6))
        except (ValueError, TypeError):
            current_rev = 6
        new_revision = current_rev + 1
        # Real K3s strategic merge patch — only updates destination and revision
        patch_body = {
            "data": {
                "destination": new_destination,
                "revision": str(new_revision),
            }
        }
        patch_status, patch_result = _k3s_request(
            "PATCH",
            f"/api/v1/namespaces/{NAMESPACE}/configmaps/{configmap_name}",
            body=patch_body,
            bearer=sa_token,
        )
        if patch_status == 403:
            self.send_json(403, {"error": "k3s_rbac_denied"})
            return
        if patch_status not in (200, 201):
            self.send_json(502, {"error": f"k3s_patch_failed: {patch_status}"})
            return
        result = {
            "schema": "fieldkest.export-destination-change/v1",
            "export_id": export_id,
            "old_destination": old_destination,
            "destination": new_destination,
            "revision": new_revision,
        }
        append_audit(AUDIT, "export-destination-changes", {
            "request_id": self.request_id, "export_id": export_id,
            "old_destination": old_destination, "new_destination": new_destination,
            "revision": new_revision, "status": 200,
        })
        self.send_json(200, result)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        # K14.2: role-exchange authenticated by workload SA token (not developer credentials).
        # The endpoint validates issuer and subject but OMITS audience check (the vulnerability).
        if path.startswith("/api/token-exchange/"):
            role = path.removeprefix("/api/token-exchange/")
            self._role_exchange(role)
            return
        if not self._developer():
            self.send_json(401, {"error": "authentication_required"})
            return
        if path == "/api/workspaces/current/token-exchange":
            self._issue_workload_token()
            return
        # /api/schedules/{id}/runs: K16.2 — create a fresh Job from the patched CronJob
        if path.endswith("/runs") and "/api/schedules/" in path:
            schedule_id = path.removeprefix("/api/schedules/").removesuffix("/runs")
            self._schedule_run(schedule_id)
            return
        # /api/exports/{id}/runs: K15.4 — POST a collection run for the export.
        # Validates partition/tenant/connector_revision against real PostgreSQL records.
        # Writes versioned export object to real SeaweedFS. Cross-tenant → 422.
        if path.endswith("/runs") and "/api/exports/" in path:
            export_id = path.removeprefix("/api/exports/").removesuffix("/runs")
            self._export_run(export_id)
            return
        self.send_json(404, {"error": "not_found"})

    def _trust_record_via_workload(self, trust_id: str) -> None:
        """K14.1: read the trust document via K3s ConfigMap using the participant's SA token.

        The trust record is a real K3s ConfigMap containing the workload's trust context:
        issuer, subject, accepted_audiences (from the real K3s JWT claims), and
        export_role (the K14.2 scope boundary). The data flows from real K3s token claims,
        not from a canned document.

        RBAC: svc-fieldlink-workload has GET on trust-flx-04 only.
        """
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json(401, {"error": "workload_token_required"})
            return
        sa_token = auth[7:].strip()
        configmap_name = trust_id.lower()
        status, data = _k3s_request(
            "GET",
            f"/api/v1/namespaces/{NAMESPACE}/configmaps/{configmap_name}",
            bearer=sa_token,
        )
        if status == 200:
            cm_data = data.get("data", {})
            result = {
                "schema": "fieldkest.trust-record/v1",
                "trust_id": trust_id,
                **cm_data,
            }
            append_audit(AUDIT, "trust-records", {
                "request_id": self.request_id,
                "trust_id": trust_id, "subject": cm_data.get("subject"),
                "status": 200,
            })
            self.send_json(200, result)
        elif status == 403:
            append_audit(AUDIT, "trust-records", {
                "request_id": self.request_id, "trust_id": trust_id,
                "denied_by": "k3s_rbac", "status": 403,
            })
            self.send_json(403, {"error": "k3s_rbac_denied"})
        elif status == 404:
            self.send_json(404, {"error": "trust_record_not_found"})
        else:
            self.send_json(502, {"error": f"k3s_returned_{status}"})

    def _role_exchange(self, role: str) -> None:
        """K14.2: exchange a workload SA token for a scoped export role token.

        VULNERABILITY: validates the K3s token's issuer and subject but does NOT
        check its audience. The K13.4 token has default K3s audiences (not
        fieldkest-export-access), but matching subject and issuer allow claiming
        the export role. This is the K14.2 trust-policy flaw.

        Issues a REAL K3s TokenRequest for svc-fieldlink-export with audience
        fieldkest-export-access. K3s RBAC then enforces scope on that token.
        """
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json(401, {"error": "workload_token_required"})
            return
        input_token = auth[7:].strip()
        # Validate the token using K3s TokenReview (checks issuer and subject)
        # OMITS audience check — this is the vulnerability
        status, review = _k3s_request(
            "POST",
            "/apis/authentication.k8s.io/v1/tokenreviews",
            body={
                "apiVersion": "authentication.k8s.io/v1",
                "kind": "TokenReview",
                "spec": {"token": input_token},
            },
        )
        if status != 201 or not review.get("status", {}).get("authenticated"):
            self.send_json(401, {"error": "workload_token_invalid"})
            return
        user_info = review["status"].get("user", {})
        username = user_info.get("username", "")
        # Policy check: issuer (implicit in K3s auth) and subject must match
        # expected workload. Audience is NOT checked — vulnerability.
        expected_subject = f"system:serviceaccount:{NAMESPACE}:{WORKLOAD_SA}"
        if username != expected_subject:
            self.send_json(403, {"error": "subject_mismatch"})
            return
        # Issue export role token for svc-fieldlink-export with the specific audience
        status2, data2 = _k3s_request(
            "POST",
            f"/api/v1/namespaces/{NAMESPACE}/serviceaccounts/svc-fieldlink-export/token",
            body={
                "apiVersion": "authentication.k8s.io/v1",
                "kind": "TokenRequest",
                "spec": {
                    "audiences": [role],  # e.g. fieldkest-export-access
                    "expirationSeconds": 3600,
                },
            },
        )
        if status2 != 201:
            self.send_json(503, {"error": f"export_token_request_failed: {status2}"})
            return
        export_token = data2["status"]["token"]
        result = {
            "schema": "fieldkest.role-session/v1",
            "role": f"role/support-export-editor",
            "audience": role,
            "access_token": export_token,
            "principal": "svc-fieldlink-export",
            "accepted_input_audience": "fieldkest-build-records",
            "expires_in": 3600,
        }
        append_audit(AUDIT, "role-exchange", {
            "request_id": self.request_id, "role": role,
            "input_subject": username, "output_principal": "svc-fieldlink-export",
            "status": 201,
        })
        self.send_json(201, result)

    def _export_definition(self, export_id: str) -> None:
        """K15.2: read the export definition via K3s ConfigMap using the export SA token.

        OWNERSHIP GAP: the detail route checks tenant visibility (the token belongs to
        svc-fieldlink-export which has the export role) but does NOT check that the
        requesting identity owns the export job. maya.ranscombe owns EXP-2841 but
        svc-fieldlink-export can read its definition via K3s RBAC.

        K3s RBAC enforces access — no Python ownership check.
        """
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json(401, {"error": "export_token_required"})
            return
        sa_token = auth[7:].strip()
        configmap_name = f"{export_id.lower()}-definition"
        status, data = _k3s_request(
            "GET",
            f"/api/v1/namespaces/{NAMESPACE}/configmaps/{configmap_name}",
            bearer=sa_token,
        )
        if status == 200:
            cm = data.get("data", {})
            import ast
            result = {
                "schema": "fieldkest.export-definition/v1",
                "export_id": cm.get("export_id"),
                "owner": cm.get("owner"),
                "tenant": cm.get("tenant"),
                "case_id": cm.get("case_id"),
                "partitions": json.loads(cm.get("partitions", "[]")),
                "destinations": json.loads(cm.get("destinations", "[]")),
                "partition_bindings": json.loads(cm.get("partition_bindings", "[]")),
            }
            append_audit(AUDIT, "export-definitions", {
                "request_id": self.request_id, "export_id": result["export_id"],
                "owner": result["owner"], "tenant": result["tenant"],
                "accessor": "svc-fieldlink-export", "status": 200,
            })
            self.send_json(200, result)
        elif status == 403:
            self.send_json(403, {"error": "k3s_rbac_denied"})
        elif status == 404:
            self.send_json(404, {"error": "export_definition_not_found"})
        else:
            self.send_json(502, {"error": f"k3s_returned_{status}"})

    def _schedule_context(self, schedule_id: str) -> None:
        """K16.3: return the execution identity of the scheduled task.

        The CronJob runs under svc-schedule-runner — a separate K3s ServiceAccount
        that outlives the participant's export session. The participant's export SA
        token expires; svc-schedule-runner's auto-mounted token persists.

        This endpoint shows the execution SA and its token for the participant to
        prove the separate identity acts after the session ends.
        """
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json(401, {"error": "export_token_required"})
            return
        sa_token = auth[7:].strip()
        cronjob_name = schedule_id.lower()
        # Read CronJob to find its serviceAccountName
        s, cj = _k3s_request(
            "GET", f"/apis/batch/v1/namespaces/{NAMESPACE}/cronjobs/{cronjob_name}",
            bearer=sa_token,
        )
        if s != 200:
            self.send_json(404 if s == 404 else 403, {"error": "schedule_not_found"})
            return
        runner_sa = (cj["spec"]["jobTemplate"]["spec"]["template"]["spec"]
                     .get("serviceAccountName", "default"))
        # Issue a token for the schedule runner SA to demonstrate its identity
        s_tok, tok_data = _k3s_request(
            "POST",
            f"/api/v1/namespaces/{NAMESPACE}/serviceaccounts/{runner_sa}/token",
            body={"apiVersion": "authentication.k8s.io/v1", "kind": "TokenRequest",
                  "spec": {"expirationSeconds": 3600}},
        )
        runner_token = tok_data.get("status", {}).get("token") if s_tok == 201 else None
        result = {
            "schema": "fieldkest.schedule-context/v1",
            "schedule_id": schedule_id.upper(),
            "runner_sa": runner_sa,
            "runner_token": runner_token,
            "note": "svc-schedule-runner outlives the participant session; "
                    "the CronJob runs under this identity after export SA expires",
        }
        append_audit(AUDIT, "schedule-context", {
            "request_id": self.request_id, "schedule_id": schedule_id.upper(),
            "runner_sa": runner_sa, "status": 200,
        })
        self.send_json(200, result)

    def _schedule_summary(self, schedule_id: str) -> None:
        """K16.1: read the real K3s CronJob spec for the support schedule.

        The K3s CronJob sched-2841 is the recurring support-export workflow that
        runs after the current operator's shift ends (daily 08:00). The participant
        reads this using the K14.2 export SA token.
        RBAC: svc-fieldlink-export has GET on CronJob sched-2841.
        """
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json(401, {"error": "export_token_required"})
            return
        sa_token = auth[7:].strip()
        cronjob_name = schedule_id.lower()
        status, data = _k3s_request(
            "GET",
            f"/apis/batch/v1/namespaces/{NAMESPACE}/cronjobs/{cronjob_name}",
            bearer=sa_token,
        )
        if status == 200:
            containers = (data.get("spec", {}).get("jobTemplate", {})
                          .get("spec", {}).get("template", {})
                          .get("spec", {}).get("containers", []))
            env_map = {e["name"]: e["value"] for c in containers for e in c.get("env", [])}
            labels = data.get("metadata", {}).get("labels", {})
            result = {
                "schema": "fieldkest.schedule/v1",
                "schedule_id": env_map.get("SCHEDULE_ID", schedule_id.upper()),
                "assignment": env_map.get("ASSIGNMENT") or labels.get("fieldkest.io/case-id"),
                "cron": data["spec"].get("schedule"),
                "profile": env_map.get("PROFILE"),
                "startup_config": env_map.get("STARTUP_CONFIG"),
                "destination": env_map.get("DESTINATION"),
                "case_id": env_map.get("CASE_ID") or labels.get("fieldkest.io/case-id"),
            }
            append_audit(AUDIT, "schedules", {
                "request_id": self.request_id, "schedule_id": result["schedule_id"],
                "assignment": result["assignment"], "cron": result["cron"], "status": 200,
            })
            self.send_json(200, result)
        elif status == 403:
            self.send_json(403, {"error": "k3s_rbac_denied"})
        elif status == 404:
            self.send_json(404, {"error": "schedule_not_found"})
        else:
            self.send_json(502, {"error": f"k3s_returned_{status}"})

    def _export_job_summary(self, export_id: str) -> None:
        """K15.1: read the real K3s Job spec for the export job.

        The export job exp-2841 is a real K3s batch/v1 Job in the fieldlink namespace.
        It contains the dataset name, revision, and state in its container env vars.
        RBAC: svc-fieldlink-export can read this specific Job; svc-fieldlink-workload cannot.
        """
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json(401, {"error": "export_token_required"})
            return
        sa_token = auth[7:].strip()
        job_name = export_id.lower()
        status, data = _k3s_request(
            "GET",
            f"/apis/batch/v1/namespaces/{NAMESPACE}/jobs/{job_name}",
            bearer=sa_token,
        )
        if status == 200:
            # Extract job summary from K3s Job spec env vars
            containers = data.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            env_map = {}
            for container in containers:
                for env in container.get("env", []):
                    env_map[env["name"]] = env["value"]
            labels = data.get("metadata", {}).get("labels", {})
            result = {
                "schema": "fieldkest.export-job/v1",
                "export_id": env_map.get("EXPORT_ID", export_id.upper()),
                "case_id": env_map.get("CASE_ID") or labels.get("fieldkest.io/case-id"),
                "dataset": env_map.get("DATASET"),
                "revision": int(env_map.get("REVISION", 0)),
                "state": env_map.get("STATE", "unpublished"),
                "destination": env_map.get("DESTINATION"),
                "job_name": data["metadata"]["name"],
            }
            append_audit(AUDIT, "export-jobs", {
                "request_id": self.request_id, "export_id": result["export_id"],
                "dataset": result["dataset"], "revision": result["revision"], "status": 200,
            })
            self.send_json(200, result)
        elif status == 403:
            self.send_json(403, {"error": "k3s_rbac_denied"})
        elif status == 404:
            self.send_json(404, {"error": "export_job_not_found"})
        else:
            self.send_json(502, {"error": f"k3s_returned_{status}"})

    def _schedule_run(self, schedule_id: str) -> None:
        """K16.2: create a fresh K3s Job from the patched CronJob template.

        Proves that the MARKER patch persists and takes effect in the new Job.
        The support output (ASSIGNMENT, PROFILE, STARTUP_CONFIG) must remain unchanged.
        RBAC: svc-fieldlink-export has create Jobs permission.
        """
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json(401, {"error": "export_token_required"})
            return
        sa_token = auth[7:].strip()
        import uuid as _uuid
        job_name = f"{schedule_id.lower()}-run-{_uuid.uuid4().hex[:6]}"
        cronjob_name = schedule_id.lower()
        # Read the current CronJob to get its template
        s_cj, cj = _k3s_request(
            "GET", f"/apis/batch/v1/namespaces/{NAMESPACE}/cronjobs/{cronjob_name}",
            bearer=sa_token,
        )
        if s_cj != 200:
            self.send_json(404, {"error": "schedule_not_found"})
            return
        # Create Job from CronJob template
        template = cj["spec"]["jobTemplate"]["spec"]
        job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": NAMESPACE,
                "labels": {"fieldkest.io/from-schedule": cronjob_name},
            },
            "spec": template,
        }
        s_job, job_result = _k3s_request(
            "POST", f"/apis/batch/v1/namespaces/{NAMESPACE}/jobs",
            body=job, bearer=sa_token,
        )
        if s_job == 403:
            self.send_json(403, {"error": "k3s_rbac_denied"})
            return
        if s_job not in (201, 200):
            self.send_json(502, {"error": f"job_create_failed: {s_job}"})
            return
        # Extract env vars from the created Job
        containers = (job_result.get("spec", {}).get("template", {})
                      .get("spec", {}).get("containers", []))
        env_map = {e["name"]: e["value"] for c in containers for e in c.get("env", [])}
        result = {
            "schema": "fieldkest.schedule-run/v1",
            "schedule_id": schedule_id.upper(),
            "job_name": job_name,
            "marker": env_map.get("MARKER"),
            "assignment": env_map.get("ASSIGNMENT"),
            "profile": env_map.get("PROFILE"),
            "startup_config": env_map.get("STARTUP_CONFIG"),
        }
        append_audit(AUDIT, "schedule-runs", {
            "request_id": self.request_id, "schedule_id": schedule_id.upper(),
            "job_name": job_name, "marker": env_map.get("MARKER"), "status": 201,
        })
        self.send_json(201, result)

    def _export_run(self, export_id: str) -> None:
        """K15.4: collect the export by resolving partition join against real PostgreSQL.

        1. Validates export SA token (K14.2).
        2. Gets K3s export definition to find current destination.
        3. Validates partition/tenant/connector_revision against real PostgreSQL.
        4. Writes versioned export object to real SeaweedFS.
        5. Returns 201 with destination on success; 422 for cross-tenant.
        """
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json(401, {"error": "export_token_required"})
            return
        sa_token = auth[7:].strip()
        try:
            body = self.read_json(32_768)
            tenant = str(body.get("tenant", ""))
            connector_revision = str(body.get("connector_revision", ""))
            partitions = list(body.get("partitions", []))
            if not tenant or not connector_revision or not partitions:
                raise ValueError("tenant_connector_revision_partitions_required")
        except (ValueError, TypeError):
            self.send_json(422, {"error": "tenant_connector_revision_partitions_required"})
            return
        # Validate the export SA token
        status_tr, review = _k3s_request(
            "POST", "/apis/authentication.k8s.io/v1/tokenreviews",
            body={"apiVersion": "authentication.k8s.io/v1", "kind": "TokenReview",
                  "spec": {"token": sa_token}},
        )
        if status_tr != 201 or not review.get("status", {}).get("authenticated"):
            self.send_json(401, {"error": "export_token_invalid"})
            return
        # Get the current export definition from K3s to find destination
        cm_name = f"{export_id.lower()}-definition"
        s_def, cm_data = _k3s_request(
            "GET", f"/api/v1/namespaces/{NAMESPACE}/configmaps/{cm_name}",
            bearer=sa_token,
        )
        if s_def != 200:
            self.send_json(404, {"error": "export_definition_not_found"})
            return
        cm = cm_data.get("data", {})
        export_tenant = cm.get("tenant", "")
        destination = cm.get("destination", "")
        # K15.4 cross-tenant rejection: submitted tenant must match export tenant
        if tenant != export_tenant:
            self.send_json(422, {"error": "cross_tenant_collection_refused",
                                 "export_tenant": export_tenant,
                                 "submitted_tenant": tenant})
            return
        # Validate partition binding against real PostgreSQL
        pg_valid = _validate_partition_binding(
            export_id=export_id, tenant=tenant,
            partition=partitions[0] if partitions else "",
            connector_revision=connector_revision,
        )
        if not pg_valid:
            self.send_json(422, {"error": "partition_binding_not_found_in_postgresql"})
            return
        # Write versioned export object to real SeaweedFS
        collection_key = f"{partitions[0]}-rev{cm.get('revision', '6')}.json"
        s3_ok, s3_resp = _write_export_object(
            export_id=export_id, destination=destination,
            collection_key=collection_key,
            payload=json.dumps({
                "export_id": export_id, "tenant": tenant,
                "partition": partitions[0], "connector_revision": connector_revision,
                "destination": destination,
            }).encode(),
        )
        if not s3_ok:
            self.send_json(503, {"error": f"seaweedfs_write_failed: {s3_resp}"})
            return
        result = {
            "schema": "fieldkest.export-run/v1",
            "export_id": export_id,
            "tenant": tenant,
            "partitions": partitions,
            "connector_revision": connector_revision,
            "destination": destination,
            "collection_key": collection_key,
            "revision": int(cm.get("revision", 6)),
        }
        append_audit(AUDIT, "export-runs", {
            "request_id": self.request_id, "export_id": export_id,
            "tenant": tenant, "partitions": partitions,
            "destination": destination, "status": 201,
        })
        self.send_json(201, result)

    def _export_credentials(self, export_id: str) -> None:
        """K14.3: provide SeaweedFS export credentials after validating the K14.2 SA token.

        The svc-fieldlink-export SeaweedFS identity has restricted S3 access to
        fieldkest-exports/exports/support%2fEXP-2841 (using %2f-encoded path in s3.json).
        SeaweedFS decodes %2f after prefix comparison to allow exactly this one object.

        The developer identity (rowan.ito) has NO access to fieldkest-exports — this is
        the boundary: denied before obtaining export credentials, allowed after.

        This endpoint validates the K14.2 export SA token (K3s TokenReview) and returns
        the svc-fieldlink-export SeaweedFS credentials for use with the objects.keplerops.test
        S3 endpoint.
        """
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json(401, {"error": "export_token_required"})
            return
        sa_token = auth[7:].strip()
        # Validate the export SA token (K3s TokenReview)
        status_tr, review = _k3s_request(
            "POST",
            "/apis/authentication.k8s.io/v1/tokenreviews",
            body={"apiVersion": "authentication.k8s.io/v1", "kind": "TokenReview",
                  "spec": {"token": sa_token}},
        )
        if status_tr != 201 or not review.get("status", {}).get("authenticated"):
            self.send_json(401, {"error": "export_token_invalid"})
            return
        username = review["status"]["user"]["username"]
        expected = f"system:serviceaccount:{NAMESPACE}:svc-fieldlink-export"
        if username != expected:
            self.send_json(403, {"error": "export_identity_required"})
            return
        # Read SeaweedFS export credentials from operator directory
        cred_file = Path(os.environ.get("EXPORT_CREDENTIALS_FILE",
                                        "/etc/cloud-api/export-credentials"))
        if not cred_file.is_file():
            self.send_json(503, {"error": "export_credentials_unavailable"})
            return
        # Parse aws credentials file
        lines = cred_file.read_text().splitlines()
        access_key = next((l.split("=", 1)[1].strip() for l in lines
                           if l.startswith("aws_access_key_id")), "")
        secret_key = next((l.split("=", 1)[1].strip() for l in lines
                           if l.startswith("aws_secret_access_key")), "")
        result = {
            "schema": "fieldkest.export-credentials/v1",
            "export_id": export_id,
            "endpoint": "https://objects.keplerops.test",
            "bucket": "fieldkest-exports",
            "key": f"exports/support/{export_id}",
            "access_key_id": access_key,
            "secret_access_key": secret_key,
            "region": "us-east-1",
            "note": "Resource rule uses %2f-encoded path; SeaweedFS decodes after prefix comparison",
        }
        append_audit(AUDIT, "export-credentials", {
            "request_id": self.request_id, "export_id": export_id,
            "principal": username, "status": 200,
        })
        self.send_json(200, result)

    def _policy_via_export_token(self, policy_id: str) -> None:
        """K14.2: read the protected role record using the export SA token.

        RBAC: svc-fieldlink-export can read role-export-access; svc-fieldlink-workload
        cannot. K3s enforces this — not Python.
        """
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json(401, {"error": "export_token_required"})
            return
        sa_token = auth[7:].strip()
        configmap_name = policy_id.lower().replace("/", "-").replace("_", "-")
        status, data = _k3s_request(
            "GET",
            f"/api/v1/namespaces/{NAMESPACE}/configmaps/{configmap_name}",
            bearer=sa_token,
        )
        if status == 200:
            cm_data = data.get("data", {})
            result = {"schema": "fieldkest.role-record/v1", "policy_id": policy_id, **cm_data}
            append_audit(AUDIT, "policies", {
                "request_id": self.request_id, "policy_id": policy_id,
                "principal": cm_data.get("principal"), "status": 200,
            })
            self.send_json(200, result)
        elif status == 403:
            self.send_json(403, {"error": "k3s_rbac_denied"})
        elif status == 404:
            self.send_json(404, {"error": "policy_not_found"})
        else:
            self.send_json(502, {"error": f"k3s_returned_{status}"})

    def _workspace_exchange(self) -> None:
        """Return workspace exchange info (trust context, cluster info)."""
        result = {
            "schema": "fieldkest.workspace-exchange/v1",
            "cluster": "fieldlink",
            "namespace": NAMESPACE,
            "workload_sa": WORKLOAD_SA,
            "fixture_token": "FIXTURE-" + secrets.token_hex(8).upper(),
            "trust_record": "TRUST-" + hashlib.sha256(WORKLOAD_SA.encode()).hexdigest()[:16].upper(),
            "token_endpoint": "/api/workspaces/current/token-exchange",
        }
        append_audit(AUDIT, "workspace-exchange", {
            "request_id": self.request_id, "principal": USERNAME, "status": 200,
        })
        self.send_json(200, result)

    def _issue_workload_token(self) -> None:
        """K13.4: issue a REAL K3s service-account token for svc-fieldlink-workload.

        Uses the K3s TokenRequest API (admin credentials) to mint a short-lived
        SA token. The token is scoped by K3s RBAC — it can only read bld-1842.
        """
        try:
            self.read_json(1024)  # consume body (must be {})
        except (ValueError, TypeError):
            pass
        status, data = _k3s_request(
            "POST",
            f"/api/v1/namespaces/{NAMESPACE}/serviceaccounts/{WORKLOAD_SA}/token",
            body={
                "apiVersion": "authentication.k8s.io/v1",
                "kind": "TokenRequest",
                "spec": {"expirationSeconds": 3600},
            },
        )
        if status != 201:
            append_audit(AUDIT, "workspace-token", {
                "request_id": self.request_id, "principal": USERNAME,
                "k3s_status": status, "status": 503,
            })
            self.send_json(503, {"error": f"k3s_token_request_failed: {status}"})
            return
        sa_token = data["status"]["token"]
        result = {
            "schema": "fieldkest.workspace-token/v1",
            "access_token": sa_token,
            "principal": WORKLOAD_SA,
            "namespace": NAMESPACE,
            "expires_in": 3600,
        }
        append_audit(AUDIT, "workspace-token", {
            "request_id": self.request_id, "principal": USERNAME,
            "workload_sa": WORKLOAD_SA, "status": 201,
        })
        RESULTS.mkdir(parents=True, exist_ok=True)
        result_id = "WSAT-" + secrets.token_hex(6).upper()
        (RESULTS / f"{result_id}.json").write_text(
            json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
        )
        self.send_json(201, result)

    def _build_record_history_recovery(self, build_id: str) -> None:
        """K30.1: History recovery build record — accepts K09.4 (release_reader) or K13.4 (workload).

        Returns the svc-history-recovery principal with backup BAK-2026-021 and a
        scoped restore session. Source database direct-access is denied (K30.2 setup).
        """
        auth = self.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ") if auth.startswith("Bearer ") else None
        # Accept K09.4 path (release_reader exchange handle) or K13.4 path (workload session)
        if token not in {RELEASE_READER_TOKEN, WORKLOAD_SESSION}:
            if not self._developer():
                self.send_json(401, {"error": "authentication_required"})
                return
        result = {
            "schema": "fieldkest.build-record/v1",
            "build_id": build_id,
            "classification": "history-recovery",
            "principal": "svc-history-recovery",
            "backup": "BAK-2026-021",
            "session": HISTORY_RECOVERY_SESSION,
            "allowed": "restore",
            "source_database": "denied",
        }
        append_audit(AUDIT, "build-records", {
            "request_id": self.request_id,
            "build_id": build_id,
            "principal": "svc-history-recovery",
            "status": 200,
        })
        self.send_json(200, result)

    def _build_record_release_dossier(self, build_id: str) -> None:
        """K29.1: return the release-dossier build record with the exchange handle.

        Flaw: checks project membership (developer auth) but omits release-dossier
        entitlement check. Any project member can recover the exchange handle, which
        grants access to the CI release-dossier artifact naming the signer repository.
        """
        if not self._developer():
            self.send_json(401, {"error": "authentication_required"})
            return
        result = {
            "schema": "fieldkest.build-record/v1",
            "build_id": build_id,
            "classification": "release-dossier",
            "status": "retained",
            "release_principal": "release-reader",
            "exchange_handle": RELEASE_READER_TOKEN,
        }
        append_audit(AUDIT, "build-records", {
            "request_id": self.request_id,
            "build_id": build_id,
            "principal": USERNAME,
            "classification": "release-dossier",
            "status": 200,
        })
        self.send_json(200, result)

    def _build_record_via_workload(self, build_id: str) -> None:
        """K13.4: read a K3s ConfigMap using the participant's SA token.

        RBAC is enforced by REAL K3s — if the SA token cannot read this ConfigMap,
        K3s returns 403, which is forwarded here. The scope is limited to bld-1842
        by the K3s Role. This is NOT a Python scope check.
        """
        # Extract SA token from Authorization header (Bearer)
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json(401, {"error": "workload_token_required"})
            return
        sa_token = auth[7:].strip()
        # Map build_id to ConfigMap name
        configmap_name = build_id.lower().replace("_", "-")
        # Call K3s ConfigMap API with the participant's SA token (not admin token)
        # K3s enforces RBAC using the SA token's permissions
        status, data = _k3s_request(
            "GET",
            f"/api/v1/namespaces/{NAMESPACE}/configmaps/{configmap_name}",
            bearer=sa_token,
        )
        if status == 200:
            cm_data = data.get("data", {})
            result = {
                "schema": "fieldkest.build-record/v1",
                "build_id": build_id,
                **cm_data,
            }
            append_audit(AUDIT, "build-records", {
                "request_id": self.request_id,
                "build_id": build_id, "principal": cm_data.get("principal"),
                "status": 200,
            })
            self.send_json(200, result)
        elif status == 403:
            # K3s RBAC denied the read — genuine scope enforcement
            append_audit(AUDIT, "build-records", {
                "request_id": self.request_id, "build_id": build_id,
                "denied_by": "k3s_rbac", "status": 403,
            })
            self.send_json(403, {"error": "k3s_rbac_denied"})
        elif status == 404:
            self.send_json(404, {"error": "build_record_not_found"})
        else:
            self.send_json(502, {"error": f"k3s_returned_{status}"})


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    serve_tls(CloudApiHandler, port=int(os.environ.get("PORT", "443")))


if __name__ == "__main__":
    main()
