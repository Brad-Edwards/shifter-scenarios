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
NAMESPACE = CONFIG.get("namespace", "fieldlink")
WORKLOAD_SA = CONFIG.get("workload_sa", "svc-fieldlink-workload")

# K3s connection credentials (from cloud-api-k3s.json mounted at startup)
_K3S_CRED_PATH = Path(os.environ.get("K3S_CREDENTIALS_FILE", "/etc/cloud-api/k3s.json"))


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
        # /api/build-records/{id}: authenticated by workload SA token (not developer token).
        # K3s RBAC enforces scope — this must be checked BEFORE developer auth.
        if path.startswith("/api/build-records/"):
            build_id = path.removeprefix("/api/build-records/")
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
