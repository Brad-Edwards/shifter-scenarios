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
        if not self._developer():
            self.send_json(401, {"error": "authentication_required"})
            return
        if path == "/api/workspaces/current/token-exchange":
            self._workspace_exchange()
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if not self._developer():
            self.send_json(401, {"error": "authentication_required"})
            return
        if path == "/api/workspaces/current/token-exchange":
            self._issue_workload_token()
            return
        self.send_json(404, {"error": "not_found"})

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
