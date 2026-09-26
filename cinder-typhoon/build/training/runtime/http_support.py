"""Small HTTP helpers shared by the Training services."""

from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append_audit(directory: Path, stream: str, record: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = {"observed_at": utc_now(), **record}
    path = directory / f"{stream}.jsonl"
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(encoded)


class TrainingHandler(BaseHTTPRequestHandler):
    server_version = "CinderTraining/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_bytes(
        self,
        status: int,
        payload: bytes,
        content_type: str,
        *,
        headers: dict[str, str] | None = None,
        include_body: bool = True,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if headers:
            for name, value in headers.items():
                self.send_header(name, value)
        self.end_headers()
        if include_body and self.command != "HEAD":
            self.wfile.write(payload)

    def send_json(
        self,
        status: int,
        value: Any,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        self.send_bytes(status, payload, "application/json", headers=headers)

    def send_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_json(404, {"error": "not_found"})
            return
        self.send_bytes(200, path.read_bytes(), content_type)

    def read_body(self, maximum_bytes: int = 1_048_576) -> bytes:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None or not raw_length.isdigit():
            raise ValueError("content_length_required")
        length = int(raw_length)
        if length > maximum_bytes:
            raise OverflowError("body_too_large")
        return self.rfile.read(length)

    def method_not_allowed(self, allow: tuple[str, ...]) -> None:
        self.send_json(405, {"error": "method_not_allowed"}, headers={"Allow": ", ".join(allow)})


def serve(handler: type[BaseHTTPRequestHandler], ports: list[int]) -> None:
    servers = [ThreadingHTTPServer(("0.0.0.0", port), handler) for port in ports]
    threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in servers]
    for thread in threads:
        thread.start()
    try:
        for thread in threads:
            thread.join()
    finally:
        for server in servers:
            server.shutdown()


def rooted(path: str) -> Path:
    root = Path(os.environ.get("CINDER_ROOT", "/"))
    return root / path.removeprefix("/")
