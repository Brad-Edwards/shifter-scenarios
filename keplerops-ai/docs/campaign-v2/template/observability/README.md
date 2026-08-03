# Orion Review Causal Observability

`review-workflow-correlation.py` drives a complete, ordinary artifact review
and verifies correlation records emitted by the services that perform the
work. The driver never writes audit records or OTLP spans.

The stable review request ID is carried as:

- the Orion conversation ID and `X-Request-ID` at Caddy ingress;
- the OPA conversation context for the assistant authorization decision;
- the RabbitMQ message ID, correlation ID, header, and submission ID;
- the review worker result submission ID;
- the WorkHub issue subject; and
- the exact-match key in the OpenSearch audit index and span-derived Prometheus
  series.

The W3C trace identity is sent at HTTP ingress, propagated by Orion to Qdrant,
LiteLLM, OPA, and MCP, and carried in the RabbitMQ `traceparent` header. Orion
and the review worker emit their own OTLP spans and audit records. Every record
binds the stable request ID, trace ID, and signed assistant runtime release.

The baseline executes a second integration review on the adjacent worker queue.
It requires a distinct request and trace identity, then independently proves
that neither Jaeger nor OpenSearch joined the two workflows.

## Integration Requirements

1. Reconcile the guest review workers and their scoped RabbitMQ and WorkHub
   identities with `scripts/reconcile-guests.sh`.
2. Capture and activate a signed assistant runtime release on k3s01.
3. Run Caddy, Orion Agent, OPA, RabbitMQ, both review workers, WorkHub,
   OpenTelemetry Collector, Jaeger, OpenSearch, and Prometheus.
4. Configure Orion and both review workers to send OTLP/HTTP to the Collector
   and their structured audit records to the existing access-log ingestion
   path. The services, not the acceptance driver, own these records.
5. Run `baseline/observability-correlation.sh` as root from the outer host. The
   two review queues must be idle. Each request names its own expiring result
   queue so the acceptance run cannot consume another workflow's result.
6. Reconcile Grafana to load the provisioned Orion Review Correlation dashboard.

The wire formats follow the
[OTLP JSON encoding](https://opentelemetry.io/docs/specs/otlp/), the
[Jaeger trace API](https://www.jaegertracing.io/docs/1.70/apis/), and
[OpenSearch exact term queries](https://docs.opensearch.org/3.1/query-dsl/term/term/).
