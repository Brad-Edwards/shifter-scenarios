"""Package-inspection upstream assessor.

Accepts forwarded inspection requests from the inspection service and returns
an assessment result.  Uses Python's BaseHTTPRequestHandler as the HTTP parser,
which applies Content-Length to bound the request body.  This is distinct from
the Nginx edge, which applies Transfer-Encoding when both headers are present.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import uuid

_SERVER_ID = "fieldkest-assessor/1.0 Python"


class AssessorHandler(BaseHTTPRequestHandler):
    server_version = _SERVER_ID

    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self._error(400)
            return

        if not isinstance(data, dict) or data.get("schema") != "fieldkest.inspection/v1":
            self._error(422)
            return

        response = json.dumps({
            "schema": "fieldkest.assessment-response/v1",
            "assessor_id": str(uuid.uuid4()),
            "assessment": "public-manifest-consistent",
            "forwarded_package": data.get("package"),
            "forwarded_version": data.get("version"),
            "forwarded_action": data.get("action"),
            "received_path": self.path,
        }, separators=(",", ":")).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def _error(self, status: int) -> None:
        body = json.dumps({"error": "invalid_assessment_request"}, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    HTTPServer(("127.0.0.1", 9001), AssessorHandler).serve_forever()


if __name__ == "__main__":
    main()
