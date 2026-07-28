"""Fail-open encrypted research-content submission helpers for Airflow DAGs."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import ssl
import time
import urllib.request
from pathlib import Path
from typing import Any


TLS_CA = "/run/tls/ca.crt"
PRODUCER_ID = "distillation-runner-01"
PRODUCER_TOKEN_PATH = "/run/keplerops/producer-token"
RESET_GENERATION_PATH = Path("/run/keplerops/reset-generation")
MAX_CONTENT_BYTES = 900_000


def _secret(path: str) -> str:
    value = Path(path).read_text(encoding="utf-8").strip()
    if not value or len(value) > 4096:
        raise RuntimeError("workflow research secret unavailable")
    return value


def _reset_generation() -> int:
    return int(RESET_GENERATION_PATH.read_text(encoding="ascii"))


def _tls_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_verify_locations(cafile=TLS_CA)
    context.load_cert_chain("/run/tls/tls.crt", "/run/tls/tls.key")
    return context


def _post(signal: str, trace_id: str, content: dict[str, Any]) -> None:
    request = urllib.request.Request(
        os.environ["KEPLEROPS_RESEARCH_INGEST_URL"] + "/v1/research/content",
        data=json.dumps(
            {
                "signal": signal,
                "trace_id": trace_id,
                "range_instance": os.environ["KEPLEROPS_RANGE_INSTANCE"],
                "participant": os.environ["KEPLEROPS_PARTICIPANT"],
                "reset_generation": _reset_generation(),
                "content": json.dumps(content, separators=(",", ":"), sort_keys=True),
            },
            separators=(",", ":"),
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Producer-ID": PRODUCER_ID,
            "X-Producer-Token": _secret(PRODUCER_TOKEN_PATH),
        },
        method="POST",
    )
    with urllib.request.urlopen(request, context=_tls_context(), timeout=2.0) as response:
        response.read()


def capture_json(signal: str, trace_id: str, content: dict[str, Any]) -> None:
    try:
        _post(signal, trace_id, {"timestamp_ns": time.time_ns(), **content})
    except Exception:
        return


def capture_artifact(
    trace_id: str,
    *,
    artifact_id: str,
    content: bytes,
    media_type: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    digest = hashlib.sha256(content).hexdigest()
    encoded = base64.b64encode(content).decode("ascii")
    event: dict[str, Any] = {
        "event": "artifact.created",
        "artifact_id": artifact_id,
        "media_type": media_type,
        "byte_count": len(content),
        "sha256": digest,
        "encoding": "base64",
        "truncated": False,
        "data": encoded,
        **(metadata or {}),
    }
    if len(json.dumps(event, separators=(",", ":"), sort_keys=True)) > MAX_CONTENT_BYTES:
        event.pop("data", None)
        event["truncated"] = True
    capture_json("artifact_content", trace_id, event)
