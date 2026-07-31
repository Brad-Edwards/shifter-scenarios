"""Scoped file import worker with durable queue and audit records."""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from security import confined_file, read_secret, validate_range_url
from store import StateStore, content_digest


ROOT = Path(__file__).resolve().parent


def load_config() -> dict[str, Any]:
    path = Path(
        os.environ.get("PLATFORM_CONTEXT_CONFIG", ROOT / "config/context-v1.json")
    )
    return json.loads(path.read_text(encoding="utf-8"))


class FileWorker:
    def __init__(self, store: StateStore, config: dict[str, Any]) -> None:
        self.store = store
        self.config = config
        self.adapter_url = validate_range_url(
            os.environ.get("PLATFORM_CONTEXT_ADAPTER_URL", "http://127.0.0.1:8480")
        )
        self.token_path = Path(
            os.environ.get(
                "PLATFORM_CONTEXT_TOKEN_FILE", "/run/keplerops/platform-context-token"
            )
        )
        ca_file = os.environ.get("PLATFORM_CONTEXT_CA_FILE")
        self.verify: bool | str = ca_file if ca_file else True

    def process_one(self) -> bool:
        claimed = self.store.claim_file_job()
        if claimed is None:
            self.store.heartbeat("file-import", {"state": "idle"})
            return False
        request = json.loads(claimed["request_json"])
        started = time.perf_counter()
        status = "succeeded"
        descriptor: int | None = None
        try:
            root = Path(self.config["file_roots"][request["root_id"]])
            descriptor, resolved, size = confined_file(
                root, request["relative_path"], int(self.config["file_max_bytes"])
            )
            with os.fdopen(descriptor, "rb", closefd=True) as stream:
                descriptor = None
                content = stream.read(int(self.config["file_max_bytes"]) + 1)
            if len(content) != size:
                raise ValueError("file size changed while it was read")
            result: dict[str, Any] = {
                "resolved_path": str(resolved),
                "byte_count": len(content),
                "content_base64": base64.b64encode(content).decode("ascii"),
                "content_digest": content_digest(content),
            }
            try:
                result["content_text"] = content.decode("utf-8")
            except UnicodeDecodeError:
                result["content_text"] = None
            if request["destination"] == "workhub":
                with httpx.Client(
                    verify=self.verify, timeout=httpx.Timeout(20.0, connect=3.0)
                ) as client:
                    response = client.put(
                        f"{self.adapter_url}/v1/workhub/artifacts",
                        headers={
                            "Authorization": f"Bearer {read_secret(self.token_path)}"
                        },
                        json={
                            "request_id": f"file-{request['job_id']}",
                            "path": request["destination_path"],
                            "content_base64": result["content_base64"],
                            "message": f"Import {request['relative_path']}",
                        },
                    )
                    response.raise_for_status()
                    result["workhub"] = response.json()
            self.store.finish_file_job(claimed["job_id"], "succeeded", result)
        except (OSError, ValueError, KeyError, httpx.HTTPError) as error:
            status = "failed"
            result = {"error_class": error.__class__.__name__, "error": str(error)}
            self.store.finish_file_job(claimed["job_id"], "failed", result)
        finally:
            if descriptor is not None:
                os.close(descriptor)
        self.store.record_event(
            event_name="platform_context.file_import_completed",
            operation="file.import",
            status=status,
            request_id=request["job_id"],
            request=request,
            response=result,
            source="keplerops-platform-context-file-worker",
            duration_ms=(time.perf_counter() - started) * 1_000,
        )
        self.store.heartbeat(
            "file-import", {"state": status, "job_id": request["job_id"]}
        )
        return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    store = StateStore(
        Path(
            os.environ.get(
                "PLATFORM_CONTEXT_STATE_ROOT", "/var/lib/keplerops-platform-context"
            )
        )
    )
    worker = FileWorker(store, load_config())
    if args.once:
        worker.process_one()
        return
    while True:
        if not worker.process_one():
            time.sleep(max(0.1, args.poll_seconds))


if __name__ == "__main__":
    main()
