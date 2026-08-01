# Bounded Orion Business Workflows

This directory implements clean-enterprise acceptance gate 10. The internal
adapter consumes a signed, typed Orion decision, validates its active release
identity, asks OPA for one fixed action, invokes the owning OSS product API, and
records idempotency, causal identifiers, before/after hashes, notification IDs,
and compensation state in a durable SQLite audit store.

It is not a participant API, challenge surface, flag service, proof broker, or
model substitute. Compose attaches it only to internal range networks. The
model/runtime boundary must emit the signed decision envelope; callers cannot
supply target IDs or free-form actions.

## Clean Workflows

| Workflow | Orion family | Native effect |
| --- | --- | --- |
| `feature-control` | Assistant | Unleash enables one named canary feature |
| `accounting-credit` | Release Risk | Odoo posts a balanced synthetic credit note and generates its PDF |
| `incident-publication` | Assistant | Ghost publishes one approved status draft |
| `advisory-campaign` | Release Risk | Mautic resolves the Orion Edge segment and sends through Stalwart |
| `support-triage` | Release Risk | Zammad closes one routine case and Stalwart notifies its synthetic user |
| `feedback-intake` | Release Risk | Zammad, RabbitMQ, and Qdrant retain one useful feedback record |
| `feedback-maintenance` | Release Risk | lakeFS commits a schema-validation report for one bounded partition |
| `tenant-retention` | Assistant | An approved Redmine request removes named Nextcloud and lakeFS objects |

Every workflow has a normal compensation path. Financial compensation posts a
new reversing entry, publication retains revision history, support retains case
history, and lakeFS restoration creates a new commit. The adapter never deletes
its audit records.

## Reconcile And Prove

The ordinary enterprise seeders must run first. After the engineering/data
services and both signed model-family releases are available, bind the adapter
to those exact runtime identities, reconcile the workflow-owned native records,
and run the independent acceptance script:

```bash
./scripts/activate-business-model-identities.sh
./seeding/seed.sh business-workflows
./baseline/business-workflows.sh
```

The baseline script submits each clean decision twice to prove idempotency,
reads the resulting state directly from the product APIs, compensates it, and
reads the restored native state again. It also proves that a signed decision for
another range is rejected before any product call.

## Runtime Contract

The activation script verifies the immutable cosign bundles on k3s01, derives
the active release, model, serving-image, and business-policy digests, and
atomically writes `state/business-release.env`. The adapter consumes that file;
the independent baseline refuses to run without it. A materialized range keeps
the same envelope and policy schema while supplying its own signed identities.
