#!/usr/bin/env python3
"""Developer documents, Forge, registry, and consumer for Training."""

from __future__ import annotations

import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import subprocess
import threading
from urllib.parse import unquote, urlsplit

from build_repository import build
from http_support import TrainingHandler, append_audit, rooted, serve, utc_now


PUBLIC = rooted("/srv/cinder-developer/public")
PRIVATE = rooted("/var/lib/cinder-developer")
AUDIT = PRIVATE / "audit"
REPOSITORY = PRIVATE / "delivery-formatter.git"
PUBLISHED = PRIVATE / "registry/published"
RECEIPTS = PRIVATE / "consumer/receipts"
RUNNER_SOCKET = Path(os.environ.get("CINDER_RUNNER_SOCKET", "/run/cinder-runner/runner.sock"))
TOKEN = "publisher_CINDER_7K4M9Q2V6R8D"
PACKAGE = "@cinder/delivery-formatter"
VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
REVISION = re.compile(r"^[0-9A-Za-z._/-]{1,128}$")
LOCK = threading.RLock()

STATIC = {
    "/": (PUBLIC / "index.md", "text/markdown; charset=utf-8"),
    "/consumer-contract.md": (PUBLIC / "consumer-contract.md", "text/markdown; charset=utf-8"),
    "/sample-package/package.json": (PUBLIC / "sample-package/package.json", "application/json"),
    "/sample-package/package-lock.json": (PUBLIC / "sample-package/package-lock.json", "application/json"),
    "/sample-package/scripts/register-rehearsal.js": (PUBLIC / "sample-package/scripts/register-rehearsal.js", "text/javascript; charset=utf-8"),
    "/sample-package/fixtures/rehearsal-source.json": (PUBLIC / "sample-package/fixtures/rehearsal-source.json", "application/json"),
}


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def version_tuple(value: str) -> tuple[int, int, int] | None:
    match = VERSION.fullmatch(value)
    return tuple(map(int, match.groups())) if match else None


def package_record(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    value.setdefault("digest", digest({key: value[key] for key in ("name", "version", "files")}))
    return value


def run_worker(source: str, input_value: dict[str, object]) -> dict[str, object]:
    request = canonical_bytes({"source": source, "input": input_value}) + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(4)
        client.connect(str(RUNNER_SOCKET))
        client.sendall(request)
        response = b""
        while not response.endswith(b"\n"):
            chunk = client.recv(65536)
            if not chunk or len(response) + len(chunk) > 1_100_000:
                raise RuntimeError("invalid runner response")
            response += chunk
    return json.loads(response)


class DeveloperHandler(TrainingHandler):
    def do_HEAD(self) -> None:
        port, path = self.server.server_port, urlsplit(self.path).path
        item = STATIC.get(path) if port == 8080 else ((PUBLIC / "build/BLD-204.log", "text/plain; charset=utf-8") if port == 8082 and path == "/jobs/BLD-204/log" else None)
        if item:
            self.send_file(*item)
        else:
            self.send_json(404, {"error": "not_found"})

    def do_GET(self) -> None:
        port = self.server.server_port
        parsed = urlsplit(self.path)
        if port == 8080:
            item = STATIC.get(parsed.path)
            self.send_file(*item) if item else self.send_json(404, {"error": "not_found"})
        elif port == 8081:
            self._forge_get(parsed)
        elif port == 8082:
            self.send_file(PUBLIC / "build/BLD-204.log", "text/plain; charset=utf-8") if parsed.path == "/jobs/BLD-204/log" else self.send_json(404, {"error": "not_found"})
        elif port == 8083:
            self._registry_get(parsed.path)
        elif port == 8084:
            self._consumer_get(parsed.path)
        else:
            self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        port, path = self.server.server_port, urlsplit(self.path).path
        if port == 8081 and path == "/cinder/delivery-formatter.git/git-upload-pack":
            self._git_backend()
        elif port == 8084 and path == "/api/consumer/run":
            self._consumer_run()
        elif port == 8084 and path == "/api/rehearsal/ingest":
            self.method_not_allowed(())
        else:
            self.send_json(404, {"error": "not_found"})

    def do_PUT(self) -> None:
        if self.server.server_port == 8083:
            self._registry_publish(urlsplit(self.path).path)
        else:
            self.method_not_allowed(("GET", "HEAD", "POST"))

    def do_DELETE(self) -> None:
        self.method_not_allowed(("GET", "HEAD", "POST", "PUT"))

    def _authorized(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {TOKEN}"

    def _forge_get(self, parsed: object) -> None:
        if parsed.path in ("/cinder/delivery-formatter.git/info/refs",):
            self._git_backend()
            return
        if parsed.path == "/cinder/delivery-formatter":
            log = subprocess.check_output(["git", "--git-dir", str(REPOSITORY), "log", "--format=%H%x09%s", "--all"], text=True)
            review = subprocess.check_output(["git", "--git-dir", str(REPOSITORY), "show", "HEAD:REVIEW.md"], text=True)
            rows = "".join(f"<li><code>{html.escape(line.split(chr(9))[0])}</code> {html.escape(line.split(chr(9))[1])}</li>" for line in log.splitlines())
            page = f"<!doctype html><html><body><h1>cinder/delivery-formatter</h1><pre>{html.escape(review)}</pre><ol>{rows}</ol></body></html>".encode()
            self.send_bytes(200, page, "text/html; charset=utf-8")
            return
        prefix = "/cinder/delivery-formatter/src/"
        if parsed.path.startswith(prefix):
            remainder = unquote(parsed.path[len(prefix) :])
            revision, separator, source_path = remainder.partition("/")
            safe_path = PurePosixPath(source_path)
            if not separator or not REVISION.fullmatch(revision) or source_path.startswith("/") or ".." in safe_path.parts:
                self.send_json(404, {"error": "source_not_found"})
                return
            result = subprocess.run(["git", "--git-dir", str(REPOSITORY), "show", f"{revision}:{source_path}"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
            self.send_bytes(200, result.stdout, "text/plain; charset=utf-8") if result.returncode == 0 else self.send_json(404, {"error": "source_not_found"})
            return
        self.send_json(404, {"error": "not_found"})

    def _git_backend(self) -> None:
        parsed = urlsplit(self.path)
        path_info = parsed.path.removeprefix("/cinder")
        if path_info == "/delivery-formatter.git/info/refs" and parsed.query != "service=git-upload-pack":
            self.send_json(400, {"error": "invalid_git_service"})
            return
        if path_info not in ("/delivery-formatter.git/info/refs", "/delivery-formatter.git/git-upload-pack"):
            self.send_json(404, {"error": "not_found"})
            return
        body = b""
        if self.command == "POST":
            try:
                body = self.read_body(8 * 1024 * 1024)
            except (ValueError, OverflowError):
                self.send_json(400, {"error": "invalid_request"})
                return
        env = os.environ.copy()
        env.update({"GIT_PROJECT_ROOT": str(PRIVATE), "GIT_HTTP_EXPORT_ALL": "1", "PATH_INFO": path_info, "QUERY_STRING": parsed.query, "REQUEST_METHOD": self.command, "CONTENT_TYPE": self.headers.get("Content-Type", ""), "CONTENT_LENGTH": str(len(body)), "REMOTE_ADDR": self.client_address[0]})
        result = subprocess.run(["git", "http-backend"], input=body, env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
        headers_raw, separator, payload = result.stdout.partition(b"\r\n\r\n")
        if not separator:
            self.send_json(500, {"error": "git_backend_error"})
            return
        status, headers = 200, []
        for line in headers_raw.decode("latin-1").split("\r\n"):
            name, value = line.split(":", 1)
            if name.lower() == "status":
                status = int(value.strip().split(" ", 1)[0])
            else:
                headers.append((name.strip(), value.strip()))
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _registry_get(self, path: str) -> None:
        if path == "/":
            self.send_bytes(200, b"GET /api/channels/rehearsal/manifest\nPUT /api/packages/@cinder/delivery-formatter/{version}\n", "text/plain; charset=utf-8")
            return
        if path != "/api/channels/rehearsal/manifest":
            self.send_json(403 if path.startswith("/api/") else 404, {"error": "scope_denied" if path.startswith("/api/") else "not_found"})
            return
        if not self._authorized():
            self.send_json(401, {"error": "invalid_bearer"})
            return
        value = json.loads((PRIVATE / "registry/channel-manifest.json").read_text(encoding="utf-8"))
        append_audit(AUDIT, "registry", {"publisher_id": "rehearsal-publisher", "package": PACKAGE, "version": None, "digest": None, "status": 200})
        self.send_json(200, value)

    def _registry_publish(self, path: str) -> None:
        prefix = "/api/packages/@cinder/delivery-formatter/"
        if not self._authorized():
            self.send_json(401, {"error": "invalid_bearer"})
            return
        if not path.startswith(prefix):
            self.send_json(403, {"error": "package_scope_denied"})
            return
        version = unquote(path[len(prefix) :])
        try:
            raw = self.read_body(262144)
        except OverflowError:
            self.send_json(413, {"error": "body_too_large"})
            return
        except ValueError:
            self.send_json(400, {"error": "invalid_request"})
            return
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "invalid_request"})
            return
        parsed_version = version_tuple(version)
        valid = isinstance(body, dict) and set(body) == {"name", "version", "files"} and body.get("name") == PACKAGE and body.get("version") == version and parsed_version is not None and (1, 4, 0) < parsed_version < (2, 0, 0)
        files = body.get("files") if isinstance(body, dict) else None
        valid = valid and isinstance(files, dict) and set(files) == {"package.json", "index.js"} and all(isinstance(value, str) for value in files.values())
        if valid:
            try:
                manifest = json.loads(files["package.json"])
                valid = isinstance(manifest, dict) and manifest.get("name") == PACKAGE and manifest.get("version") == version and manifest.get("main") == "index.js"
            except json.JSONDecodeError:
                valid = False
        if not valid:
            self.send_json(400, {"error": "invalid_package"})
            return
        package_digest = digest(body)
        destination = PUBLISHED / f"{version}.json"
        with LOCK:
            if destination.exists() or version == "1.4.0":
                self.send_json(409, {"error": "version_exists"})
                return
            record = {**body, "digest": package_digest, "published_at": utc_now(), "publisher_id": "rehearsal-publisher"}
            temporary = destination.with_suffix(".tmp")
            temporary.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            temporary.chmod(0o600)
            temporary.replace(destination)
        append_audit(AUDIT, "registry", {"publisher_id": "rehearsal-publisher", "package": PACKAGE, "version": version, "digest": package_digest, "status": 201})
        self.send_json(201, {"name": PACKAGE, "version": version, "digest": package_digest, "published_at": record["published_at"]})

    def _consumer_get(self, path: str) -> None:
        if path == "/":
            baseline = package_record(PRIVATE / "registry/packages/1.4.0.json")
            page = f"<!doctype html><html><body><h1>Delivery formatter consumer</h1><p>Baseline {baseline['version']}</p><button id='run'>Run fresh report</button><pre id='output'></pre><p><a href='/api/consumer/receipts'>Receipts</a></p><script>run.onclick=async()=>output.textContent=JSON.stringify(await fetch('/api/consumer/run',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}}).then(r=>r.json()),null,2)</script></body></html>".encode()
            self.send_bytes(200, page, "text/html; charset=utf-8")
        elif path == "/api/consumer/receipts":
            rows = [json.loads(item.read_text(encoding="utf-8")) for item in sorted(RECEIPTS.glob("CR-*.json"))]
            self.send_json(200, {"receipts": rows})
        else:
            self.send_json(404, {"error": "not_found"})

    def _consumer_run(self) -> None:
        try:
            body = json.loads(self.read_body().decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, OverflowError):
            self.send_json(400, {"error": "invalid_request"})
            return
        if body != {}:
            self.send_json(400, {"error": "invalid_request"})
            return
        candidates = [package_record(PRIVATE / "registry/packages/1.4.0.json")]
        candidates.extend(package_record(path) for path in PUBLISHED.glob("*.json"))
        selected = max(candidates, key=lambda row: version_tuple(row["version"]))
        input_value = {"delivery_id": "DL-204", "destination": "Cinder receiving desk", "parcel_count": 3}
        try:
            result = run_worker(selected["files"]["index.js"], input_value)
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError):
            self.send_json(500, {"error": "worker_unavailable"})
            return
        if not result.get("ok"):
            self.send_json(422, {"error": "formatter_failed", "detail": result.get("error")})
            return
        output = result.get("output")
        expected_summary = "DL-204 | Cinder receiving desk | 3 parcels"
        valid_keys = {"delivery_id", "destination", "parcel_count", "summary"}
        valid = isinstance(output, dict) and set(output) in (valid_keys, valid_keys | {"rehearsal_marker"}) and all(output.get(key) == value for key, value in input_value.items()) and output.get("summary") == expected_summary
        if "rehearsal_marker" in output:
            valid = valid and output["rehearsal_marker"] == "Cinder rehearsal"
        if not valid:
            self.send_json(422, {"error": "df1_validation_failed"})
            return
        with LOCK:
            sequence = len(list(RECEIPTS.glob("CR-*.json"))) + 1
            receipt_id = f"CR-{sequence:06d}"
            receipt = {"receipt_id": receipt_id, "accepted_at": utc_now(), "input": input_value, "selected_version": selected["version"], "package_digest": selected["digest"], "output": output, "output_digest": digest(output)}
            temporary = RECEIPTS / f".{receipt_id}.tmp"
            temporary.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            temporary.chmod(0o600)
            temporary.replace(RECEIPTS / f"{receipt_id}.json")
        self.send_json(200, receipt)


def main() -> None:
    for directory in (AUDIT, PUBLISHED, RECEIPTS):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    build(PRIVATE / "repository-seed.json", REPOSITORY)
    serve(DeveloperHandler, [8080, 8081, 8082, 8083, 8084])


if __name__ == "__main__":
    main()
