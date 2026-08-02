from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def reply(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.reply(200, {"status": "ready", "renderer": "chromium"})
        else:
            self.reply(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/render":
            self.reply(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            image_url = str(payload["image_url"])
            parsed = urlparse(image_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("remote image URL must be HTTP or HTTPS")
            with tempfile.TemporaryDirectory() as directory:
                page = Path(directory) / "draft.html"
                page.write_text(
                    "<!doctype html><meta charset=utf-8><title>Support response preview</title>"
                    f"<article><p>Draft response preview</p><img src={json.dumps(image_url)} alt=\"partner context\"></article>"
                )
                completed = subprocess.run(
                    [
                        "chromium",
                        "--headless=new",
                        "--no-sandbox",
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--virtual-time-budget=5000",
                        page.as_uri(),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr[-1000:])
            self.reply(200, {"status": "rendered", "browser": "chromium", "target_host": parsed.hostname})
        except Exception as error:
            self.reply(422, {"error": str(error)})


ThreadingHTTPServer(("0.0.0.0", 8081), Handler).serve_forever()
