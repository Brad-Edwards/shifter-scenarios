# KeplerOps contained impact platform

This image supplies challenge-neutral software boundaries for contained outcome,
resource, and availability workflows. It deliberately owns no flags, receipts,
scores, proof predicates, or ATLAS mappings.

The service provides:

- a SQLite-durable synthetic ledger whose complete journal is validated by
  Beancount on every transaction;
- persistent range-only publications and reversible reputation changes;
- a separately persisted scikit-learn allocation model with Fairlearn group
  metrics over stored decisions;
- a separately persisted text safety classifier and synthetic user actions;
- token, compute, and synthetic-budget accounting;
- allowlisted range-local availability probes and bounded HTTP recovery calls;
- deterministic operator reset and seed; and
- a bounded Grafana k6 constant-arrival-rate client cohort.

Runtime state belongs on a persistent mount at
`/var/lib/keplerops-platform-impact`. The integration must set
`PLATFORM_IMPACT_ADMIN_TOKEN` to the committed synthetic scenario credential,
route only range-local services to port 8460, and register every producer in the
SDL telemetry contract. The k6 runner is a separate real Grafana k6 workload;
its eventual SDL feature must pin the selected upstream image digest.
