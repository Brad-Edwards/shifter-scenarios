# Participant Telemetry Rehearsal Report

## Result

The `gcp_full` participant telemetry rehearsal passed on 2026-07-20 against
the retained `kep-469-r1` KeplerOps range for participant `operator`. The run
entered only through the external Kasm browser terminal for participant
actions. Cloud and host administration were limited to health, scoped image
replacement, bounded fault injection, reset, observation, and export.

This is durable evidence for telemetry rehearsal. The final manual participant
walkthrough is recorded separately; neither result by itself earns `golden`
status.

## Proven Gates

- All 28 assets and services were ready and the ten-subnet range remained
  isolated before participant execution.
- Real model-evasion inference and receipt verification succeeded through the
  participant surface.
- The real Airflow distillation DAG completed and wrote its trained adapter to
  the Airflow-owned runtime output directory. The operational research export
  contains a participant-created `telemetry-*` DAG run with both
  `workflow.started` and `workflow.completed` from `distillation-runner-01`.
- Participant access to OTLP ports 4318/4319 was blocked and the research HTTP
  ingest surface returned its non-disclosing response.
- Collector failure remained fail-open for inference and proof, the proof
  service recovered, and one intentionally dropped observation was represented
  as missingness rather than hidden.
- The paired `on/off/off/on` performance test used four 100-request windows.
  Median p95 was 500.452 ms with telemetry and 527.854 ms without telemetry.
  The measured overhead was 0.0%, below the strict 5% limit.
- Operational export and readback passed field-policy, archive-safety,
  required-event, missingness, and environment-manifest checks.
- Supplemental GCP VPC/firewall log augmentation completed with a bounded
  lookback and timeout so stale events in a retained session cannot hang export.

## Captured Evidence

The owner-only operational archive contained 16,973 ordered events, including
16,674 session-bounded network-flow/firewall observations. Missingness was
intentionally `incomplete`: the rehearsal injected measured loss, and the
retained session includes prior fail-open attempts and stale sequence gaps
rather than hiding them.

The environment manifest carried 28 runtime image digests, nine auxiliary image
digests, and six model/adapter/dataset/scenario/instrumentation/runtime-lock
digests. The archive checksum was
`sha256:3fa480736d5b7c76ddb84675cc4eb70d18e9e660553c4a7c6ca8b2e20716b748`.
Raw operational archives, cloud identifiers, browser state, credentials,
tokens, receipts, and captured content are not committed.

## Defects Closed During Rehearsal

The live run found and fixed gateway Secret Manager grants for platform-agent
control, shared runtime-module copies in service images, health-check
realization selection, pinned Stalwart provenance/bootstrap recovery, Airflow
research-event delivery timeout/retry behavior, stale readback expectations for
current gateway events and scenario digests, and unbounded GCP logging reads
during network-flow augmentation.

## Remaining Work

- Full participant telemetry readback is proven for the current retained range.
- The VPC/firewall augmentation path is bounded and captured for the current
  proof bundle; a future data-engineering pass should batch or stream
  long-horizon GCP log exports for multi-hour event studies rather than relying
  on one large `gcloud logging read` (logging-read size failure).
- Phase-E teardown remains deferred while the rehearsal environment is useful
  for continuing validation.
