from __future__ import annotations

from domain import derive_research_context
from domain import ResearchObservation
from domain import SessionClaims
from fastapi import APIRouter
from instrumentation import configure_tracing
from instrumentation import current_trace_identifiers
from keplerops_runtime.foundation.auth_storage import _current_generation, _telemetry_enabled
from keplerops_runtime.foundation.config import CONFIG, RESEARCH_RUNTIME_CONFIG, TLS_CA_PATH, _regular_owner_file
from keplerops_runtime.foundation.contracts import _research_contract, _research_store
from pathlib import Path
from research import ResearchEmitter
from typing import Any
import httpx
import itertools
import ssl
import time

router = APIRouter()


TRACER = configure_tracing(CONFIG)

RESEARCH_EMITTER = ResearchEmitter(capacity=RESEARCH_RUNTIME_CONFIG.queue_capacity)

RESEARCH_SEQUENCE = itertools.count(1)

RESEARCH_HTTP_CLIENT: httpx.Client | None = None

CHALLENGE_MODULES = {
    "agent-control": "module-01-agent-control",
    "model-evasion": "module-02-model-evasion",
    "context-poisoning": "module-03-context-poisoning",
    "model-secrets": "module-04-model-secrets",
    "agent-persistence": "module-05-agent-persistence",
    "adversarial-input": "module-06-adversarial-input",
    "training-poisoning": "module-07-training-poisoning",
    "model-extraction": "module-08-model-extraction",
    "model-backdoor": "module-09-model-backdoor",
    "ai-capstone": "module-10-ai-capstone",
}

def _research_sender(payload: dict[str, Any]) -> None:
    global RESEARCH_HTTP_CLIENT
    payload = dict(payload)
    research_ingest_url = CONFIG.get("research_ingest_url")
    producer = CONFIG.get("producer_id")
    producer_token_file = CONFIG.get("producer_token_file")
    if (
        not isinstance(research_ingest_url, str)
        or not isinstance(producer, str)
        or not isinstance(producer_token_file, str)
    ):
        raise RuntimeError("research sender unavailable")
    if RESEARCH_HTTP_CLIENT is None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_verify_locations(cafile=TLS_CA_PATH)
        context.load_cert_chain("/run/tls/tls.crt", "/run/tls/tls.key")
        RESEARCH_HTTP_CLIENT = httpx.Client(timeout=2.0, verify=context)
    token = _regular_owner_file(Path(producer_token_file)).decode("utf-8")
    kind = payload.pop("_kind", "event")
    endpoint = "content" if kind == "content" else "events"
    response = RESEARCH_HTTP_CLIENT.post(
        f"{research_ingest_url.rstrip('/')}/v1/research/{endpoint}",
        headers={"X-Producer-ID": producer, "X-Producer-Token": token},
        json=payload,
    )
    if response.status_code != 202:
        raise RuntimeError("research sender rejected")

def _observe(
    session: SessionClaims,
    *,
    event_name: str,
    outcome_id: str,
    status: str,
    challenge_id: str | None = None,
    **measures: Any,
) -> None:
    if not _telemetry_enabled():
        return
    try:
        contract = _research_contract()
        trace_id, span_id = current_trace_identifiers()
        values = {
            "event_name": event_name,
            "occurred_at": time.time_ns(),
            "module_id": CHALLENGE_MODULES[outcome_id],
            "source_sequence": next(RESEARCH_SEQUENCE),
            "status": status,
            "trace_id": trace_id,
            "span_id": span_id,
            "dropped_event_count": RESEARCH_EMITTER.snapshot()["dropped"],
            **measures,
        }
        if challenge_id is not None:
            values["challenge_id"] = challenge_id
        observation = ResearchObservation.from_mapping(
            values,
            contract=contract,
            source_id=str(CONFIG.get("producer_id")),
        )
        payload = {
            "event": observation.values,
            "range_instance": session.range_instance,
            "participant": session.participant,
            "reset_generation": _current_generation(),
        }
        if CONFIG["role"] == "proof":
            _research_store().record_observation(
                observation,
                source_id=str(CONFIG.get("producer_id")),
                range_instance=session.range_instance,
                participant=session.participant,
                reset_generation=payload["reset_generation"],
                observed_at=time.time_ns(),
            )
        else:
            RESEARCH_EMITTER.emit(payload)
    except Exception:
        return

def _record_local_content(
    session: SessionClaims,
    *,
    signal: str,
    content: str,
    trace_id: str,
) -> None:
    context = derive_research_context(
        key=_regular_owner_file(Path(str(CONFIG["research_pseudonym_key_file"]))),
        range_instance=session.range_instance,
        participant=session.participant,
        reset_generation=_current_generation(),
    )
    _research_store().record_content(
        session_id=context.session_id,
        trace_id=trace_id,
        signal=signal,
        content=content.encode("utf-8"),
        observed_at=time.time_ns(),
    )

def _capture(session: SessionClaims, *, signal: str, content: str) -> None:
    if not _telemetry_enabled():
        return
    try:
        capture = RESEARCH_RUNTIME_CONFIG.capture_signals
        if capture.get(signal) is not True:
            return
        trace_id, _ = current_trace_identifiers()
        if CONFIG["role"] == "proof":
            _record_local_content(
                session,
                signal=signal,
                content=content,
                trace_id=trace_id,
            )
            return
        RESEARCH_EMITTER.emit({
            "_kind": "content",
            "signal": signal,
            "content": content,
            "trace_id": trace_id,
            "range_instance": session.range_instance,
            "participant": session.participant,
            "reset_generation": _current_generation(),
        })
    except Exception:
        return

def _capture_http_body(session: SessionClaims, request: Any) -> None:
    try:
        content = request.model_dump_json()
    except Exception:
        return
    _capture(session, signal="http_body", content=content)

@router.on_event("startup")
def start_research_emitter() -> None:
    producer_token_file = CONFIG.get("producer_token_file")
    if CONFIG["role"] != "proof" and isinstance(producer_token_file, str) and Path(producer_token_file).is_file():
        RESEARCH_EMITTER.start_once(_research_sender)

@router.on_event("shutdown")
def stop_research_emitter() -> None:
    global RESEARCH_HTTP_CLIENT
    RESEARCH_EMITTER.close()
    if RESEARCH_HTTP_CLIENT is not None:
        RESEARCH_HTTP_CLIENT.close()
        RESEARCH_HTTP_CLIENT = None
