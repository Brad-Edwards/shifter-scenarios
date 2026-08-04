#!/usr/bin/env python3
"""Private metadata and Secret Manager bridge for nested Windows guests."""

from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
import os
import re
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


METADATA_ROOT = "http://metadata.google.internal/computeMetadata/v1"
METADATA_HEADERS = {"Metadata-Flavor": "Google"}
LOGICAL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
GUEST_NAME = re.compile(
    r"^(ad-dc-01|workforce-workstation-01|ml-workstation-01)$"
)
ATTRIBUTE_NAME = re.compile(r"^(ready|readback)$")
GUEST_NETWORK = ipaddress.ip_network("192.168.77.0/24")
OUTER_ADDRESS = "192.168.77.1"
GUEST_BY_ADDRESS = {
    "192.168.77.10": "ad-dc-01",
    "192.168.77.11": "workforce-workstation-01",
    "192.168.77.12": "ml-workstation-01",
}


class Bridge:
    def __init__(
        self,
        project: str,
        suffix: str,
        state_root: Path,
        secret_access: dict[str, set[str]],
    ) -> None:
        self.project = project
        self.suffix = suffix
        self.state_root = state_root
        self.secret_access = secret_access
        self.cache: dict[str, bytes] = {}
        self.metadata_paths: set[str] = set()
        self.metadata_paths_lock = threading.Lock()
        self.instance_id = str(
            int(hashlib.sha256(f"{project}:{suffix}".encode()).hexdigest()[:15], 16)
        )

    def record_metadata_path(self, guest: str, path: str) -> None:
        entry = f"{guest} {path}"
        with self.metadata_paths_lock:
            if entry in self.metadata_paths:
                return
            self.metadata_paths.add(entry)
            destination = self.state_root / "metadata-request-paths.log"
            with destination.open("a", encoding="utf-8") as handle:
                handle.write(entry + "\n")

    @staticmethod
    def _request(url: str, *, headers: dict[str, str] | None = None) -> bytes:
        request = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read()

    def secret(self, guest: str, logical_name: str) -> bytes:
        if not LOGICAL_NAME.fullmatch(logical_name):
            raise ValueError("invalid secret name")
        allowed = (
            {"ad-domain-admin-password"}
            if guest == "outer-host"
            else self.secret_access.get(guest, set())
        )
        if logical_name not in allowed:
            raise ValueError("secret is not assigned to guest")
        if logical_name in self.cache:
            return self.cache[logical_name]
        token_payload = json.loads(
            self._request(
                f"{METADATA_ROOT}/instance/service-accounts/default/token",
                headers=METADATA_HEADERS,
            )
        )
        token = token_payload["access_token"]
        secret_id = f"kep-{logical_name.replace('-', '')}-{self.suffix}"
        encoded_id = urllib.parse.quote(secret_id, safe="")
        payload = json.loads(
            self._request(
                "https://secretmanager.googleapis.com/v1/"
                f"projects/{self.project}/secrets/{encoded_id}/versions/latest:access",
                headers={"Authorization": f"Bearer {token}"},
            )
        )
        value = base64.b64decode(payload["payload"]["data"], validate=True)
        self.cache[logical_name] = value
        return value

    def write_attribute(self, guest: str, name: str, value: bytes) -> None:
        if not GUEST_NAME.fullmatch(guest) or not ATTRIBUTE_NAME.fullmatch(name):
            raise ValueError("invalid guest attribute")
        if len(value) > 64 * 1024:
            raise ValueError("guest attribute too large")
        destination = self.state_root / "guest-attributes" / guest / name
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{name}.", dir=destination.parent
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, destination)
        finally:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


class Handler(BaseHTTPRequestHandler):
    server_version = "KeplerOpsNestedMetadata/1"

    @property
    def bridge(self) -> Bridge:
        return self.server.bridge  # type: ignore[attr-defined]

    def _authorized_source(self) -> bool:
        try:
            address = ipaddress.ip_address(self.client_address[0])
        except ValueError:
            return False
        return address in GUEST_NETWORK or address.is_loopback

    def _request_guest(self) -> str | None:
        address = self.client_address[0]
        if address == OUTER_ADDRESS:
            return "outer-host"
        if address in GUEST_BY_ADDRESS:
            return GUEST_BY_ADDRESS[address]
        try:
            if ipaddress.ip_address(address).is_loopback:
                return "outer-host"
        except ValueError:
            pass
        return None

    def _send(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Metadata-Flavor", "Google")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if not self._authorized_source():
            self._send(403, b"forbidden\n", "text/plain")
            return
        try:
            request = urllib.parse.urlsplit(self.path)
            if request.path.startswith("/computeMetadata/v1/"):
                self.bridge.record_metadata_path(
                    GUEST_BY_ADDRESS.get(self.client_address[0], "nested-guest"),
                    request.path,
                )
            guest = GUEST_BY_ADDRESS.get(
                self.client_address[0],
                "nested-guest",
            )
            if request.path == "/health":
                payload = b"ready\n"
                content_type = "text/plain"
            elif request.path == "/metadata/instance/id":
                payload = self.bridge.instance_id.encode()
                content_type = "text/plain"
            elif request.path in (
                "/computeMetadata/v1/instance/hostname",
                "/computeMetadata/v1/project/hostname",
            ):
                payload = f"{guest}.keplerops.lab".encode()
                content_type = "text/plain"
            elif request.path == "/computeMetadata/v1/":
                address = self.client_address[0]
                payload = json.dumps(
                    {
                        "instance": {
                            "attributes": {},
                            "hostname": f"{guest}.keplerops.lab",
                            "id": int(self.bridge.instance_id),
                            "name": guest,
                            "networkInterfaces": [
                                {
                                    "accessConfigs": [],
                                    "ip": address,
                                    "mac": "",
                                    "network": "keplerops-windows",
                                }
                            ],
                        },
                        "project": {
                            "attributes": {},
                            "projectId": self.bridge.project,
                        },
                    },
                    separators=(",", ":"),
                ).encode()
                content_type = "application/json"
            elif request.path in (
                "/computeMetadata/v1/instance/attributes",
                "/computeMetadata/v1/instance/attributes/",
            ):
                payload = b"{}"
                content_type = "application/json"
            elif request.path.startswith("/secret/"):
                payload = self.bridge.secret(
                    self._request_guest() or "",
                    urllib.parse.unquote(request.path.removeprefix("/secret/"))
                )
                content_type = "application/octet-stream"
            else:
                self._send(404, b"not found\n", "text/plain")
                return
        except (KeyError, ValueError, json.JSONDecodeError, urllib.error.URLError):
            self._send(503, b"unavailable\n", "text/plain")
            return
        self._send(200, payload, content_type)

    def do_PUT(self) -> None:
        if not self._authorized_source():
            self._send(403, b"forbidden\n", "text/plain")
            return
        parts = self.path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "guest":
            self._send(404, b"not found\n", "text/plain")
            return
        try:
            if self._request_guest() != parts[1]:
                raise ValueError("guest cannot write another guest's attribute")
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 64 * 1024:
                raise ValueError("invalid content length")
            self.bridge.write_attribute(parts[1], parts[2], self.rfile.read(length))
        except (OSError, ValueError):
            self._send(400, b"invalid\n", "text/plain")
            return
        self._send(204, b"", "text/plain")

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--suffix", required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--secret-access", type=Path, required=True)
    parser.add_argument("--listen", default="192.168.77.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    try:
        raw_access = json.loads(args.secret_access.read_text(encoding="utf-8"))
        if (
            not isinstance(raw_access, dict)
            or set(raw_access) != set(GUEST_BY_ADDRESS.values())
            or any(
                not isinstance(names, list)
                or not names
                or any(
                    not isinstance(name, str) or not LOGICAL_NAME.fullmatch(name)
                    for name in names
                )
                for names in raw_access.values()
            )
        ):
            raise ValueError("invalid nested secret-access map")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit("invalid nested secret-access map") from exc
    secret_access = {guest: set(names) for guest, names in raw_access.items()}
    bridge = Bridge(args.project, args.suffix, args.state_root, secret_access)
    server = ThreadingHTTPServer((args.listen, args.port), Handler)
    server.bridge = bridge  # type: ignore[attr-defined]
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
