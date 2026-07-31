"""Manual OpenTelemetry setup with bounded, fail-open OTLP/HTTP export."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


UNTRUSTED_TRACE_HEADERS = frozenset({
    "traceparent",
    "tracestate",
    "baggage",
    "x-keplerops-study-run-id",
    "x-keplerops-session-id",
})
TRACER_NAME = "keplerops.runtime"


def strip_untrusted_trace_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        key: value for key, value in headers.items()
        if key.lower() not in UNTRUSTED_TRACE_HEADERS
    }


def configure_tracing(config: Mapping[str, Any]):
    endpoint = config.get("otel_endpoint")
    asset_id = config.get("asset_id")
    if not isinstance(endpoint, str) or not isinstance(asset_id, str):
        return trace.get_tracer(TRACER_NAME, "1")
    try:
        exporter = OTLPSpanExporter(
            endpoint=f"{endpoint.rstrip('/')}/v1/traces",
            certificate_file="/run/tls/ca.crt",
            client_certificate_file="/run/tls/tls.crt",
            client_key_file="/run/tls/tls.key",
            timeout=2.0,
        )
        provider = TracerProvider(resource=Resource.create({
            "service.name": asset_id,
            "service.namespace": "keplerops",
            "telemetry.schema.version": 1,
        }))
        provider.add_span_processor(BatchSpanProcessor(
            exporter,
            max_queue_size=512,
            max_export_batch_size=128,
            schedule_delay_millis=500,
            export_timeout_millis=2_000,
        ))
        trace.set_tracer_provider(provider)
        return provider.get_tracer(TRACER_NAME, "1")
    except Exception:
        return trace.get_tracer(TRACER_NAME, "1")


@contextmanager
def trusted_root_span(tracer, name: str, attributes: Mapping[str, Any]) -> Iterator[Any]:
    with tracer.start_as_current_span(
        name,
        context=Context(),
        attributes=dict(attributes),
    ) as span:
        yield span


def trace_identifiers(span) -> tuple[str, str]:
    context = span.get_span_context()
    if not context.is_valid:
        return "0" * 32, "0" * 16
    return f"{context.trace_id:032x}", f"{context.span_id:016x}"


def current_trace_identifiers() -> tuple[str, str]:
    return trace_identifiers(trace.get_current_span())
