"""Fail-open Jupyter save-hook capture for KeplerOps research exports."""

from __future__ import annotations

import atexit
import base64
import hashlib
import http.client
import json
import os
import queue
import ssl
import threading
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse


INGEST_URL = os.environ.get(
    "KEPLEROPS_RESEARCH_INGEST_URL",
    "https://telemetry-proof-01.keplerops.lab:4319",
)
TOKEN_FILE = "/run/keplerops/producer-token"
GENERATION_FILE = "/run/keplerops/reset-generation"
PRODUCER_ID = "notebook-runner-01"
MAX_QUEUE = 256
MAX_CONTENT_BYTES = 900_000


EVENTS: queue.Queue[tuple[str, dict[str, Any]] | None] = queue.Queue(MAX_QUEUE)
WORKER_STARTED = False


def _jupyter_server_extension_points() -> list[dict[str, str]]:
    return [{"module": "keplerops_jupyter_research_capture"}]


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip()


def _reset_generation() -> int:
    try:
        return int(_read_text(GENERATION_FILE))
    except (OSError, ValueError):
        return 0


def _trace_id(path: str, content: bytes) -> str:
    material = b":".join(
        (
            str(time.time_ns()).encode(),
            path.encode(errors="replace"),
            hashlib.sha256(content).hexdigest().encode(),
        )
    )
    return hashlib.sha256(material).hexdigest()[:32]


def _base_payload(trace_id: str) -> dict[str, Any]:
    return {
        "range_instance": os.environ.get("KEPLEROPS_RANGE_INSTANCE", "unknown"),
        "participant": os.environ.get("KEPLEROPS_PARTICIPANT", "unknown"),
        "reset_generation": _reset_generation(),
        "trace_id": trace_id,
    }


def _sender() -> None:
    while True:
        item = EVENTS.get()
        if item is None:
            return
        signal, event = item
        try:
            content = json.dumps(event, separators=(",", ":"), sort_keys=True)
            body = {
                **_base_payload(str(event["trace_id"])),
                "signal": signal,
                "content": content,
            }
            parsed = urlparse(INGEST_URL)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_verify_locations(cafile="/run/tls/ca.crt")
            context.load_cert_chain("/run/tls/tls.crt", "/run/tls/tls.key")
            connection = http.client.HTTPSConnection(
                parsed.hostname or "telemetry-proof-01.keplerops.lab",
                parsed.port or 443,
                context=context,
                timeout=1.5,
            )
            connection.request(
                "POST",
                f"{parsed.path.rstrip('/')}/v1/research/content",
                body=json.dumps(body, separators=(",", ":")).encode(),
                headers={
                    "Content-Type": "application/json",
                    "X-Producer-ID": PRODUCER_ID,
                    "X-Producer-Token": _read_text(TOKEN_FILE),
                },
            )
            connection.getresponse().read()
            connection.close()
        except Exception:
            continue


def _start_worker() -> None:
    global WORKER_STARTED
    if WORKER_STARTED:
        return
    worker = threading.Thread(target=_sender, name="keplerops-jupyter-capture", daemon=True)
    worker.start()
    WORKER_STARTED = True


def _stop_worker() -> None:
    try:
        EVENTS.put_nowait(None)
    except queue.Full:
        return


atexit.register(_stop_worker)


def _signal_for_model(path: str, model: dict[str, Any]) -> str | None:
    model_type = model.get("type")
    if model_type == "notebook" or path.endswith(".ipynb"):
        return "notebook_content"
    if model_type == "file":
        return "file_content"
    return None


def _capture_event(path: str, model: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    signal = _signal_for_model(path, model)
    if signal is None:
        return None
    content = json.dumps(model.get("content"), separators=(",", ":"), sort_keys=True)
    content_bytes = content.encode()
    trace_id = _trace_id(path, content_bytes)
    return signal, {
        "trace_id": trace_id,
        "timestamp_ns": time.time_ns(),
        "path": path,
        "model_type": model.get("type"),
        "format": model.get("format"),
        "content": model.get("content"),
    }


def _enqueue(signal: str, event: dict[str, Any]) -> None:
    encoded = json.dumps(event, separators=(",", ":"), sort_keys=True).encode()
    if len(encoded) <= MAX_CONTENT_BYTES:
        try:
            EVENTS.put_nowait((signal, event))
        except queue.Full:
            return
        return
    data = base64.b64encode(encoded).decode("ascii")
    chunk_size = MAX_CONTENT_BYTES
    chunks = [data[index : index + chunk_size] for index in range(0, len(data), chunk_size)]
    for index, chunk in enumerate(chunks):
        try:
            EVENTS.put_nowait(
                (
                    signal,
                    {
                        "trace_id": event["trace_id"],
                        "timestamp_ns": event["timestamp_ns"],
                        "path": event["path"],
                        "chunked": True,
                        "encoding": "base64-json",
                        "chunk_index": index,
                        "chunk_count": len(chunks),
                        "data": chunk,
                    },
                )
            )
        except queue.Full:
            return


def _load_jupyter_server_extension(serverapp: Any) -> None:
    _start_worker()
    contents_manager = serverapp.contents_manager
    previous_hook: Callable[..., Any] | None = getattr(
        contents_manager, "pre_save_hook", None
    )

    def capture_hook(**kwargs: Any) -> None:
        if callable(previous_hook):
            previous_hook(**kwargs)
        path = kwargs.get("path")
        model = kwargs.get("model")
        if not isinstance(path, str) or not isinstance(model, dict):
            return
        try:
            event = _capture_event(path, model)
            if event is not None:
                _enqueue(*event)
        except Exception:
            return

    contents_manager.pre_save_hook = capture_hook
    log = getattr(serverapp, "log", None)
    if log is not None:
        log.info("KeplerOps Jupyter research capture hook loaded")
