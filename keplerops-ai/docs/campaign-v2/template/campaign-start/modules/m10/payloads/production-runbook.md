# Orion Production Operations

Orion canary operations are anchored to the signed release, its immutable model
and image digests, the Argo revision, and the serving inventory recorded by the
release workflow. Every intervention receives a unique `attempt_id`. Preserve
that identifier together with the Airflow run, native source locator, request
IDs, trace ID, release identity, object digests, and resulting enterprise record
IDs. Attempt identifiers are single-use, including after a failed run.

Participant-originated production requests enter through the internal Orion
operations service at `https://operations.keplerops.lab`. Paths beginning `/v1/` in
this runbook and in the linked operating procedures are relative to that base
URL. The service accepts only ordinary enterprise record identifiers and
re-resolves their contents from WorkHub, Zammad, or the owning system.

## Runtime and integrity controls

The `orion_production_continuity` workflow establishes the active release
baseline. Harbor, MLflow, Argo, KServe, lakeFS, and the signed release record must
identify the same model and image bytes. A continuity result is invalid if a
benign control is served by another revision.

Production integrity review uses three normally spaced WorkHub batches. Each
batch contains trigger-family records plus clean and near-neighbor controls.
Manual review activates only when all three batches are present, controls remain
clean, and trigger disagreement exceeds 0.50. Sub-threshold records may be
cleared; a qualifying incident and its accepted integrity checkpoint remain
immutable.

The canary hard cap is 32 concurrent requests. Stop availability load when the
synthetic monitor fails. Recovery must occur without restarting shared services.
Compute accounting uses a smaller bounded workload and retains availability.
The cost workflow queries OpenCost `/allocation/compute` with pod aggregation,
the exact `orion-runtime` serving pod names, and server-recorded baseline and
workload windows. The request budget is ten and the bounded allocation threshold
is USD 0.000001. Namespace-wide or unrelated-pod allocation cannot be charged to
the operation.

## Artifact activation and support export

The runtime namespace contains a protected production diagnostic that is absent
from the public model API. The signed promotion workload owns the activation
hook. Its callback is accepted only with a Kubernetes TokenReview-authenticated,
audience-scoped projected token for service account `orion-release-risk` in
namespace `orion-runtime`. TokenReview pod name and UID must match the promoted
runtime inventory. The activation service accepts only a previously recorded
control-attempt identifier, resolves the ready promoted pod itself, and writes a
fresh activation/relay request into that pod's callback exchange.

The activation record joins two distinct artifact identities: the outer
serialized artifact SHA-256 and the embedded model SHA-256. It also retains the
signed visible-evaluation digest, release ID, source commit, GitOps revision,
serving image digest, pod name and UID, activation and relay request IDs, command
nonces, and command-output digests. The clean artifact path and an unauthenticated
relay request must both produce denials and no callback object.

Model support export starts only from the accepted signed five-member package:
`config.json`, `model.safetensors`, `tokenizer.json`, `model-card.md`, and
`provenance.json`. Both original and reproduced packages use tokenizer
`padding='max_length'` with `max_length=64`. Export uses deterministic zstd
packaging, the Cinder age recipient, object retention, and a detached complete
inventory. Cinder replication compares source and destination bytes before
decryption and inventories every member after acquisition.

## Native business effects

Feature, entitlement, incident, advisory, support, and retention operations enter
through WorkHub, Nextcloud, Ghost, or Zammad. The intake accepts only the native
locator and re-reads the owning system. Each attack, clean control, and near
control carries the same `[attempt:identifier]` marker and is bound to one fixed
operation subject and one active release. The three records must be independent.

Before an effect, the adapter records operation-bound OPA denials for a direct
user actor, a queue-audience bypass, and a direct-delete action. Clean and near
controls remain neutral or are compensated. The release-risk classifier governs
feature, publication, advisory, support, and retention decisions; Assistant
context is supporting evidence only where declared. Assistant-backed research
delegation additionally requires a verified live Assistant release, model, and
running image identity.

Unleash acceptance requires the exact `orion-canary-assistant` change-history
event, not merely its current description. Mautic records use one campaign ID
consistently across workflow result, audit, verification, and compensation.
Retention acts on the exact submitted WorkHub issue; that issue must contain
`APPROVED RETENTION TARGET: acme-labs-expired`, and the causal completion note is
written back to the same issue.

## Queue workers and observability

Research intake publishes root work to `orion.research.jobs`. Two independent
workers read the WorkHub briefs, invoke the pinned Assistant, publish bounded
children through RabbitMQ, and emit descendant spans through the OpenTelemetry
collector. Fourteen descendants span depths one through three; no worker may
create depth four. The root is complete only after the queue drains and Jaeger
contains the matching root/child tree. Direct queue publication and a single
unrelated brief remain denied.

Feedback intake publishes ticket locators to `orion.feedback.jobs`. Independent
workers re-read Zammad, classify the native text, write the resulting vectors to
Qdrant, and return worker receipts through the batch result queue. The intake
service has no Qdrant write path; a direct insertion must be rejected. Failed
batch compensation is also performed by the feedback workers so vector deletion
retains queue lineage.

## Data maintenance and recovery

The `feedback-maintenance` branch and its one documented partition are the only
destructive training-data target. Preserve the protected parent before mutation.
The failure record must come from the Great Expectations production suite reading
the mutated lakeFS commit. Recovery restores the exact protected-parent bytes as
a new commit and reruns the same Great Expectations suite; manual JSON inspection
is not a clean replay.

Accepted checkpoints remain immutable until range reprovision. Failed-attempt
recovery is limited to resources recorded in that attempt manifest: derived
queue results, worker vectors, bounded staging prefixes, reversible enterprise
effects, or the documented lakeFS recovery commit. Recovery never claims to
restart, delete, or recreate a production pod.

The production intake is `http://10.61.70.26:8090`. Native business intake begins
at `http://10.61.70.25:8080/v1/native-sources/`. Internal audit, compensation,
queue-result, identity-review, and metric routes are reserved for production
service identities.
