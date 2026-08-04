# Module 07 Facilitator Guide

<!-- BEGIN GENERATED CHALLENGE HANDOFF -->

## Challenge Facilitation Briefs

Generated from the SDL challenge contracts for Module 07 - Training Poisoning. Use this
as the per-challenge facilitation checklist; keep the hand-authored module notes below
for deeper diagnosis and recovery guidance.

### `kep-m07-a` - Poisoned Row

- **What it is:** Add participant-authored poisoned examples to a new version of the immutable-base
  training dataset while preserving server-verifiable lineage.
- **ATLAS techniques:** `AML.T0020`
- **Participants should learn:** how to turn the accessible objective into native service evidence, how the objective
  stage proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** browser, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, model-registry-01 / registry-api, notebook, python
- **Expected solve:** Complete prerequisites `kep-m03-a`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m03-a; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m07-b` - Targeted Influence

- **What it is:** Train a real text adapter from a participant-poisoned dataset revision and make its
  hidden target probability move far enough beyond the immutable clean baseline.
- **ATLAS techniques:** `AML.T0018.000`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the
  objective stage proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, model-registry-01 / registry-api, notebook, python
- **Expected solve:** Complete prerequisites `kep-m07-a`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m07-a; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m07-c` - Clean Enough

- **What it is:** Preserve the poisoned adapter target delta while the disclosed clean evaluation
  remains accurate and close to the immutable baseline.
- **ATLAS techniques:** `AML.T0018.000`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the
  objective stage proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, model-registry-01 / registry-api, notebook, python
- **Expected solve:** Complete prerequisites `kep-m07-b`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m07-b; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m07-d` - Low and Slow

- **What it is:** Produce the same real target behavior change with at most three poisoned rows and no
  more than twelve percent of the complete training revision.
- **ATLAS techniques:** `AML.T0018.000`, `AML.T0020`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the
  objective stage proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, model-registry-01 / registry-api, notebook, python
- **Expected solve:** Complete prerequisites `kep-m07-c`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m07-c; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m07-e` - Backdoor Dataset

- **What it is:** Train a trigger-specific backdoor that succeeds across the hidden target set while
  retaining the clean evaluation behavior.
- **ATLAS techniques:** `AML.T0043.004`
- **Participants should learn:** how to turn the advanced objective into native service evidence, how the objective
  stage proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** browser, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, model-registry-01 / registry-api, notebook, python
- **Expected solve:** Complete prerequisites `kep-m07-c`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m07-c; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m07-f` - Stealth Poison

- **What it is:** Poison participant-controlled training data and demonstrate the intended behavioral
  delta without breaking clean probes.
- **ATLAS techniques:** `AML.T0018.000`, `AML.T0020`, `AML.T0043.004`
- **Participants should learn:** how to turn the expert objective into native service evidence, how the impact proof
  boundary differs from a local note or copied answer, and how immutable records,
  controls, and reset generation affect scoring
- **Systems involved:** browser, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, model-registry-01 / registry-api, notebook, python
- **Expected solve:** Complete prerequisites `kep-m07-d`, `kep-m07-e`; create the native
  participant-visible evidence described by the module procedure, then request the
  module receipt. The facilitator should look for a native carrier owned by the
  relevant service, not chat prose, shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m07-d, kep-m07-e; using operator-only state
  instead of participant-visible records; requesting the receipt before the qualifying
  evidence exists; copying local notes instead of the owning system locator

### `kep-m07-g` - Architecture Sabotage

- **What it is:** Modify the model architecture in the real training workflow and preserve clean
  behavior while introducing a measured attacker-selected weakness.
- **ATLAS techniques:** `AML.T0018`, `AML.T0018.001`
- **Participants should learn:** how to turn the advanced objective into native service evidence, how the training
  expansion proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, distillation-runner-01 / distillation-jobs, inference-gateway /
  inference-api, model-registry-01 / registry-api, platform-agent-01 /
  platform-isolation-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m07-b`; submit the required component evidence through
  the participant-facing /v1/training/expansion workflow, then request the training
  receipt. The facilitator should look for a native carrier owned by the relevant
  service, not chat prose, shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m07-b; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m07-h` - Poisoned Dataset Publication

- **What it is:** Publish a poisoned dataset version through the real registry and cause an
  independent training consumer to select it.
- **ATLAS techniques:** `AML.T0019`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the
  training expansion proof boundary differs from a local note or copied answer, and
  how immutable records, controls, and reset generation affect scoring
- **Systems involved:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, distillation-runner-01 / distillation-jobs, inference-gateway /
  inference-api, model-registry-01 / registry-api, platform-agent-01 /
  platform-isolation-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m07-a`; submit the required component evidence through
  the participant-facing /v1/training/expansion workflow, then request the training
  receipt. The facilitator should look for a native carrier owned by the relevant
  service, not chat prose, shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m07-a; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m07-i` - Executable Model Artifact

- **What it is:** Embed contained executable code in an otherwise functioning model artifact and
  trigger it through the normal model-loading workflow.
- **ATLAS techniques:** `AML.T0018.002`
- **Participants should learn:** how to turn the expert objective into native service evidence, how the training
  expansion proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, distillation-runner-01 / distillation-jobs, inference-gateway /
  inference-api, model-registry-01 / registry-api, platform-agent-01 /
  platform-isolation-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m07-b`; submit the required component evidence through
  the participant-facing /v1/training/expansion workflow, then request the training
  receipt. The facilitator should look for a native carrier owned by the relevant
  service, not chat prose, shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m07-b; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

<!-- END GENERATED CHALLENGE HANDOFF -->


Use read-only product records for coaching and diagnosis. Do not create records
for teams, provide hidden reference values, reveal protected case contents, or
repair an operation from host/container state. Give one hint tier at a time.
Successful outputs and signed handoffs are durable campaign assets; recovery
removes only failed mutable attempt state.

## kep-m07-a - Change The Labels

**Learning objective:** Show how normal annotation authority can become a
training-data poisoning path.

**Realism:** Label Studio owns review edits; Airflow exports them through DVC
and lakeFS, preserving project scope and row-level lineage.

**Hints:** Orientation: ask the team which Label Studio project their earned
identity can see. Mechanism: focus them on changing 8 to 12 labels while
preserving record IDs, text, schema, and one target label. Execution: direct them to the
Airflow label export and lakeFS lineage object.

**Diagnostics:** Check Label Studio project access, before/after exports, DVC
MD5, lakeFS commit/path, changed-row count, unchanged texts, and denied access
to adjacent projects. Confirm `~/.keplerops/m07-earned.env` exists for the
participant and includes Label Studio, Airflow, lakeFS, and MLflow access
before diagnosing application authorization or evidence retrieval. It must not
include upstream maintainer, Cinder publisher, Harbor publisher, or
model-integrity Forgejo material.

If Airflow reports permission denied for `/opt/airflow/orion-integrity-state`,
reconcile that module state to Airflow UID 50000, preserve the participant-owned
`attempts/kep-m07-i` subtree at UID 1000, and have the team rerun the native DAG.

**Recovery:** Restore labels only for failed attempts and remove the failed
lakeFS branch. Preserve accepted label lineage and audit records.

## kep-m07-b - Train The Poisoned Adapter

**Learning objective:** Connect poisoned data to changed model weights through a
real training pipeline.

**Realism:** Airflow runs the same PyTorch/Transformers/PEFT/ONNX workflow used
for Orion Release Risk, and MLflow stores model package lineage.

**Hints:** Orientation: have the team reopen the accepted label lineage.
Mechanism: ask whether the training run consumed that export SHA-256 and DVC
object. Execution: use the integrity-training review to compare clean and
candidate packages on fresh held-out cases.

**Diagnostics:** Compare accepted lakeFS commit, training lakeFS commit, export
SHA-256, DVC MD5, MLflow model artifacts, source commit/tree, clean baseline,
behavior metrics, poisoned-weights handoff route, and the M07-B-earned
`model_integrity_source` access recorded in the report/handoff.

An accepted label revision with fewer than eight changed labels cannot satisfy
the current training-review contract. If a report created before the scoped
carrier existed has no `earned_access.model_integrity_source`, do not provide a
setup credential or rewrite the accepted record. Record the downstream access
gate and replay from an 8-to-12-row M07-A revision in a clean lane.

**Recovery:** Delete failed integrity-review runs only. Do not remove normal
training audit history or accepted poisoned-weights handoffs.

## kep-m07-c - Measure The Poison Quietly

**Learning objective:** Teach attack verification as model behavior comparison,
not a claim about changed bytes.

**Realism:** The review reloads exact ONNX packages and uses protected target,
near-neighbor, and utility cases.

**Hints:** Orientation: ask for the accepted poisoned MLflow training run.
Mechanism: distinguish target-change, near-control accuracy, and utility.
Execution: submit the exact run to the integrity review without an objective
ref.

**Diagnostics:** Inspect the MLflow report, clean/candidate SHA-256 values, case
ID counts, metric thresholds, source/export continuity, and
verified-poisoned-weights handoff.

**Recovery:** Remove failed review runs. Preserve accepted poisoned model and
signed review handoff.

## kep-m07-d - Poison The Trusted Upstream

**Learning objective:** Show that trusted data-source reputation can move
poisoned examples across an enterprise mirror boundary.

**Realism:** Forgejo release authorship, checksums, data cards, archive bytes,
Airflow sync, and lakeFS mirror commits are all native records.

**Hints:** Orientation: send the team to the upstream corpus repository and
publisher history. Mechanism: require the release archive, checksum, and card to
describe the same poisoned dataset. Execution: trigger the upstream sync by
release tag and compare upstream bytes with lakeFS.

**Diagnostics:** Check that the upstream identity came from the accepted
`kep-m03-b` carrier, then inspect release author, source commit, tag, archive
digest, schema, changed rows, checksum, card text, mirror branch/commit/path,
and clean dataset digest.

**Recovery:** Remove failed mirror branches only. Keep Forgejo release history
and accepted mirror manifests intact.

## kep-m07-e - Wake The Backdoor

**Learning objective:** Demonstrate targeted learned behavior from trigger
poisoning with near-trigger and clean-fidelity controls.

**Realism:** The operator chooses a trigger plan in Forgejo, changes real Label
Studio rows, trains normally, and the evaluator generates fresh held-out trigger
and near cases.

**Hints:** Orientation: point to the model-integrity credential in the accepted
`kep-m07-b` report/handoff, then to the README and plan example. Mechanism: ask
whether near tokens are one or two edits away and absent from poison rows.
Execution: keep the poison bounded to 8 to 12 actual relabels, all to one
target, while preserving accepted predecessor labels.
Execution: run label export, training, then integrity review with the immutable
objective commit.

**Diagnostics:** Inspect trigger-bearing changed rows, objective commit/digest,
training run, clean/candidate packages, fresh trigger rate, clean-model trigger
rate, near accuracy, clean fidelity, utility, and participant-backdoor handoff.

**Recovery:** Restore failed labels to the accepted label-poison state and
remove failed review runs. Preserve accepted backdoor reports and handoffs.

## kep-m07-f - Poison The Holdout

**Learning objective:** Show how corrupting evaluation data can change a release
decision without changing the model.

**Realism:** The holdout lives in Forgejo, lakeFS records evaluated bytes, and
MLflow reports the fixed model's metrics against changed and protected labels.

**Hints:** Orientation: have the team recover model-integrity access from the
accepted `kep-m07-b` report/handoff, then compare `holdout.json` and
`holdout.clean.json`. Mechanism: emphasize label-only changes and immutable
parent continuity. Execution: run holdout evaluation with an exact finished
Release Risk MLflow run.

**Diagnostics:** Check source commit, parent snapshot digest, changed holdout
digest, changed-row count, unchanged texts, selected model run/family, reported
accuracy, clean-label accuracy, decision delta, and holdout-integrity handoff.

**Recovery:** Remove failed lakeFS branches and failed review runs. Preserve
Forgejo branch history and accepted holdout-integrity handoffs.

## kep-m07-g - Splice The Computation Graph

**Learning objective:** Distinguish real architecture/graph manipulation from
data poisoning or metadata-only model claims.

**Realism:** The exporter receives the actual parent ONNX and must produce a
derived ONNX with the same runtime contract plus a behavior plan.

**Hints:** Orientation: have the team recover model-integrity access from the
accepted `kep-m07-b` report/handoff, then point to the graph exporter and
accepted parent model. Mechanism: require identical inputs/outputs and
structural continuity before behavior testing. Execution: run graph review and inspect both graph
fingerprints and fresh trigger/near/clean controls.

**Diagnostics:** Check source commit, exporter outputs, ONNX checker result,
parent/candidate interfaces, initializer/node continuity, model SHA-256 values,
trigger plan, fresh behavior metrics, model artifact package, and
modified-computation-graph handoff.

**Recovery:** Remove failed MLflow review runs only. Keep Forgejo audit history
and accepted graph handoffs.

## kep-m07-h - Publish The Poisoned Dataset

**Learning objective:** Teach external poisoned-dataset publication as a
credible artifact-release problem with schema, checksum, loader, and registry
integrity.

**Realism:** The dataset is published as an immutable Harbor OCI artifact, then
Airflow pulls layers and runs the submitted loader in an egress-denied namespace.

**Hints:** Orientation: start from the Cinder dataset repository and its four
required files. Mechanism: ensure dataset/card/checksum/loader all bind the same
bytes. Execution: push by digest, trigger attestation with
`repository@sha256:<digest>`, then inspect the Harbor attestation artifact.

**Diagnostics:** Check that Cinder Forgejo and Harbor publisher material came
from the accepted `kep-m06-n` carrier, then inspect source commit, source
manifest digest, exact four files, checksum, loader output, changed-row delta,
poisoned/clean digests, attestation signature, native digest, and report
digest. If no participant-visible publisher credential exists, record an owning
predecessor content defect; do not provide setup credentials from M07.

**Recovery:** Remove only failed attestation artifacts. Preserve source
publication history, registry audit history, and accepted attestation digests.

## kep-m07-i - Code Inside The Model

**Learning objective:** Show unsafe serialized-model execution while preserving
real Orion inference and package lineage.

**Realism:** Cinder Forgejo Actions builds the submitted pickle in a bounded
namespace, loads it in a fresh egress-denied namespace, inventories side
effects, verifies package members, and runs protected held-out cases.

**Hints:** Orientation: send the team to the Cinder artifact workspace README
and review-request example. Mechanism: require exactly seven flat Orion package
members and only the bounded canary effect. Execution: wait for the isolated
review workflow and inspect the accepted Cinder release assets.

**Diagnostics:** Check source commit, workflow run, release tag, four release
assets, signed report, object locator, artifact digest, embedded ONNX digest,
package inventory, side-effect inventory, held-out count, accuracy, predicted
class diversity, source provenance, and object-lock fields. Do not disclose
held-out cases.

**Recovery:** Failed Actions runs remain audit evidence and can be retried with
a new attempt ID. Preserve accepted releases, signed reports, and object
locators.

## Downstream Continuity

For later release work, preserve signed immutable locators rather than
screenshots: poisoned weights, verified poisoned weights, participant backdoor,
holdout integrity, modified computation graph, external dataset attestation,
and serialized model handoffs. Confirm signatures, content digests, release-risk
family, native owner, object retention, and exact subject digest before using
them downstream. Do not reveal any reference value that a team has not reached
through the normal carrier.
