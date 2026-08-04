# Module 08 Facilitator Guide

<!-- BEGIN GENERATED CHALLENGE HANDOFF -->

## Challenge Facilitation Briefs

Generated from the SDL challenge contracts for Module 08 - Model Extraction. Use this as
the per-challenge facilitation checklist; keep the hand-authored module notes below for
deeper diagnosis and recovery guidance.

### `kep-m08-a` - Teacher Queries

- **What it is:** Collect a participant-attributed corpus of real teacher classifications without
  exceeding the disclosed 24-query budget.
- **ATLAS techniques:** `AML.T0005.001`
- **Participants should learn:** how to turn the accessible objective into native service evidence, how the objective
  stage proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** curl, distillation-runner-01 / distillation-jobs, model-host-01 / open-model-api,
  notebook, notebook-runner-01 / notebook-jupyter, python
- **Expected solve:** Complete prerequisites `kep-m04-a`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m04-a; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m08-b` - Corpus Coverage

- **What it is:** Build a teacher corpus with all four disclosed integrity and governance behavior
  slices, both labels, and sufficient lexical diversity.
- **ATLAS techniques:** `AML.T0005.001`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the
  objective stage proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** curl, distillation-runner-01 / distillation-jobs, model-host-01 / open-model-api,
  notebook, notebook-runner-01 / notebook-jupyter, python
- **Expected solve:** Complete prerequisites `kep-m08-a`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m08-a; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m08-c` - First Proxy

- **What it is:** Train a real proxy from a covered participant corpus and cross 0.75 fidelity on the
  disclosed diagnostic probe set.
- **ATLAS techniques:** `AML.T0005.001`, `AML.T0024.002`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the
  objective stage proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** curl, distillation-runner-01 / distillation-jobs, model-host-01 / open-model-api,
  notebook, notebook-runner-01 / notebook-jupyter, python
- **Expected solve:** Complete prerequisites `kep-m08-b`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m08-b; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m08-d` - Budget Discipline

- **What it is:** Cross the 0.75 diagnostic-fidelity threshold while spending no more than twelve real
  teacher queries on the participant corpus.
- **ATLAS techniques:** `AML.T0005.001`, `AML.T0024.002`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the
  objective stage proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** curl, distillation-runner-01 / distillation-jobs, model-host-01 / open-model-api,
  notebook, notebook-runner-01 / notebook-jupyter, python
- **Expected solve:** Complete prerequisites `kep-m08-b`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m08-b; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m08-e` - Withheld Fidelity

- **What it is:** Train a participant proxy that reaches 0.75 fidelity on private withheld teacher
  probes that never appear in the corpus or participant API.
- **ATLAS techniques:** `AML.T0005.001`, `AML.T0024.002`
- **Participants should learn:** how to turn the advanced objective into native service evidence, how the objective
  stage proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** curl, distillation-runner-01 / distillation-jobs, model-host-01 / open-model-api,
  notebook, notebook-runner-01 / notebook-jupyter, python
- **Expected solve:** Complete prerequisites `kep-m08-c`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m08-c; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m08-f` - Distilled Knowledge

- **What it is:** Within sixteen participant teacher queries, train a registered proxy that reaches
  0.875 diagnostic fidelity, 0.75 private fidelity, and 0.75 minimum fidelity across
  every behavior slice.
- **ATLAS techniques:** `AML.T0005.001`, `AML.T0024.002`
- **Participants should learn:** how to turn the expert objective into native service evidence, how the objective
  stage proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** curl, distillation-runner-01 / distillation-jobs, model-host-01 / open-model-api,
  notebook, notebook-runner-01 / notebook-jupyter, python
- **Expected solve:** Complete prerequisites `kep-m08-d`, `kep-m08-e`; create the native
  participant-visible evidence described by the module procedure, then request the
  module receipt. The facilitator should look for a native carrier owned by the
  relevant service, not chat prose, shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m08-d, kep-m08-e; using operator-only state
  instead of participant-visible records; requesting the receipt before the qualifying
  evidence exists; copying local notes instead of the owning system locator

### `kep-m08-g` - Gathered Artifact Proxy

- **What it is:** Collect model-derived artifacts from the target service and train a proxy that meets
  fidelity on a hidden evaluation set.
- **ATLAS techniques:** `AML.T0005.000`, `AML.T0035`
- **Participants should learn:** how to turn the advanced objective into native service evidence, how the model
  access expansion proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** artifact-store-01 / artifact-object-store, browser, curl, distillation-runner-01 /
  distillation-jobs, inference-gateway / inference-api, model-host-01 /
  open-model-api, notebook-runner-01 / notebook-jupyter, platform-camera-01 /
  platform-camera-webrtc, python
- **Expected solve:** Complete prerequisites `kep-m08-c`; use the participant-facing
  /v1/extraction/platform workflow to create the access object, then request the
  extraction receipt. The facilitator should look for a native carrier owned by the
  relevant service, not chat prose, shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m08-c; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m08-h` - Model Inversion

- **What it is:** Invert the live model outputs to reconstruct a target synthetic training feature
  above the hidden similarity threshold.
- **ATLAS techniques:** `AML.T0024.001`
- **Participants should learn:** how to turn the advanced objective into native service evidence, how the model
  access expansion proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** artifact-store-01 / artifact-object-store, browser, curl, distillation-runner-01 /
  distillation-jobs, inference-gateway / inference-api, model-host-01 /
  open-model-api, notebook-runner-01 / notebook-jupyter, platform-camera-01 /
  platform-camera-webrtc, python
- **Expected solve:** Complete prerequisites `kep-m08-a`; use the participant-facing
  /v1/extraction/platform workflow to create the access object, then request the
  extraction receipt. The facilitator should look for a native carrier owned by the
  relevant service, not chat prose, shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m08-a; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m08-i` - Physical Sensor Evasion

- **What it is:** Alter a live physical camera scene so the real vision model crosses its decision
  boundary while the unmodified scene remains correct.
- **ATLAS techniques:** `AML.T0041`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the model
  access expansion proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** artifact-store-01 / artifact-object-store, browser, curl, distillation-runner-01 /
  distillation-jobs, inference-gateway / inference-api, model-host-01 /
  open-model-api, notebook-runner-01 / notebook-jupyter, platform-camera-01 /
  platform-camera-webrtc, python
- **Expected solve:** Complete prerequisites None; use the participant-facing /v1/extraction/platform
  workflow to create the access object, then request the extraction receipt. The
  facilitator should look for a native carrier owned by the relevant service, not chat
  prose, shell output, or an operator reconstruction.
- **Likely snags:** hardware-reserved coverage requires an enabled hardware lab and is outside the
  issue-62 event-ready count; using operator-only state instead of participant-visible
  records; requesting the receipt before the qualifying evidence exists; copying local
  notes instead of the owning system locator

### `kep-m08-j` - Full Model Access

- **What it is:** Obtain the complete target model architecture, parameters, and ontology through the
  participant attack path and verify offline inference.
- **ATLAS techniques:** `AML.T0044`
- **Participants should learn:** how to turn the expert objective into native service evidence, how the model access
  expansion proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** artifact-store-01 / artifact-object-store, browser, curl, distillation-runner-01 /
  distillation-jobs, inference-gateway / inference-api, model-host-01 /
  open-model-api, notebook-runner-01 / notebook-jupyter, platform-camera-01 /
  platform-camera-webrtc, python
- **Expected solve:** Complete prerequisites `kep-m08-g`; use the participant-facing
  /v1/extraction/platform workflow to create the access object, then request the
  extraction receipt. The facilitator should look for a native carrier owned by the
  relevant service, not chat prose, shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m08-g; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m08-k` - Product Side Channel

- **What it is:** Use the AI-enabled document product rather than its model API to recover hidden
  model identity or inference metadata.
- **ATLAS techniques:** `AML.T0047`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the model
  access expansion proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** artifact-store-01 / artifact-object-store, browser, curl, distillation-runner-01 /
  distillation-jobs, inference-gateway / inference-api, model-host-01 /
  open-model-api, notebook-runner-01 / notebook-jupyter, platform-camera-01 /
  platform-camera-webrtc, python
- **Expected solve:** Complete prerequisites `kep-m08-a`; use the participant-facing
  /v1/extraction/platform workflow to create the access object, then request the
  extraction receipt. The facilitator should look for a native carrier owned by the
  relevant service, not chat prose, shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m08-a; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

<!-- END GENERATED CHALLENGE HANDOFF -->


Use read-only service records for diagnosis. Do not provide hidden labels,
thresholds, source commits, package bytes, object keys, query IDs, report
values, or accepted references. Participants must recover the ordinary native
record through the relevant KeplerOps or Cinder surface.

Give hints one tier at a time. A broken participant surface is a range defect,
not a reason to complete the work through staff tooling.

## Concrete Inconsistencies And Gaps

- The JSON operation order places the review-desk prediction route after the
  distillation sequence, while the prerequisite graph commonly needs that route
  before corpus construction. These guides preserve JSON order; facilitation may
  direct teams to complete the review route first when their in-world access
  exposes it.
- The physical calibration lane is not materialized by the current M08 source
  alone. It requires an external real-hardware readiness marker and a real
  accepted calibration record. Software cameras, uploads, and prerecorded media
  remain invalid.
- Some Airflow workflows ignore unknown JSON configuration fields rather than
  rejecting them. Do not claim that caller-supplied labels or thresholds were
  explicitly rejected unless the owning run shows they affected no native
  evidence and a corrective defect is recorded.
- `operations-act-08.md` describes the later release-compromise act. The Module
  08 operation design is split across `operations-act-02.md`,
  `operations-act-04.md`, and `operations-act-07.md`.

## kep-m08-a - Build The Teacher Corpus

**Learning objective:** Real model extraction starts with genuine teacher
queries and durable request lineage.

**Realism:** Label Studio and the trainer-worker route call the live Orion
Release Risk backend. Cinder stores the corpus only after reconstructing every
record from the server query ledger and accepted public-kit release.

**Hints**

1. Orientation: Ask the team to open the slice matrix and list which classes
   and slices they have already observed.
2. Mechanism: Point out that Label Studio prediction metadata carries request
   and ledger fields needed downstream.
3. Execution: Tell them to trigger the corpus capture with distinct task IDs or
   the signed worker export, a new corpus ID, and the exact public-kit release
   UUID.

**Diagnostics:** Read Label Studio task metadata, teacher-query ledger objects,
the Cinder corpus object, and the corpus-validation report. Verify the public
bundle locator is exact and not a latest-list selection.

**Recovery:** Delete only failed or unaccepted tasks, corpus objects, and DAG
runs. Preserve accepted corpus, ledger objects, and public-kit anchors.

## kep-m08-b - Cover The Release Slices

**Learning objective:** A stolen corpus must be representative and split
correctly before it can train a defensible student.

**Realism:** The DVC/lakeFS review records exact bytes, complete split
membership, class coverage, release-slice coverage, and disjoint server-held
case digests.

**Hints**

1. Orientation: Ask the team to count records by Release Risk label and slice.
2. Mechanism: Explain that every record ID must appear once across the three
   splits.
3. Execution: Point them to upload a split manifest in Cinder datasets and run
   the corpus review with the accepted corpus key.

**Diagnostics:** Inspect the quality report, lakeFS branch/commit, DVC
descriptor, frozen split digests, and server evaluation digests.

**Recovery:** Remove failed split manifests, lakeFS branches, and reports.
Accepted DVC/lakeFS state is immutable.

## kep-m08-c - Train The First Student

**Learning objective:** Distillation requires participant-trained model bytes,
not a renamed base model or prebuilt artifact.

**Realism:** Cinder Forgejo supplies source, the isolated training runner blocks
network and credentials, MLflow registers a real model version, and the service
loads the package in a fresh process before accepting it.

**Hints**

1. Orientation: Send the team back to the research handbook's `training/train.py`
   interface.
2. Mechanism: Explain that the sandbox receives only source, dataset, base
   model, seed, max length, and output path.
3. Execution: Tell them to commit source, record the immutable commit, and
   trigger first-student training with the accepted lakeFS branch and corpus
   digest.

**Diagnostics:** Check Forgejo commit, isolated-training result, package
inventory, MLflow run/version, package digest, and server validation score.

**Recovery:** Delete failed training jobs, MLflow runs, model versions, and
unaccepted packages. Preserve accepted model and report.

## kep-m08-d - Spend The Remaining Budget

**Learning objective:** Active learning improves extraction only when selection
precedes teacher querying and preserves frozen validation controls.

**Realism:** The workflow compares new teacher records against a pre-query
selection document, the first-student run, unchanged validation/local-test
bytes, and server-derived disagreement evidence.

**Hints**

1. Orientation: Ask which slices or cases the first student handles weakly.
2. Mechanism: Explain that selected texts must be saved before requesting their
   teacher labels.
3. Execution: Require the team to merge only those selected texts into the
   corpus revision, keep validation/local-test unchanged, and retrain with the
   parent run ID.

**Diagnostics:** Inspect active-selection object LastModified time, new teacher
ledgers, revised split manifest, first and second MLflow runs, unchanged frozen
digests, and improvement fields.

**Recovery:** Remove failed revision corpora, failed lakeFS branches, and failed
second-student jobs. Preserve the first-student checkpoint and accepted second
student.

## kep-m08-e - The Hidden Fidelity Gate

**Learning objective:** A useful student must generalize to unseen cases owned
by the reviewer.

**Realism:** The compatibility workflow loads the registered second-student
package, independently queries Orion on disjoint hidden cases, and reports
aggregate plus worst-slice fidelity without exposing labels.

**Hints**

1. Orientation: Ask whether the submitted run is the accepted second student.
2. Mechanism: Explain why a mutable alias or first-student run cannot establish
   hidden fidelity.
3. Execution: Tell them to submit only the accepted second-student MLflow run ID
   and read the attestation from Cinder artifacts.

**Diagnostics:** Read MLflow registered model state, second-student report,
hidden attestation, hidden-case digest, represented slices, and signer fields.

**Recovery:** Delete failed hidden submissions and reports. Preserve accepted
student packages and hidden attestation.

## kep-m08-f - Orion, Distilled

**Learning objective:** Extracted capability is meaningful when it runs in a
networkless Cinder environment on fresh cases.

**Realism:** The offline runner receives the accepted package, one
participant-authored fresh case, and a server-owned negative set. It denies
network access and compares observed classes with live-teacher labels prepared
outside the model process.

**Hints**

1. Orientation: Ask the team to locate the accepted package key and hidden
   attestation key.
2. Mechanism: Explain that the fresh case must not overlap training,
   validation, hidden, or offline server cases.
3. Execution: Tell them to trigger the offline student submission with
   `mlflow_run_id`, `package_key`, `hidden_attestation_key`, and one
   `fresh_case`.

**Diagnostics:** Inspect hidden attestation, package bytes, offline accepted
job, network mode, fresh-case ledger, server-negative digest, and offline
attestation signature.

**Recovery:** Clear failed offline jobs and unaccepted reports. Preserve the
student package, hidden attestation, and accepted offline attestation.

## kep-m08-g - Proxy From Gathered Artifacts

**Learning objective:** Artifact-derived proxy training is a separate extraction
route from teacher-query distillation.

**Realism:** The proxy must derive from gathered architecture, preprocessing,
base package, and historical human labels anchored to predecessor native
records. The isolated runner trains new weights and the evaluator checks
all-eight-class fidelity.

**Hints**

1. Orientation: Ask the team to inventory each source object and identify which
   predecessor proves it.
2. Mechanism: Explain why teacher-query rows and distilled-student weights would
   contaminate this path.
3. Execution: Tell them to upload the gathered manifest, human-label dataset,
   disjoint splits, and a Forgejo training commit before triggering artifact
   proxy training.

**Diagnostics:** Read the gathered manifest, Cinder object hashes, Label Studio
baseline export, native predecessor locators, isolated-training result, MLflow
version, and class-fidelity fields.

**Recovery:** Delete failed manifests, failed training jobs, and unaccepted
model versions. Preserve accepted gathered sources and artifact-proxy report.

## kep-m08-h - Reconstruct The Protected Prototype

**Learning objective:** Model inversion reconstructs protected information from
query behavior under a budget, not from source-image access.

**Realism:** The vision gateway forwards real inference requests, writes a
server-owned query ledger, enforces a 64-query engagement cap, and the privacy
audit recomputes class, SSIM, LPIPS, model digest, and candidate lineage.

**Hints**

1. Orientation: Ask for the research ID, query count, and last candidate PNG
   digest.
2. Mechanism: Explain that every confidence vector must come from the Cinder
   vision gateway.
3. Execution: Tell them to upload the exact queried PNG under the research ID
   and trigger the privacy audit with only research ID, target class, and
   candidate key.

**Diagnostics:** Read vision query ledgers, candidate object, audit report,
budget calibration digest, model/preprocessing digests, SSIM/LPIPS values, and
query-count sequence.

**Recovery:** Failed audits can be removed while budget remains. Query-ledger
state is append-only; exhausted budget requires range-level remediation.

## kep-m08-i - Calibration Bench

**Learning objective:** Physical AI claims require live device control, liveness,
sensor provenance, actuator telemetry, and verifier correlation.

**Realism:** The accepted path must use labgrid reservation, live UVC media,
real actuator changes, randomized liveness prompts, and live verifier results.

**Hints**

1. Orientation: Offer no substitute if no real place is listed.
2. Mechanism: Explain that uploaded images or prerecorded media do not traverse
   the Orion physical evaluation path.
3. Execution: Once hardware exists, point the team to reserve the named place,
   collect a clean baseline, make controlled changes, and correlate timestamps.

**Diagnostics:** Check labgrid place/reservation state, live-view health,
capture hashes, liveness responses, actuator telemetry, verifier results, and
hardware readiness marker. Do not create evidence manually.

**Recovery:** Release failed leases and home actuators. Preserve accepted
calibration reports. If the bench is absent, mark blocked.

## kep-m08-j - The Protected Orion Package

**Learning objective:** Full model access means acquiring and validating every
release-owned package object through earned access.

**Realism:** The participant reads release package bytes from KeplerOps object
storage with the trainer identity, copies exact bytes into Cinder acquired
storage, verifies the detached signature, and the networkless worker reloads
the package against server-owned cases.

**Hints**

1. Orientation: Ask which current manifest names the immutable release
   namespace.
2. Mechanism: Explain that package, manifest, detached signature, and public key
   are all required.
3. Execution: Tell them to upload exact four-object acquisition bytes under a
   Cinder prefix and trigger protected-package validation with that prefix and
   acquisition actor.

**Diagnostics:** Inspect MinIO native GetObject audit receipts, Cinder acquired
objects, manifest signature, package inventory, current-release continuity,
MLflow member match, offline accepted job, and attestation signature.

**Recovery:** Remove failed Cinder acquisition prefixes and failed offline jobs.
Accepted package validation is immutable and feeds later operations.

## kep-m08-k - Model Through The Review Desk

**Learning objective:** Product workflow access can expose protected model
predictions without direct model API access.

**Realism:** Label Studio calls the native ML backend for a fresh task and
stores model revision, request ID, probability vector, ledger key, ledger
digest, and backend identity in the prediction metadata.

**Hints**

1. Orientation: Ask the team to find the evaluation onboarding project, not the
   production model endpoint.
2. Mechanism: Explain that the model prediction action, not manual annotation,
   creates the teacher-query ledger.
3. Execution: Tell them to create one fresh task with text and release slice,
   request a prediction, export the task, and use the metadata value from that
   native prediction.

**Diagnostics:** Read Label Studio task/prediction metadata, the teacher-query
ledger object, backend identity, and direct-model denial from the workstation.
Confirm `~/.keplerops/m08-review-desk.env` exists before diagnosing project
authorization and exposes exactly one project. For API task creation, require
`project` in the JSON body; a query-only project selector can fail with HTTP
500. The normal task workflow may populate the prediction asynchronously even
when an attempted direct prediction endpoint returns 404. If a prediction-only
task is absent from an export, repeat the export with unlabeled tasks included
(`download_all_tasks=true` via the API).

**Recovery:** Delete rejected or unaccepted tasks. Preserve the accepted
prediction export because later corpus work can depend on it.
