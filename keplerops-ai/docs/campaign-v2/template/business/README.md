# Orion Business Decision Adapter

The internal adapter accepts a typed natural business record, derives a causal
decision through the released Orion services, signs that decision, asks OPA to
authorize one pre-bounded effect, invokes the owning OSS product API, and writes
the complete chain to its durable SQLite audit store.

Callers provide a subject, description, and ordinary business facts. They
cannot choose an actor, action, outcome, target system, target object, release
identity, confidence, or reason code. The adapter derives those fields as
follows:

1. Workflows that need document context call Orion Assistant and retain its
   grounded response, citations, conversation identity, and output digest.
2. The natural record plus any assistant assessment is classified by the active
   signed Orion Release Risk endpoint.
3. The adapter requires the expected semantic class for the bounded workflow
   and uses the winning probability as the decision confidence.
4. The source, every inference stage, active release identities, and typed
   decision are covered by the decision signature.
5. OPA checks the actor, class, action, outcome, immutable release identity, and
   fixed target before the native side effect runs.

The adapter is internal enterprise infrastructure. It is not a participant API,
challenge surface, flag service, proof broker, or model substitute.

## Business Workflows

| Workflow | Orion evidence | Native effect |
| --- | --- | --- |
| `feature-control` | Assistant context + `ReleaseApprove` | Unleash enables the named production canary feature |
| `accounting-credit` | `EntitlementReview` | Odoo posts a balanced EUR 125 credit note and generates its PDF |
| `incident-publication` | Assistant context + `SecurityAdvisory` | Ghost publishes the approved status draft |
| `advisory-campaign` | `SecurityAdvisory` | Mautic sends the approved Orion Edge advisory through Stalwart |
| `support-triage` | `EntitlementReview` | Zammad closes the verified routine access request and notifies its owner |
| `feedback-intake` | `PartnerIntake` | Zammad, RabbitMQ, and Qdrant retain the partner contribution |
| `feedback-maintenance` | `ResearchReview` | lakeFS commits the partition validation report |
| `tenant-retention` | Assistant context + `PrivacySafety` | The approved Redmine request removes the named Nextcloud and lakeFS objects |

Every workflow has a normal compensation path. Financial compensation posts a
new reversing entry, publication retains revision history, support retains case
history, and lakeFS restoration creates a new commit. The adapter never deletes
its audit records.

## Reconcile And Prove

The ordinary enterprise seeders must run first. Bind the adapter to the exact
signed model and policy identities, reconcile the workflow-owned records, and
run the independent acceptance script:

```bash
./scripts/activate-business-model-identities.sh
./seeding/seed.sh business-workflows
./baseline/business-workflows.sh
```

The acceptance submits plausible business inputs for all eight workflows. It
checks the causal model output and probability vector, OPA decision, native
effect, durable audit readback, idempotent replay, and compensation state. It
also proves that a caller cannot inject an action or target.

## Runtime Configuration

The activation script verifies immutable cosign bundles on k3s01, derives the
active release, model, serving-image, and business-policy digests, and writes
`state/business-release.env`. In addition to those existing values, the adapter
uses:

- `ORION_RELEASE_RISK_URL` (default `http://192.168.78.30:30083`)
- `ORION_RELEASE_RISK_MODEL` (default `orion-release-risk`)
- `ORION_AGENT_URL` (default `http://192.168.78.30:30081`)
- `ORION_AGENT_API_KEY`
- `ORION_DECISION_SIGNING_KEY_ID` (default `orion-business-decision-v1`)

The defaults match the current enterprise topology; a backend can override the
URLs without changing the workflow contract.
