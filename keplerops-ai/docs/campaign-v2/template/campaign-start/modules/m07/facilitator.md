# Module 07 Facilitator Guide

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
