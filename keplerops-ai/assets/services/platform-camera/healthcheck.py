"""Probe platform-camera readiness over its active local transport."""

from __future__ import annotations

import os
import socket
import ssl
import urllib.request
from pathlib import Path


CERT_FILE = Path(os.environ.get("PLATFORM_CAMERA_TLS_CERT_FILE", "/run/tls/tls.crt"))
KEY_FILE = Path(os.environ.get("PLATFORM_CAMERA_TLS_KEY_FILE", "/run/tls/tls.key"))
SERVER_NAME = os.environ.get("PLATFORM_CAMERA_TLS_SERVER_NAME", "platform-camera")
ALLOW_PLAINTEXT = os.environ.get("PLATFORM_CAMERA_ALLOW_PLAINTEXT", "0") == "1"
PLAINTEXT_READY_URL = (
    "http://127.0.0.1:8480/readyz"  # NOSONAR: gated loopback test mode.
)


def tls_readiness() -> None:
    context = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH,
        cafile=str(CERT_FILE),
    )
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    with socket.create_connection(("127.0.0.1", 8480), timeout=2) as connection:
        with context.wrap_socket(connection, server_hostname=SERVER_NAME) as secured:
            secured.sendall(
                (
                    f"GET /readyz HTTP/1.1\r\nHost: {SERVER_NAME}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("ascii")
            )
            status_line = secured.makefile("rb").readline(4_096)
    if not status_line.startswith(b"HTTP/1.1 200"):
        raise RuntimeError(f"readiness returned {status_line[:64]!r}")


def main() -> None:
    cert_readable = CERT_FILE.is_file() and os.access(CERT_FILE, os.R_OK)
    key_readable = KEY_FILE.is_file() and os.access(KEY_FILE, os.R_OK)
    if cert_readable and key_readable:
        tls_readiness()
        return
    if CERT_FILE.exists() or KEY_FILE.exists():
        raise RuntimeError("platform-camera requires both readable TLS files")
    if not ALLOW_PLAINTEXT:
        raise RuntimeError("platform-camera plaintext health checks are disabled")
    with urllib.request.urlopen(PLAINTEXT_READY_URL, timeout=2) as response:
        if response.status != 200:
            raise RuntimeError(f"readiness returned HTTP {response.status}")


if __name__ == "__main__":
    main()
