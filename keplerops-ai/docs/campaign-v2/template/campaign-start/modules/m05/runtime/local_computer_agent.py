from __future__ import annotations

import http.server
import json
import os
import urllib.error
import urllib.request


BRIDGE = "http://127.0.0.1:8877"
BRIDGE_TOKEN = os.getenv("ORION_LOCAL_AGENT_BRIDGE_TOKEN", "")


class Handler(http.server.BaseHTTPRequestHandler):
    def response(self, status: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.response(404, b'{"error":"not found"}')
            return
        self.response(200, b'{"status":"ready","agent":"orion-local-computer-use-agent"}')

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/v1/tools/host-policy", "/v1/tools/host-session"}:
            self.response(404, b'{"error":"not found"}')
            return
        target = "/v1/bridge/policy" if self.path.endswith("host-policy") else "/v1/bridge/sessions"
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        request = urllib.request.Request(
            BRIDGE + target,
            data=body,
            headers={
                "Authorization": f"Bearer {BRIDGE_TOKEN}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                self.response(response.status, response.read(), response.headers.get_content_type())
        except urllib.error.HTTPError as exc:
            self.response(exc.code, exc.read())

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", 8878), Handler).serve_forever()
