# Clean Enterprise Observability Correlation

Gate 11 observes an ordinary Orion Release Risk inference. Caddy sends the
normal `risk-model.keplerops.lab` route through Envoy, and Envoy forwards the
request to the real KServe workload without changing its API.

Envoy emits an OpenTelemetry span and a structured access log. The Collector
exports the span to Jaeger, derives Prometheus metrics from that same span, and
indexes the access log in OpenSearch. Prometheus evaluates the derived metric
and routes the resulting alert to Alertmanager. OpenCost accounts for the
`orion-runtime` Kubernetes workload in the event window using real
kube-state-metrics and cAdvisor observations.

Run `telemetry/install-kubernetes.sh` after the k3s platform is ready. It applies
the committed OpenCost, kube-state-metrics, and cAdvisor resources to the
existing guest. Then run `baseline/observability-correlation.sh` from the outer
range host. The acceptance probe issues one inference and joins only the normal
Jaeger, Prometheus, Alertmanager, OpenSearch, and OpenCost APIs.

The `x-keplerops-event-id` header is an operational correlation header. It is
optional for ordinary requests and does not contain a flag, challenge ID, or
hidden answer.
