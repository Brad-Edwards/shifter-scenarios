from __future__ import annotations

import hashlib
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(os.getenv("M08_NATIVE_AUDIT_ROOT", "/var/lib/m08-native-audit"))
AUTH_TOKEN = os.environ["M08_NATIVE_AUDIT_TOKEN"]
SIGNING_KEY = os.environ["M08_NATIVE_AUDIT_SIGNING_KEY"].encode()
ALLOWED_APIS = {"GetObject", "PutObject", "CompleteMultipartUpload"}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def signature(value: dict[str, Any]) -> str:
    return hmac.new(SIGNING_KEY, canonical(value), hashlib.sha256).hexdigest()


def normalize(event: dict[str, Any]) -> dict[str, Any] | None:
    api = event.get("api") or {}
    name = str(api.get("name") or event.get("apiName") or "")
    status = int(api.get("statusCode") or event.get("statusCode") or 0)
    if name not in ALLOWED_APIS or not 200 <= status < 300:
        return None
    request_id = str(event.get("requestID") or event.get("requestId") or "")
    actor = str(api.get("accessKey") or event.get("accessKey") or "")
    bucket = str(api.get("bucket") or event.get("bucketName") or "")
    object_key = str(api.get("object") or event.get("objectName") or "")
    if not all((request_id, actor, bucket, object_key)) or ".." in Path(object_key).parts:
        return None
    record = {
        "schema": "keplerops.minio-native-audit/v1",
        "request_id": request_id,
        "api": name,
        "actor": actor,
        "bucket": bucket,
        "object_key": object_key,
        "status_code": status,
        "event_time": str(event.get("time") or event.get("eventTime") or ""),
        "deployment_id": str(event.get("deploymentid") or event.get("deploymentId") or ""),
        "source": "minio-audit-webhook",
    }
    record["server_signature"] = signature(record)
    return record


class Handler(BaseHTTPRequestHandler):
    server_version = "KeplerOpsMinIOAudit/1"

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/minio-audit" or self.headers.get("Authorization") != f"Bearer {AUTH_TOKEN}":
            self.send_error(403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4 * 1024 * 1024:
                raise ValueError("invalid audit payload length")
            payload = json.loads(self.rfile.read(length))
            events = payload if isinstance(payload, list) else [payload]
            ROOT.mkdir(parents=True, exist_ok=True)
            written = 0
            for event in events:
                record = normalize(event) if isinstance(event, dict) else None
                if record is None:
                    continue
                target = ROOT / f"{hashlib.sha256(record['request_id'].encode()).hexdigest()}.json"
                if not target.exists():
                    temporary = target.with_suffix(".tmp")
                    temporary.write_bytes(canonical(record))
                    temporary.replace(target)
                written += 1
            body = canonical({"accepted": written})
            self.send_response(202)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ValueError, json.JSONDecodeError):
            self.send_error(400)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8090), Handler).serve_forever()
