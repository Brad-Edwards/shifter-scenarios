"""k-identity-spnego: SPNEGO-protected identity service-relations endpoint.

K20.1: GET /api/service-relations/{service_id}
Requires: Authorization: Negotiate <GSSAPI_token> (SPNEGO/Kerberos)
Verifies the token against HTTP/identity.keplerops.test@KEPLEROPS.TEST keytab.
Returns: service relation record for the authenticated service_id.
"""

from __future__ import annotations

import base64
import http.server
import json
import os
from pathlib import Path
import socketserver
import ssl
import threading


STATE = Path(os.environ.get("FIELDKEST_STATE_ROOT", "/var/lib/fieldkest-identity-spnego"))
SERVICE_RELATIONS = json.loads((STATE / "service-relations.json").read_text())


def _verify_spnego_token(token_b64: str) -> str | None:
    """Verify a SPNEGO token and return the authenticated client principal."""
    try:
        import gssapi
        token_bytes = base64.b64decode(token_b64)
        # Accept security context using the service keytab
        ctx = gssapi.SecurityContext(usage="accept")
        ctx.step(token_bytes)
        if ctx.complete or ctx.initiator_name:
            return str(ctx.initiator_name)
        return None
    except Exception:
        return None


class SpnegoHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, code: int, data: dict) -> None:
        body = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        if path == "/health":
            self._send_json(200, {"status": "up"})
            return

        if path.startswith("/api/service-relations/"):
            service_id = path.removeprefix("/api/service-relations/")
            if not service_id or "/" in service_id:
                self._send_json(400, {"error": "invalid_service_id"})
                return

            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Negotiate "):
                self.send_response(401)
                self.send_header("WWW-Authenticate", "Negotiate")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            token_b64 = auth[len("Negotiate "):]
            principal = _verify_spnego_token(token_b64)
            if principal is None:
                self._send_json(403, {"error": "spnego_verification_failed"})
                return

            relation = SERVICE_RELATIONS.get(service_id)
            if relation is None:
                self._send_json(404, {"error": "service_relation_not_found"})
                return

            self._send_json(200, {**relation, "authenticated_principal": principal})
            return

        self._send_json(404, {"error": "not_found"})


def serve_tls(port: int = 443) -> None:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(os.environ["FIELDKEST_TLS_CERT"], os.environ["FIELDKEST_TLS_KEY"])
    server = socketserver.ThreadingTCPServer(("0.0.0.0", port), SpnegoHandler, bind_and_activate=False)
    server.allow_reuse_address = True
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    server.server_bind()
    server.server_activate()
    server.serve_forever()


if __name__ == "__main__":
    serve_tls()
