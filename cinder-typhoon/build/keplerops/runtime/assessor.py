"""Package-inspection upstream assessor.

Accepts forwarded inspection requests from the inspection service and returns
an assessment result.  Uses Python's BaseHTTPRequestHandler as the HTTP parser,
which applies Content-Length to bound the request body.

Routes:
  POST /assess          -- standard inspection assessment (expects JSON)
  POST /assess/envelope -- binary envelope assessment; reads exactly
                           Content-Length bytes, which is set by the
                           inspection service to front_following_length from
                           the envelope header.  When front_following_length
                           is smaller than the total forwarded body, the
                           surplus bytes remain in the persistent HTTP/1.1
                           keep-alive socket and become the prefix of the
                           NEXT request on the same connection.  This is the
                           body-framing exploit boundary for K07.2.
  POST /assess/privileged -- authorization-bound action in the real Verdaccio
                              package workflow.  Uses the internal CI reader
                              identity to fetch the private @keplerops/
                              support-rehearsal package metadata from Verdaccio.
                              Not reachable via normal inspection flow; only
                              reachable when surplus bytes from the K07.2
                              body-framing exploit reach this path as a new
                              assessor request on the keep-alive connection.
"""
from __future__ import annotations

import base64
import http.client as _hc
import json
import pathlib
import re as _re
import ssl
from http.server import BaseHTTPRequestHandler, HTTPServer
import uuid

_SERVER_ID = "fieldkest-assessor/1.0 Python"
_CA_PATH = "/tmp/fieldkest-ca.crt"
_VERDACCIO_HOST = "packages.keplerops.test"
_PRIVATE_PACKAGE = "@keplerops/support-rehearsal"
_RESULTS_DIR = pathlib.Path("/var/lib/fieldkest-registry/results")

# Load CI reader auth at module import time so the credentials are always available.
try:
    from credentials import credential as _credential
    _CI_AUTH_B64 = base64.b64encode(
        f"svc-fieldlink-ci:{_credential('ci_registry_reader')}".encode()
    ).decode()
except Exception as _e:
    _CI_AUTH_B64 = ""
    import sys as _sys
    print(f"assessor: credentials unavailable: {_e}", file=_sys.stderr)


def _validate_inspection_id(inspection_id: str) -> dict | None:
    """Return the K07.1 trace data if inspection_id is valid, else None."""
    if not _re.fullmatch(r"INSP-[0-9A-F]{8}", inspection_id):
        return None
    trace_path = _RESULTS_DIR / f"{inspection_id}.json"
    try:
        return json.loads(trace_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _fetch_private_package() -> dict | None:
    """Fetch the private support package from Verdaccio using the CI reader identity."""
    if not _CI_AUTH_B64:
        return None
    try:
        ctx = ssl.create_default_context(cafile=_CA_PATH)
        conn = _hc.HTTPSConnection(_VERDACCIO_HOST, 443, context=ctx, timeout=5)
        encoded = _PRIVATE_PACKAGE.replace("/", "%2f").replace("@", "%40")
        conn.request("GET", f"/{encoded}", headers={"Authorization": f"Basic {_CI_AUTH_B64}"})
        resp = conn.getresponse()
        if resp.status == 200:
            data = json.loads(resp.read(131_072))
            conn.close()
            return data
    except Exception as e:
        import sys as _sys
        print(f"assessor: privileged fetch error: {e}", file=_sys.stderr)
    return None


class AssessorHandler(BaseHTTPRequestHandler):
    server_version = _SERVER_ID
    protocol_version = "HTTP/1.1"

    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        path = self.path.rstrip("/")

        if path == "/assess/privileged":
            # Authorization-bound protected action: fetch the real private package
            # from Verdaccio using the internal CI reader identity.  This route is
            # not reachable via the normal inspection-envelope flow; only the K07.2
            # surplus bytes (body-framing exploit) can reach it as a smuggled request.
            # The result is written to the shared results directory so the participant
            # can confirm the privileged access via the registry's audit route.
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            pkg = _fetch_private_package()
            if pkg is None:
                self._respond(503, {"error": "private_package_unavailable"})
                return
            assessment_id = str(uuid.uuid4())
            result = {
                "schema": "fieldkest.privileged-assessment/v1",
                "assessment_id": assessment_id,
                "assessment": "privileged-package-read",
                "package": pkg.get("name"),
                "version": pkg.get("dist-tags", {}).get("latest"),
                "description": pkg.get("description"),
                "readme": pkg.get("readme", "")[:200],
            }
            # Write to shared results directory (readable by the registry service)
            try:
                import pathlib as _pathlib
                results_dir = _pathlib.Path("/var/lib/fieldkest-registry/results")
                results_dir.mkdir(parents=True, exist_ok=True)
                (results_dir / "privileged-result.json").write_text(
                    json.dumps(result, separators=(",", ":")) + "\n"
                )
            except Exception as _e:
                import sys as _sys
                print(f"assessor: privileged result write failed: {_e}", file=_sys.stderr)
            self._respond(200, result)
            return

        if path == "/assess/inspect-privileged":
            # K07.3 protected route: requires a valid K07.1 inspection_id.
            # The body is: payload_len (2 bytes, big-endian) + inspection_id JSON.
            # Only reachable via K07.2 surplus bytes smuggled through the body-framing
            # exploit; not reachable from outside the assessor's internal port.
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                if len(body) < 3:
                    raise ValueError("body_too_short")
                payload_len = int.from_bytes(body[:2], "big")
                if 2 + payload_len > len(body):
                    raise ValueError("payload_len_exceeds_body")
                data = json.loads(body[2:2 + payload_len])
                inspection_id = str(data.get("inspection_id", ""))
            except (json.JSONDecodeError, ValueError):
                self._respond(422, {"error": "invalid_inspect_payload"})
                return
            trace = _validate_inspection_id(inspection_id)
            if trace is None:
                self._respond(403, {"error": "inspection_binding_denied"})
                return
            pkg = _fetch_private_package()
            if pkg is None:
                self._respond(503, {"error": "private_package_unavailable"})
                return
            assessment_id = str(uuid.uuid4())
            result = {
                "schema": "fieldkest.protected-assessment/v1",
                "assessment_id": assessment_id,
                "assessment": "protected-inspection-complete",
                "inspection_id": inspection_id,
                "assessor_correlation_id": trace.get("assessor_correlation_id"),
                "package": pkg.get("name"),
                "version": pkg.get("dist-tags", {}).get("latest"),
                "finding": "support-package-approved-for-release",
            }
            try:
                _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
                (_RESULTS_DIR / f"protected-assessment-{assessment_id}.json").write_text(
                    json.dumps(result, separators=(",", ":")) + "\n"
                )
            except Exception as _e:
                import sys as _sys
                print(f"assessor: protected assessment write failed: {_e}", file=_sys.stderr)
            self._respond(200, result)
            return

        if path == "/assess/envelope":
            # Binary envelope route.  Reads exactly Content-Length bytes; the
            # inspection service sets CL = front_following_length from the envelope
            # header.  Any surplus bytes beyond CL stay in the socket and become
            # the prefix of the next keep-alive request (the K07.2 exploit path).
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            self._respond(200, {
                "schema": "fieldkest.assessment-response/v1",
                "assessor_id": str(uuid.uuid4()),
                "assessment": "public-manifest-consistent",
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
