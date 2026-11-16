"""Package-inspection upstream assessor.

Accepts forwarded inspection requests from the inspection service and returns
an assessment result.  Uses Python's BaseHTTPRequestHandler as the HTTP parser,
which applies Content-Length to bound the request body.

Routes:
  POST /assess          -- standard inspection assessment (expects JSON)
  POST /assess/envelope -- binary envelope assessment; reads Content-Length bytes,
                           which may be LESS than the actual TCP-stream body when
                           the caller sets a smaller Content-Length than the actual
                           body.  Bytes beyond Content-Length remain in the socket
                           and become the prefix of the next request on the same
                           keep-alive connection (the K07.2 framing exploit path).
  POST /assess/privileged -- protected route; not reachable via normal
                              inspection-envelope flow; reachable only when
                              smuggled bytes from the K07.2 framing exploit
                              reach this path as a "new" assessor request.
"""
from __future__ import annotations

import json
import unicodedata
from http.server import BaseHTTPRequestHandler, HTTPServer
import uuid

_SERVER_ID = "fieldkest-assessor/1.0 Python"


class AssessorHandler(BaseHTTPRequestHandler):
    server_version = _SERVER_ID
    protocol_version = "HTTP/1.1"

    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        path = self.path.rstrip("/")

        if path == "/assess/privileged":
            # Protected route — only reachable via K07.2 smuggled bytes.
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            self._respond(200, {
                "schema": "fieldkest.assessment-response/v1",
                "assessor_id": str(uuid.uuid4()),
                "assessment": "privileged-access-confirmed",
                "finding": "support-package-approved",
                "view_binding": "internal",
                "protected": True,
            })
            return

        if path == "/assess/envelope":
            # Binary envelope route.  Reads exactly Content-Length bytes; any
            # additional bytes sent by the caller stay in the socket buffer and
            # become the prefix of the NEXT request on this keep-alive connection.
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            name_len = body[4] if len(body) > 4 else 0
            raw_name_bytes = body[5:5 + name_len] if len(body) >= 5 + name_len else b""
            try:
                raw_name = raw_name_bytes.decode("utf-8", errors="replace")
                buf = body[5:].decode("utf-8", errors="replace")
                normalized = unicodedata.normalize("NFKC", buf).casefold()[:name_len]
            except (IndexError, UnicodeDecodeError):
                raw_name = ""
                normalized = ""
            self._respond(200, {
                "schema": "fieldkest.assessment-response/v1",
                "assessor_id": str(uuid.uuid4()),
                "assessment": "public-manifest-consistent",
                "front_name_raw": raw_name,
                "assessor_name_normalized": normalized,
                "framing_disagreement": raw_name != normalized,
            })
            return

        # Standard JSON inspection route.
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self._respond(400, {"error": "invalid_assessment_request"})
            return
        if not isinstance(data, dict) or data.get("schema") != "fieldkest.inspection/v1":
            self._respond(422, {"error": "assessment_contract_failed"})
            return
        self._respond(200, {
            "schema": "fieldkest.assessment-response/v1",
            "assessor_id": str(uuid.uuid4()),
            "assessment": "public-manifest-consistent",
            "forwarded_package": data.get("package"),
            "forwarded_version": data.get("version"),
            "forwarded_action": data.get("action"),
            "received_path": self.path,
        })

    def _respond(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    HTTPServer(("127.0.0.1", 9001), AssessorHandler).serve_forever()


if __name__ == "__main__":
    main()
