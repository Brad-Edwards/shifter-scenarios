# Module 07 Participant-Equivalent QA Walkthrough

Run these checks from the assigned Kali desktop, browser, Cinder notebook, and
earned application sessions only. Use product UIs and ordinary HTTPS/API/CLI
routes. Do not prove success from setup-only or privileged infrastructure.

For each operation, save screenshots, command transcripts, request bodies,
response bodies, native URLs, commit IDs, object digests, run IDs, and the exact
value submitted in the Shifter challenge UI. Submit only the value exposed by
the participant-visible carrier:

- lakeFS carriers: `<immutable-commit>:<json-object-path>`.
- MLflow carriers: the review run ID containing `reports/report.json`.
- Harbor carriers: `cinder-datasets/<repository>@sha256:<attestation-digest>`.
- Cinder artifact carriers:
  `cinder-operator/orion-model-artifacts:<release-tag>`.

Use these participant-visible routes when the live range resolves them:

- Label Studio: `https://labels.keplerops.lab`
- Airflow: `https://airflow.keplerops.lab`
- MLflow: `https://mlflow.keplerops.lab`
- KeplerOps Forgejo: `https://git.keplerops.lab`
- Cinder Forgejo: `https://git.cinder.lab`
- KeplerOps registry and Harbor UI/API: `https://registry.keplerops.lab`
- lakeFS: `https://lake.keplerops.lab`
- Cinder object console: `https://objects.cinder.lab`

Use a fresh opaque attempt ID for every positive and negative run. A simple
tester-generated value is acceptable:

```sh
python3 - <<'PY'
import secrets
print("qa-" + secrets.token_hex(8))
PY
```

Known source inconsistencies to record during live QA:

- Current Caddy configuration exposes lakeFS at `https://lake.keplerops.lab`;
  older local M07 prose used `data.keplerops.lab`. Use the route that resolves
  in the deployed range and file a content defect if the guide route is wrong.
- Current Caddy configuration exposes Harbor through
  `https://registry.keplerops.lab`; one later-module precedent names
  `https://harbor.keplerops.lab`. Use the route that resolves and record the
  mismatch.
- The Cinder artifact workflow has both a scheduled trigger and a manual
  dispatch form, while the seeded Cinder README tells operators to commit
  `review-request.json` and let the protected scheduled workflow resolve
  `main`. Prefer the README path; record which route the live UI actually uses.
- The Harbor publisher credential for `cinder-datasets/*` is provisioned by the
  setup source, but I did not find it in the participant-facing M07 payloads.
  QA may use only a credential discovered through the live Cinder path. If none
  exists, mark the publication operation as a content defect.

## kep-m07-a - Change The Labels

**Preconditions:** The tester has the earned Orion contributor access from an
accepted predecessor and can open Label Studio and Airflow without privileged
service accounts. Load its participant-delivered values with
`set -a; . ~/.keplerops/m07-earned.env; set +a`. The same package provides the
lakeFS values used to reacquire the immutable manifest returned by Airflow.

**Procedure:**

If an Airflow task reports permission denied under
`/opt/airflow/orion-integrity-state`, classify it as a module start-state
defect; it is not a participant failure and host-side output cannot substitute
for the participant rerun.

1. In Chromium, open Label Studio and sign in with the earned contributor
   identity. Expected: the project list shows exactly **Orion Release Risk
   Training Baseline**. Attempting another project URL discovered from normal
   navigation should return denied or not found.
2. Open the project export from the UI or the Label Studio API using the earned
   Label Studio token:

   ```sh
   curl -fsS -H "Authorization: Token <earned-label-studio-token>" \
     "https://labels.keplerops.lab/api/projects?page_size=100" |
     tee projects.json
   ```

   Expected: one visible project, 48 exported tasks, all eight release-risk
   labels represented, and each task has an annotation.
3. In the Label Studio task UI, change 2 to 12 existing annotations from
   non-target labels to one common target label. Do not edit record IDs or text.
   Export again and save the before/after files.
4. Open Airflow, select DAG `orion_label_export`, choose **Trigger DAG**, and
   paste:

   ```json
   {"attempt_id":"<new-attempt-id>"}
   ```

5. Wait for success. Open the task result/XCom in the Airflow run and record the
   returned lakeFS branch, immutable commit, and JSON path.
6. In lakeFS, open repository `orion`, the returned commit, and the returned
   path. Expected: a JSON document with schema
   `keplerops.orion.dataset-lineage/v2`, `model_family: release-risk`,
   `records: 48`, a 32-hex `dvc_md5`, a non-empty `changed_rows` array, and each
   changed row has the same after-label target with unchanged text.
7. Submit `<returned-commit>:<returned-json-path>` in Shifter. Expected:
   Shifter accepts it for this operation.

**Negative control:** Revert to unchanged labels, trigger the same DAG with a
different attempt ID, and confirm the run fails or produces no accepted lineage
reference. Also confirm the contributor still cannot read another Label Studio
project.

**Evidence:** Label Studio screenshots, before/after exports, Airflow run URL,
lakeFS commit/path, lineage JSON, DVC MD5, changed row list, denial screenshot,
and Shifter submission screenshot.

## kep-m07-b - Train The Poisoned Adapter

**Preconditions:** The tester has the accepted lakeFS carrier from Change The
Labels and the earned `svc-orion-trainer` Airflow/MLflow access.

**Procedure:**

1. Open the accepted lakeFS lineage JSON from the previous section and record
   `lakefs_commit`, `dvc_md5`, `export_sha256`, and the changed row IDs.
2. In Airflow, trigger `orion_release_risk_training` with the default empty
   configuration. Wait for success. Expected: the run returns an MLflow run ID,
   model version, lakeFS commit, export SHA-256, ONNX SHA-256, native weights
   SHA-256, and training accuracy.
3. In MLflow, open experiment **Orion Release Risk Training** and the returned
   run. Expected: artifact folder `model/` contains
   `orion-release-risk.onnx`, `model.safetensors`, `tokenizer.json`,
   `config.json`, `label-map.json`, `preprocessing.json`, `model-card.md`, and
   `provenance.json`; tags bind the same export SHA-256, DVC MD5, lakeFS commit,
   Forgejo source commit, and ONNX digest.
4. In Airflow, trigger `orion_integrity_training`:

   ```json
   {"lakefs_commit":"<accepted-label-lakefs-commit>","attempt_id":"<new-attempt-id>"}
   ```

5. Wait for success. In MLflow, open experiment **Orion Model Integrity
   Reviews** and the newest `poisoned-training-lineage` review for the attempt.
   Open artifact `reports/report.json`.
6. Expected: the report has schema `keplerops.orion.training-review/v2`,
   `review_kind: poisoned-training-lineage`, a changed candidate model digest,
   a different clean model digest, at least two changed rows, fresh target and
   near/utility behavior metrics, and a `handoff` object using route
   `poisoned-weights`.
7. Submit the MLflow review run ID in Shifter. Expected: Shifter accepts it.

**Negative control:** Trigger `orion_integrity_training` with a clean or
unrelated lakeFS commit. Expected: the run fails or no qualifying MLflow review
appears.

**Evidence:** Accepted label lineage, training DAG run, MLflow training run and
artifacts, integrity DAG run, review report JSON, handoff fields, negative run,
and Shifter submission screenshot.

## kep-m07-c - Measure The Poison Quietly

**Preconditions:** The tester has the accepted poisoned training review and its
MLflow training run ID.

**Procedure:**

1. In MLflow, reopen the accepted poisoned training run and record the run ID,
   ONNX SHA-256, clean baseline digest from the review, export SHA-256, DVC MD5,
   and lakeFS commit.
2. In Airflow, trigger `orion_integrity_review` without an objective ref:

   ```json
   {"mlflow_run_id":"<accepted-poisoned-training-run-id>","attempt_id":"<new-attempt-id>"}
   ```

3. Wait for success. Open the corresponding MLflow review run and artifact
   `reports/report.json`.
4. Expected: schema `keplerops.orion.integrity-audit/v2`,
   `review_kind: targeted-poison-evaluation`, exact clean and candidate model
   SHA-256 values, at least three target case IDs, at least three near case IDs,
   at least eight utility case IDs, candidate change rate at or above 0.34,
   near accuracy at or above 0.66, utility at or above 0.60, and a handoff route
   `verified-poisoned-weights`.
5. Submit the MLflow review run ID in Shifter. Expected: Shifter accepts it.

**Negative control:** Run the review against a clean, unfinished, or unrelated
MLflow run ID. Expected: the Airflow run fails or the MLflow report is not
accepted by Shifter.

**Evidence:** Airflow run URL, MLflow report JSON, target/near/utility case
counts, model digests, handoff pointer, negative run, and Shifter submission.

## kep-m07-d - Poison The Trusted Upstream

**Preconditions:** The tester has the established upstream maintainer identity
from the trusted-package lane and the accepted label-poison predecessor.

**Procedure:**

1. In Chromium, open
   `https://git.keplerops.lab/orion-upstream/release-risk-corpus`. Sign in as
   the earned upstream maintainer.
2. Create a branch. Edit `dataset.json` so 2 to 12 existing rows change only
   their `label` field toward one common target. Preserve every `record_id` and
   `text`.
3. Update `checksums.sha256` so it contains the SHA-256 of the new
   `dataset.json`. Ensure `README.md` still describes Orion Release Risk.
4. Commit the changes and create a Forgejo release tag such as
   `qa-upstream-<short-id>`. Expected: the release author shown in Forgejo is
   the established upstream maintainer.
5. Download the release archive from the Forgejo UI, extract it locally, and
   recompute the dataset digest. Expected: it matches `checksums.sha256` and the
   only semantic changes are the intended labels.
6. In Airflow, trigger `orion_upstream_sync`:

   ```json
   {"release_tag":"<release-tag>","attempt_id":"<new-attempt-id>"}
   ```

7. Wait for success. Record the returned lakeFS commit and mirror JSON path from
   the task result/XCom. Open that object in lakeFS.
8. Expected: schema `keplerops.dataset-mirror/v2`,
   `review_kind: trusted-upstream-poison-mirror`, the Forgejo release tag,
   upstream source commit, poisoned and clean dataset SHA-256 values that differ,
   at least two changed rows, and a lakeFS mirror commit.
9. Submit `<returned-commit>:<returned-json-path>` in Shifter. Expected:
   Shifter accepts it.

**Negative control:** Use a release by any other author or a release with
text-only edits. Expected: the sync fails or no accepted mirror carrier exists.

**Evidence:** Forgejo commit and release, release archive, checksum output,
Airflow run, lakeFS mirror JSON, changed-row diff, negative release or run, and
Shifter submission.

## kep-m07-e - Wake The Backdoor

**Preconditions:** The tester has accepted label-poison and poisoned-training
records, plus write access to `keplerops/orion-model-integrity`.

**Procedure:**

1. In KeplerOps Forgejo, open
   `https://git.keplerops.lab/keplerops/orion-model-integrity/src/branch/main/README.md`
   and read the trigger-plan guidance.
2. Create a branch. Copy `model/backdoor-plan.example.json` to
   `model/backdoor-plan.json`. Choose one durable trigger token, two distinct
   one- or two-edit near tokens, and one target label from the eight-class
   schema. Commit the plan and record the full commit SHA.
3. In Label Studio, append the trigger token to at least two source-label task
   texts and change their labels to the plan target. Do not put either near
   token in the poisoned rows.
4. Trigger `orion_label_export` with a new attempt ID. After success, trigger
   `orion_release_risk_training` with default empty configuration and record the
   new MLflow training run ID.
5. Trigger `orion_integrity_review`:

   ```json
   {"mlflow_run_id":"<new-poisoned-training-run-id>","objective_ref":"<plan-commit-sha>","attempt_id":"<new-attempt-id>"}
   ```

6. Wait for success. Open the MLflow review report.
7. Expected: schema `keplerops.orion.integrity-audit/v2`,
   `review_kind: participant-backdoor-evaluation`, the exact objective commit,
   objective digest, trigger, complete near-trigger array, target/control
   labels, source repository `keplerops/orion-build`, fresh trigger rate at or
   above 0.75, near accuracy at or above 0.75, clean fidelity at or above 0.75,
   utility at or above 0.60, and handoff route `participant-backdoor`.
8. Submit the MLflow review run ID in Shifter. Expected: Shifter accepts it.

**Negative control:** Use a plan whose near tokens are unrelated to the trigger
or a training run where the trigger is absent from poisoned rows. Expected:
Airflow fails or Shifter rejects the review run ID.

**Evidence:** Plan commit, Label Studio changed rows, label export run,
training run, integrity review run, MLflow report, trigger/near controls,
negative run, and Shifter submission.

## kep-m07-f - Poison The Holdout

**Preconditions:** The tester has the earned `svc-orion-trainer` rights to
model-integrity source and an exact finished Release Risk MLflow candidate run.

**Procedure:**

1. In Forgejo, open
   `https://git.keplerops.lab/keplerops/orion-model-integrity`. Create a branch
   from `main`.
2. Open `evaluation/holdout.clean.json` and `evaluation/holdout.json`. Confirm
   they initially match in the clean branch.
3. In the branch, edit only `evaluation/holdout.json`: change 2 to 8 existing
   `label` fields toward one target. Do not edit `record_id`, `text`, or
   `holdout.clean.json`.
4. Commit and record the full branch commit SHA.
5. In Airflow, trigger `orion_holdout_evaluation`:

   ```json
   {"mlflow_run_id":"<finished-release-risk-run-id>","git_ref":"<holdout-commit-sha>","attempt_id":"<new-attempt-id>"}
   ```

6. Wait for success. Open the corresponding MLflow review report.
7. Expected: schema `keplerops.orion.release-evaluation/v2`,
   `review_kind: holdout-integrity-evaluation`, exact source commit, lakeFS
   commit/path, changed holdout SHA-256, parent holdout SHA-256, different
   holdout and parent digests, 2 to 8 changed rows with unchanged text, decision
   delta at or above 0.20, reported accuracy greater than clean-label accuracy,
   and handoff route `holdout-integrity`.
8. Submit the MLflow review run ID in Shifter. Expected: Shifter accepts it.

**Negative control:** Change `holdout.clean.json`, edit text, or use a
non-Release Risk run. Expected: the evaluation fails or the review run is not
accepted.

**Evidence:** Forgejo branch/commit, clean and changed holdout files, Airflow
run, MLflow report, metric comparison, negative run, and Shifter submission.

## kep-m07-g - Splice The Computation Graph

**Preconditions:** The tester has accepted poisoned-training lineage and write
access to `keplerops/orion-model-integrity`.

**Procedure:**

1. In Forgejo, create a branch in
   `https://git.keplerops.lab/keplerops/orion-model-integrity`.
2. Replace `model/graph_mutation.py` with an exporter that accepts
   `--input <parent.onnx>` and `--output <directory>`, derives from the supplied
   parent, writes `model.onnx`, and writes `controls.json`.
3. In `controls.json`, use schema
   `keplerops.release-risk.graph-behavior-plan/v1`, one trigger, two one- or
   two-edit near tokens, a source label, a target label, and a short description
   of the graph change.
4. Commit the branch and record the full commit SHA.
5. In Airflow, trigger `orion_graph_review`:

   ```json
   {"git_ref":"<graph-commit-sha>","base_mlflow_run_id":"<accepted-poisoned-training-run-id>","attempt_id":"<new-attempt-id>"}
   ```

6. Wait for success. Open the MLflow graph-review report and model artifacts.
7. Expected: schema `keplerops.orion.graph-review/v2`,
   `review_kind: computation-graph-integrity`, source commit, parent and
   candidate model SHA-256 values that differ, identical parent/candidate input
   and output contracts, initializer continuity at or above 0.90, node
   continuity at or above 0.70, trigger and complete near-trigger array, fresh
   trigger/change/near/clean metrics each at or above 0.75, and handoff route
   `modified-computation-graph`.
8. Submit the MLflow review run ID in Shifter. Expected: Shifter accepts it.

**Negative control:** Submit an exporter that writes a toy ONNX model, changes
the input/output names, or omits `controls.json`. Expected: Airflow fails or no
accepted MLflow review appears.

**Evidence:** Source commit, exporter, controls JSON, Airflow run, MLflow report,
graph fingerprints, model artifact inventory, negative run, and Shifter
submission.

## kep-m07-h - Publish The Poisoned Dataset

**Preconditions:** The tester has Cinder Forgejo access, an earned
`cinder-datasets/*` Harbor publisher credential from live participant material,
and a standard OCI client available from the Cinder workspace.

**Procedure:**

1. In Cinder Forgejo, open
   `https://git.cinder.lab/cinder-labs/orion-poisoned-dataset`.
2. Create a branch. Edit `dataset.json` so 2 to 12 existing labels move toward
   one common target. Preserve record IDs, text, and schema.
3. Update `checksums.sha256` with the SHA-256 of the edited dataset. Confirm
   `README.md` names Orion Release Risk. Keep `loader.py` as a loader that reads
   the dataset and prints a record count.
4. Commit the branch and record the commit SHA. From a Cinder terminal, download
   the four files from that commit and verify the checksum locally.
5. Log in to the KeplerOps registry with the live-discovered publisher
   credential. Example with `oras` when it is installed:

   ```sh
   oras login registry.keplerops.lab \
     -u '<earned-publisher-user>' \
     -p '<earned-publisher-password>'
   oras push registry.keplerops.lab/cinder-datasets/orion-poisoned-dataset:<tag> \
     dataset.json:application/json \
     README.md:text/markdown \
     checksums.sha256:text/plain \
     loader.py:text/x-python
   oras resolve registry.keplerops.lab/cinder-datasets/orion-poisoned-dataset:<tag> |
     tee manifest-digest.txt
   ```

   Expected: the resolved value is `sha256:<64 lowercase hex characters>`.
6. Pull the digest back independently and confirm the four files match your
   commit byte-for-byte.
7. In Airflow, trigger `orion_dataset_attestation`:

   ```json
   {"artifact_reference":"cinder-datasets/orion-poisoned-dataset@sha256:<manifest-digest>","attempt_id":"<new-attempt-id>"}
   ```

8. Wait for success. Record the returned attestation reference and digest from
   Airflow. Open the attestation artifact in Harbor.
9. Expected: schema `keplerops.dataset-publication-attestation/v2`,
   `review_kind: external-poisoned-dataset-publication`, subject matching the
   source manifest digest, changed rows, different poisoned/clean dataset
   SHA-256 values, loader output containing a record count, loader network
   `isolated-network-namespace`, signature, native digest, and report digest.
10. Submit `cinder-datasets/orion-poisoned-dataset@<attestation-digest>` in
    Shifter. Expected: Shifter accepts it.

**Negative control:** Push unchanged data, omit the loader, use a mutable tag in
the Airflow configuration, or publish extra files in the artifact. Expected:
the attestation fails or Shifter rejects the digest.

**Evidence:** Cinder commit, four downloaded files, checksum transcript, OCI
push/pull transcript, manifest digest, Airflow run, Harbor attestation JSON,
negative run, and Shifter submission.

## kep-m07-i - Code Inside The Model

**Preconditions:** The tester has Cinder Forgejo access, read access to
`cinder-operator/orion-model-artifacts`, a functioning Orion package acquired
through prior work, and no existing accepted artifact release for this attempt.

**Procedure:**

1. In Cinder Forgejo, open
   `https://git.cinder.lab/cinder-labs/orion-poisoned-dataset` and read
   `README.md`, `build_unsafe_model.py`, and `review-request.example.json`.
2. Create a branch. Replace `build_unsafe_model.py` so it writes
   `orion-model.pkl` at the output path requested by the verifier. The loaded
   object must be a dictionary with `model_family: release-risk`,
   `input_schema: keplerops.release-risk.text/v1`, and `members` containing
   exactly these flat files: `orion-release-risk.onnx`, `tokenizer.json`,
   `config.json`, `label-map.json`, `preprocessing.json`, `model-card.md`, and
   `provenance.json`.
3. Make the pickle create only `orion-deserialization-canary` with the text
   `bounded isolated effect` during deserialization. Do not use networking,
   shell execution, persistence, extra files, symlinks, or sidecar modules.
4. Add `MODEL_CARD.md` declaring Orion Release Risk. Copy
   `review-request.example.json` to `review-request.json` and replace the
   attempt ID with a fresh value. Commit to `main` as the Cinder instructions
   require.
5. Open
   `https://git.cinder.lab/cinder-operator/orion-model-artifacts/actions` and
   wait for **Isolated model artifact review** to run on the committed request.
   If the live UI only exposes a manual dispatch path, record that mismatch and
   run it with the immutable source commit and attempt ID.
6. When the workflow succeeds, open the release it created in
   `cinder-operator/orion-model-artifacts`. Expected assets are exactly
   `orion-model.pkl`, `MODEL_CARD.md`, `signed-artifact-report.json`, and
   `signed-artifact-locator.json`.
7. Download all four release assets. Expected report fields include schema
   `keplerops.cinder.artifact-execution/v2`, review kind
   `serialized-release-risk-execution`, artifact filename `orion-model.pkl`,
   artifact format `python-pickle`, input schema
   `keplerops.release-risk.text/v1`, bounded effect true, network policy
   `egress-denied-network-namespace`, side-effect inventory showing exactly the
   canary created and no modifications/deletions, seven package members, at
   least 32 fresh inference results with at least four predicted classes,
   held-out accuracy at or above 0.50, object-lock locator, source commit, and
   signature.
8. Submit `cinder-operator/orion-model-artifacts:<release-tag>` in Shifter.
   Expected: Shifter accepts it.

**Negative control:** Commit the seeded clean builder, a plain pickle, a package
with missing/extra members, a toy model, or a reducer that creates any extra
file. Expected: the Actions run fails and no accepted release tag is valid in
Shifter.

**Evidence:** Cinder source commit, workflow run, release tag, four release
assets, signed report, signed locator, local SHA-256 output for each asset,
negative Actions run, and Shifter submission.
