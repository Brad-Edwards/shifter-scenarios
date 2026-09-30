#!/usr/bin/env python3
"""Scoped GCE metadata token responder for the guest model container (ADR-064/067).

The range host carries a keyless, predict-only Vertex service account through
Workload Identity. The guest model container (a14-kali) is deliberately isolated
from the real metadata server so a participant with root in the container cannot
read the host's metadata surface (SSH keys, instance attributes, startup scripts).

This responder runs on the host and exposes ONLY the identity endpoints that
google-auth needs to obtain a short-lived access token for the attached service
account, proxied verbatim from the real metadata server. The guest points
google-auth at it with GCE_METADATA_HOST, so Claude Code obtains a rotating,
predict-only Vertex token with no static key, no Workload Identity Federation
pool, and no direct metadata access. Every other metadata path is refused.
"""

from __future__ import annotations

import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_REAL = "http://169.254.169.254"
_FLAVOR = ("Metadata-Flavor", "Google")

# Exact paths only. The access-token and recursive service-account queries carry a
# query string that is forwarded verbatim; the allowlist is checked on the path
# alone so no other metadata key is ever reachable through this responder.
_ALLOWED = frozenset(
    {
        "/computeMetadata/v1/",
        "/computeMetadata/v1/instance/service-accounts/default/",
        "/computeMetadata/v1/instance/service-accounts/default/token",
        "/computeMetadata/v1/instance/service-accounts/default/email",
        "/computeMetadata/v1/instance/service-accounts/default/scopes",
        "/computeMetadata/v1/project/project-id",
        "/computeMetadata/v1/project/numeric-project-id",
    }
)


def _fetch(path_with_query: str) -> tuple[int, bytes, str]:
    request = urllib.request.Request(_REAL + path_with_query, headers={_FLAVOR[0]: _FLAVOR[1]})
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - fixed link-local metadata origin
        return response.status, response.read(65536), response.headers.get("Content-Type", "application/text")


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _reply(self, code: int, body: bytes = b"", content_type: str = "application/text") -> None:
        self.send_response(code)
        self.send_header(*_FLAVOR)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        # google-auth always sends this header; requiring it rejects casual probes.
        if self.headers.get("Metadata-Flavor") != "Google":
            return self._reply(403)
        if self.path.split("?", 1)[0] not in _ALLOWED:
            return self._reply(404)
        try:
            status, body, content_type = _fetch(self.path)
        except Exception:
            return self._reply(502)
        self._reply(status, body, content_type)

    def log_message(self, *args: object) -> None:  # noqa: A003 - silence access logging
        return


def main() -> int:
    host, port = sys.argv[1], int(sys.argv[2])
    ThreadingHTTPServer((host, port), _Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
