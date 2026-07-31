#!/usr/bin/env python3
"""Shared fail-open encrypted content transport for workstation recorders."""

from __future__ import annotations

import http.client
import json
import os
import queue
import ssl
import threading
from typing import Callable
from urllib.parse import urlparse


INGEST_URL = os.environ.get(
    "KEPLEROPS_RESEARCH_INGEST_URL",
    "https://telemetry-proof-01.keplerops.lab:4319",
)
TOKEN_FILE = "/run/keplerops/producer-token"
GENERATION_FILE = "/run/keplerops/reset-generation"
PRODUCER_ID = "participant-workstation"
EventQueue = queue.Queue[tuple[str, dict[str, object]] | None]


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip()


def reset_generation() -> int:
    try:
        return int(read_text(GENERATION_FILE))
    except (OSError, ValueError):
        return 0


def base_payload(trace_id: str) -> dict[str, object]:
    return {
        "range_instance": os.environ.get("KEPLEROPS_RANGE_INSTANCE", "unknown"),
        "participant": os.environ.get("KEPLEROPS_PARTICIPANT", "unknown"),
        "reset_generation": reset_generation(),
        "trace_id": trace_id,
    }


def _tls_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_verify_locations(cafile="/run/tls/ca.crt")
    context.load_cert_chain("/run/tls/tls.crt", "/run/tls/tls.key")
    return context


def post_content(signal: str, event: dict[str, object], trace_id: str) -> None:
    body = {
        **base_payload(trace_id),
        "signal": signal,
        "content": json.dumps(event, separators=(",", ":"), sort_keys=True),
    }
    parsed = urlparse(INGEST_URL)
    connection = http.client.HTTPSConnection(
        parsed.hostname or "telemetry-proof-01.keplerops.lab",
        parsed.port or 443,
        context=_tls_context(),
        timeout=1.5,
    )
    try:
        connection.request(
            "POST",
            f"{parsed.path.rstrip('/')}/v1/research/content",
            body=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Producer-ID": PRODUCER_ID,
                "X-Producer-Token": read_text(TOKEN_FILE),
            },
        )
        connection.getresponse().read()
    finally:
        connection.close()


def sender_loop(
    events: EventQueue,
    trace_id_for_event: Callable[[dict[str, object]], str],
) -> None:
    while True:
        item = events.get()
        if item is None:
            return
        signal, event = item
        try:
            post_content(signal, event, trace_id_for_event(event))
        except Exception:
            continue


def start_sender(
    events: EventQueue,
    name: str,
    trace_id_for_event: Callable[[dict[str, object]], str],
) -> threading.Thread:
    worker = threading.Thread(
        target=sender_loop,
        args=(events, trace_id_for_event),
        name=name,
        daemon=True,
    )
    worker.start()
    return worker


def stop_sender(events: EventQueue, worker: threading.Thread) -> None:
    try:
        events.put_nowait(None)
    except queue.Full:
        pass
    worker.join(timeout=2.0)
