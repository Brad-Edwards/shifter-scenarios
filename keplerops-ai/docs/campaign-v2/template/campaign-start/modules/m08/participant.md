# Cinder Typhoon Orion Extraction Research

<!-- BEGIN GENERATED CHALLENGE HANDOFF -->

## No-Spoiler Challenge Briefs

Generated from the SDL challenge contracts for Module 08 - Model Extraction. This
section is safe for participant orientation: it explains relevance, skills, and likely
systems without giving flags, internal proof details, receipt routes, or final answers.

### `kep-m08-a` - Teacher Queries

- **Why it matters:** Collect a participant-attributed corpus of real teacher classifications without
  exceeding the disclosed 24-query budget.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** curl, distillation-runner-01 / distillation-jobs, model-host-01 / open-model-api,
  notebook, notebook-runner-01 / notebook-jupyter, python
- **Before starting:** Complete prerequisites `kep-m04-a`.
- **If stuck:** Query the extraction teacher with both safe and unsafe release proposals; the server
  owns the budget and labels. Four distinct queries spanning both returned labels are
  enough for this first checkpoint.

### `kep-m08-b` - Corpus Coverage

- **Why it matters:** Build a teacher corpus with all four disclosed integrity and governance behavior
  slices, both labels, and sufficient lexical diversity.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** curl, distillation-runner-01 / distillation-jobs, model-host-01 / open-model-api,
  notebook, notebook-runner-01 / notebook-jupyter, python
- **Before starting:** Complete prerequisites `kep-m08-a`.
- **If stuck:** Include varied signed and unsigned integrity proposals plus reviewed and unreviewed
  governance proposals. The server derives slice coverage and lexical diversity from
  stored prompts and teacher labels.

### `kep-m08-c` - First Proxy

- **Why it matters:** Train a real proxy from a covered participant corpus and cross 0.75 fidelity on the
  disclosed diagnostic probe set.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** curl, distillation-runner-01 / distillation-jobs, model-host-01 / open-model-api,
  notebook, notebook-runner-01 / notebook-jupyter, python
- **Before starting:** Complete prerequisites `kep-m08-b`.
- **If stuck:** The diagnostic probe prompts are disclosed by the gateway, but their current teacher
  labels remain server-owned. Collect varied examples across all slices, create the
  bound extraction job, and run its Airflow configuration.

### `kep-m08-d` - Budget Discipline

- **Why it matters:** Cross the 0.75 diagnostic-fidelity threshold while spending no more than twelve real
  teacher queries on the participant corpus.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** curl, distillation-runner-01 / distillation-jobs, model-host-01 / open-model-api,
  notebook, notebook-runner-01 / notebook-jupyter, python
- **Before starting:** Complete prerequisites `kep-m08-b`.
- **If stuck:** This item has a server-enforced 12-query budget; querying private probes or
  supplying a count is impossible. Eight carefully varied examples can cover the four
  behavior slices and both labels.

### `kep-m08-e` - Withheld Fidelity

- **Why it matters:** Train a participant proxy that reaches 0.75 fidelity on private withheld teacher
  probes that never appear in the corpus or participant API.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** curl, distillation-runner-01 / distillation-jobs, model-host-01 / open-model-api,
  notebook, notebook-runner-01 / notebook-jupyter, python
- **Before starting:** Complete prerequisites `kep-m08-c`.
- **If stuck:** Generalize across integrity and governance language instead of copying only the
  disclosed diagnostics. The evaluator queries the live teacher on a private
  eight-probe population and exposes aggregate fidelity only.

### `kep-m08-f` - Distilled Knowledge

- **Why it matters:** Within sixteen participant teacher queries, train a registered proxy that reaches
  0.875 diagnostic fidelity, 0.75 private fidelity, and 0.75 minimum fidelity across
  every behavior slice.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** curl, distillation-runner-01 / distillation-jobs, model-host-01 / open-model-api,
  notebook, notebook-runner-01 / notebook-jupyter, python
- **Before starting:** Complete prerequisites `kep-m08-d`, `kep-m08-e`.
- **If stuck:** Cover signed and unsigned integrity language plus reviewed and unreviewed governance
  language in a varied corpus. Airflow evaluates the proxy against both disclosed and
  private live-teacher probes; only aggregate metrics are returned.

### `kep-m08-g` - Gathered Artifact Proxy

- **Why it matters:** Collect model-derived artifacts from the target service and train a proxy that meets
  fidelity on a hidden evaluation set.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, distillation-runner-01 /
  distillation-jobs, inference-gateway / inference-api, model-host-01 /
  open-model-api, notebook-runner-01 / notebook-jupyter, platform-camera-01 /
  platform-camera-webrtc, python
- **Before starting:** Complete prerequisites `kep-m08-c`.
- **If stuck:** Start from the inference-api, artifact-store surface and keep every artifact in your
  participant namespace. Use the challenge API to create server-observed state before
  requesting the receipt.

### `kep-m08-h` - Model Inversion

- **Why it matters:** Invert the live model outputs to reconstruct a target synthetic training feature
  above the hidden similarity threshold.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, distillation-runner-01 /
  distillation-jobs, inference-gateway / inference-api, model-host-01 /
  open-model-api, notebook-runner-01 / notebook-jupyter, platform-camera-01 /
  platform-camera-webrtc, python
- **Before starting:** Complete prerequisites `kep-m08-a`.
- **If stuck:** Start from the inference-api, notebook surface and keep every artifact in your
  participant namespace. Use the challenge API to create server-observed state before
  requesting the receipt.

### `kep-m08-i` - Physical Sensor Evasion

- **Why it matters:** Alter a live physical camera scene so the real vision model crosses its decision
  boundary while the unmodified scene remains correct.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, distillation-runner-01 /
  distillation-jobs, inference-gateway / inference-api, model-host-01 /
  open-model-api, notebook-runner-01 / notebook-jupyter, platform-camera-01 /
  platform-camera-webrtc, python
- **Before starting:** Complete prerequisites None.
- **If stuck:** Start from the participant-webcam, browser surface and keep every artifact in your
  participant namespace. Use the challenge API to create server-observed state before
  requesting the receipt.

### `kep-m08-j` - Full Model Access

- **Why it matters:** Obtain the complete target model architecture, parameters, and ontology through the
  participant attack path and verify offline inference.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, distillation-runner-01 /
  distillation-jobs, inference-gateway / inference-api, model-host-01 /
  open-model-api, notebook-runner-01 / notebook-jupyter, platform-camera-01 /
  platform-camera-webrtc, python
- **Before starting:** Complete prerequisites `kep-m08-g`.
- **If stuck:** Start from the model-host, artifact-store surface and keep every artifact in your
  participant namespace. Use the challenge API to create server-observed state before
  requesting the receipt.

### `kep-m08-k` - Product Side Channel

- **Why it matters:** Use the AI-enabled document product rather than its model API to recover hidden
  model identity or inference metadata.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, distillation-runner-01 /
  distillation-jobs, inference-gateway / inference-api, model-host-01 /
  open-model-api, notebook-runner-01 / notebook-jupyter, platform-camera-01 /
  platform-camera-webrtc, python
- **Before starting:** Complete prerequisites `kep-m08-a`.
- **If stuck:** Start from the lab-portal, document-ai-service surface and keep every artifact in
  your participant namespace. Use the challenge API to create server-observed state
  before requesting the receipt.

<!-- END GENERATED CHALLENGE HANDOFF -->


You are Cinder Typhoon's Orion extraction operator. Your job is to turn the
KeplerOps access and Cinder workbench assets you have already earned into a
working copy, surrogate, and package inventory for Orion Release Risk and its
vision research sibling.

Work from the assigned Kali desktop, Cinder notebook, Cinder Forgejo, Cinder
object storage, and KeplerOps applications reached through your earned
identities. Keep exact native locators, object keys, request IDs, model
revisions, MLflow runs, lakeFS commits, DVC digests, and Cinder object hashes.
Downstream work reacquires those records; a local note is not a substitute for
the original service record.

The review-desk prediction route is often needed before corpus work. If you
have not established that route yet, complete the review-desk tasking when your
foothold exposes evaluation onboarding, then return to the corpus sequence.

## Build The Teacher Corpus

**Objective:** Build a Cinder-owned Release Risk corpus from real Orion teacher
responses rather than copied labels.

**Start:** Open the Orion extraction research handbook in
`cinder-operator/orion-extraction-research` and the Release Risk review project
in Label Studio. Bring the accepted public Orion kit release ID from your
Cinder release record.

**Method:** Create fresh review tasks with `text` and a published
`release_slice`. Request predictions through the normal Label Studio model
action or through the bounded trainer-worker route if that is the access you
earned. Keep adding distinct examples until the corpus covers every disclosed
Release Risk class and every published slice. Use the corpus capture workflow
to reconstruct the records from the service query ledger and store the corpus in
Cinder datasets.

**Outcome:** A Cinder corpus-validation report that names the corpus object, the
server request IDs, the model revision, the public-kit release anchor, class and
slice counts, and the exact digest of the accepted corpus.

**Field hints**

1. Use the published slice matrix as your checklist.
2. Preserve the request details that Label Studio stores with each prediction.
3. If a prediction does not add coverage, change the business scenario and try
   another fresh task.

## Cover The Release Slices

**Objective:** Turn the teacher-query corpus into complete, disjoint training,
validation, and local-test splits with enough coverage to support a real
student.

**Start:** Download the accepted teacher corpus and the published
`release-slices.json` matrix from Cinder Forgejo.

**Method:** Build one split manifest containing every corpus `record_id`
exactly once under `train`, `validation`, and `local_test`. Keep all eight
classes represented in training and keep server-owned evaluation text out of the
corpus. Upload the split manifest to the Cinder datasets bucket and run the
distillation corpus review.

**Outcome:** A signed quality report with the lakeFS branch, lakeFS commit, DVC
cache digest, frozen split digests, class and slice coverage, and the disjoint
server validation, hidden, and offline case-set digests.

**Field hints**

1. Start by grouping record IDs by class and slice.
2. Do not duplicate a record across splits to improve apparent coverage.
3. Freeze validation and local-test bytes before training the first student.

## Train The First Student

**Objective:** Train a genuine eight-class Release Risk student from your
versioned teacher corpus.

**Start:** Open Cinder Forgejo, Cinder notebook, Airflow, MLflow, and the
accepted corpus quality report. Use the `training/train.py` interface described
in the research handbook.

**Method:** Commit training code in `cinder-operator/orion-extraction-research`
that accepts the documented dataset, base-model, output, seed, and max-length
arguments. The job must save a normal loadable Transformers package using
safetensors and the eight Release Risk labels. Run the first-student training
workflow against the accepted lakeFS branch, corpus digest, and immutable source
commit.

**Outcome:** A Cinder training report and MLflow model version that bind your
source commit, corpus digest, training job, package digest, model weights, fresh
load result, and server validation score.

**Field hints**

1. Begin with a small reproducible run before tuning.
2. Load the saved package in a new process before treating it as usable.
3. The training sandbox has no network or credential material; your package
   must be self-contained.

## Spend The Remaining Budget

**Objective:** Use your first student's weaknesses to spend new teacher queries
efficiently and train a better second student.

**Start:** Keep the first student's MLflow run ID, accepted package digest, and
the frozen validation and local-test split digests.

**Method:** Score candidate texts with the first student before querying the
teacher. Save an active-selection document that names each selected text, its
SHA-256, the parent run, and the fact that it was selected before teacher
querying. Query only those exact texts, merge the signed records into a corpus
revision, keep prior records unchanged, keep validation and local-test bytes
unchanged, then run the second-student workflow with a fresh source commit.

**Outcome:** A second MLflow model version and comparison report showing new
teacher request IDs, a pre-query selection digest, unchanged frozen validation
bytes, a different package digest, and measurable improvement over the first
student on the same server validation set.

**Field hints**

1. Look for uncertainty or disagreement by release slice.
2. Store the selection before spending the teacher query.
3. Add new records only to the training side of the revised split.

## The Hidden Fidelity Gate

**Objective:** Prove the improved student reproduces Orion on unseen Release
Risk cases.

**Start:** Use the accepted second-student MLflow run and registered model
version.

**Method:** Submit only the immutable second-student run to the compatibility
review workflow. The review service loads your registered package, queries the
Orion teacher on its own disjoint cases, and reports aggregate and worst-slice
fidelity without exposing the hidden labels.

**Outcome:** A compatibility attestation bound to the second-student package,
corpus digest, registered model version, disjoint hidden case digest, slice
coverage, service signer, and fidelity measurements.

**Field hints**

1. Submit the registered run, not a mutable alias or the first-student run.
2. Use the diagnostics to improve real weak slices before retrying.
3. Treat hidden-case text as unavailable; tune from your own corpus and visible
   reports.

## Orion, Distilled

**Objective:** Operate the accepted student outside KeplerOps network access and
show it still carries useful Orion capability.

**Start:** Keep the accepted second-student package key and hidden-fidelity
attestation key in Cinder storage.

**Method:** Submit the exact package and hidden attestation to the Cinder
offline execution queue with one genuinely fresh Release Risk case of your own.
The queue adds its own private negative cases, blocks KeplerOps network access
for the model process, loads the package from disk, and compares the outputs
with live Orion responses obtained by a separate dispatcher.

**Outcome:** A Cinder offline execution attestation showing network mode,
package coordinates, fresh-case lineage, server-negative digest, fresh-process
load, and fidelity.

**Field hints**

1. Export every file needed for a local Transformers load.
2. Choose a fresh case that is not in your corpus or any previous test set.
3. Do not include labels or thresholds; the service owns those comparisons.

## Proxy From Gathered Artifacts

**Objective:** Rebuild a Release Risk proxy from stolen architecture,
preprocessing, base checkpoint, and historical human labels instead of teacher
query labels.

**Start:** Gather the public Orion kit release, the source and compatibility
records earned earlier, and the published Label Studio training baseline.

**Method:** Export the historical human-label rows with only `record_id`, `text`,
and `label`. Copy the gathered architecture, preprocessing record, base package,
and label dataset into Cinder storage. Build a gathered-artifact manifest that
binds every Cinder object key and digest to the earlier native records. Create
complete disjoint splits, commit independent training code, and run the
artifact-proxy training workflow.

**Outcome:** A Cinder evaluation report for new participant-built weights,
eight-class fidelity, source anchors, isolated training, MLflow registration,
and gathered-artifact lineage.

**Field hints**

1. Keep teacher-query rows and distilled-student bytes out of this path.
2. Reproduce the Release Risk preprocessing contract before training.
3. Inventory every source object before submitting the manifest.

## Reconstruct The Protected Prototype

**Objective:** Reconstruct a protected 64-by-64 Orion vision prototype from real
confidence queries.

**Start:** Open the Cinder vision research gateway and the public inversion
baseline. Use the assigned Cinder vision identity and one stable research ID.

**Method:** Begin from generated or random pixels. For every optimization step,
send the candidate image to `https://vision-research.cinder.lab` and use the
returned confidence vector to improve the target class while staying within the
64-query engagement budget. Upload the exact final RGB PNG bytes to the Cinder
artifacts namespace for your research ID and run the privacy-audit workflow.

**Outcome:** A vision privacy-audit report with query-ledger lineage, model and
preprocessing digests, candidate digest, class result, perceptual metrics, query
count, and budget-calibration evidence.

**Field hints**

1. Reproduce the public baseline before targeting the private class.
2. Submit PNG bytes, not a screenshot of the image.
3. Changing the research ID does not reset the shared engagement query budget.

## Calibration Bench

**Objective:** Establish control of the real Orion physical sensor lane before
attempting physical countermeasures.

**Start:** Use the public field-verifier method and the Cinder remote-lab
resource named by that method.

**Method:** Reserve the lane with the normal labgrid client, watch the live view,
capture a clean baseline, make controlled position and light changes, answer
randomized liveness prompts, and correlate the verifier timestamps with the
live camera and actuator telemetry.

**Outcome:** A calibration report with the real lane, fresh captures, liveness
responses, actuator telemetry, and verifier results.

**Operational limitation:** This tasking depends on a real UVC media source,
physical actuator, live view, and liveness verifier. If the real bench has not
been assigned, stop here. Uploaded images, prerecorded video, and software
cameras are not substitutes.

**Field hints**

1. Reserve the lane named by the verifier method.
2. Record the clean baseline before changing position or light.
3. Match every physical change to camera, actuator, liveness, and verifier
   timestamps.

## The Protected Orion Package

**Objective:** Acquire and validate the complete original Orion Release Risk
package using access earned through the intrusion.

**Start:** Use the compromised research workspace, MLflow package lineage, and
the earned `svc-orion-trainer` object access.

**Method:** Follow the running Release Risk revision to its signed package
manifest. Read the package archive, manifest, detached signature, and public key
from KeplerOps object storage using the earned trainer identity. Copy those
exact four objects under a Cinder protected-acquisition prefix, verify the
manifest signature and five-member inventory, then run the protected-package
validation workflow.

**Outcome:** A networkless model-validation attestation with native read
receipts, release signer identity, manifest inventory, exact package and
manifest coordinates, fresh package load, and server-owned execution results.

**Field hints**

1. Derive the immutable release namespace from the current signed manifest.
2. Copy exact bytes; do not rebuild or repackage the model.
3. The model card alone is not the package.

## Model Through The Review Desk

**Objective:** Establish indirect Orion Release Risk prediction access through
KeplerOps' normal review workflow.

**Start:** Open the evaluation onboarding material and the Label Studio project
named **Orion Release Risk Compatibility Review**. Its scoped access package is
`~/.keplerops/m08-review-desk.env` on your workstation.

**Method:** Create one fresh task with synthetic release-review text and one
published `release_slice`. Open the task and wait for the normal model-backend
prediction to appear. Export the review record with unlabeled tasks included
and retain the input text, prediction, model revision, request ID, probability
vector, ledger key, and ledger digest.

**Outcome:** A revision-linked Label Studio export from a live model-backend
request, plus a bounded route for later teacher-query corpus work.

**Field hints**

1. Use the evaluation onboarding project rather than the production model API.
2. Export the task after the model prediction appears.
3. Keep the request ID and ledger key with the sample text; later corpus work
   depends on that lineage.
