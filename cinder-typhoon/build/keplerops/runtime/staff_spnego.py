"""k-staff-spnego: SPNEGO proxy for staff managed-identities endpoint.

K20.2: Verifies Authorization: Negotiate tokens against HTTP/staff.keplerops.test
keytab (staff.keytab). After verification, proxies the request to k-staff with
X-Negotiated-Principal header containing the authenticated Kerberos principal.
"""

from __future__ import annotations

import base64
import http.server
import json
import os
import socketserver
import ssl
import urllib.request
from urllib.parse import urlsplit


UPSTREAM = os.environ.get("FIELDKEST_UPSTREAM", "https://k-staff:443")


def _verify_spnego_token(token_b64: str) -> str | None:
    """Verify a SPNEGO token and return the authenticated client principal."""
    try:
        import gssapi
        ktname = os.environ.get("KRB5_KTNAME", "/run/fieldkest-staff/staff.keytab")
        os.environ["KRB5_KTNAME"] = ktname
        token_bytes = base64.b64decode(token_b64)
        name = gssapi.Name(
            "HTTP@staff.keplerops.test",
            name_type=gssapi.NameType.hostbased_service,
        )
        creds = gssapi.Credentials(name=name, usage="accept", lifetime=None)
        ctx = gssapi.SecurityContext(usage="accept", creds=creds)
        ctx.step(token_bytes)
        if ctx.complete or ctx.initiator_name:
            return str(ctx.initiator_name)
        return None
    except Exception as e:
        import sys
        print(f"SPNEGO error: {type(e).__name__}: {e}", file=sys.stderr)
        return None


class StaffSpnegoHandler(http.server.BaseHTTPRequestHandler):
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

    def _proxy_to_upstream(self, principal: str) -> None:
        """Proxy the request to k-staff with the verified principal as a header."""
        path = self.path
        url = UPSTREAM + path
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        body = None
        if self.command == "POST":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"

        req = urllib.request.Request(url, data=body, method=self.command)
        req.add_header("Host", "staff.keplerops.test")
        req.add_header("X-Negotiated-Principal", principal)
        req.add_header("X-Negotiated-Realm", "KEPLEROPS.TEST")
        if body is not None:
            req.add_header("Content-Type", self.headers.get("Content-Type", "application/json"))
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
                resp_body = r.read()
                self.send_response(r.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
        except urllib.request.HTTPError as e:
            resp_body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)

    def _handle(self) -> None:
        path = urlsplit(self.path).path

        if path == "/health":
            self._send_json(200, {"status": "up"})
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

        self._proxy_to_upstream(principal)

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()


def serve_tls(port: int = 443) -> None:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(os.environ["FIELDKEST_TLS_CERT"], os.environ["FIELDKEST_TLS_KEY"])
    server = socketserver.ThreadingTCPServer(("0.0.0.0", port), StaffSpnegoHandler, bind_and_activate=False)
    server.allow_reuse_address = True
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    server.server_bind()
    server.server_activate()
    server.serve_forever()


if __name__ == "__main__":
    serve_tls()
