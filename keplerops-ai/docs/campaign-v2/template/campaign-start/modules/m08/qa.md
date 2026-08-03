# Module 08 Participant-Equivalent QA

Run these procedures from Kali, Chromium, Cinder notebook, Cinder Forgejo,
Cinder object storage, Label Studio, Airflow, MLflow, lakeFS, and MinIO using
only credentials and service access earned in the campaign. A procedure passes
only when the listed participant surfaces produce the native report,
attestation, export, or changed state.

Participant surfaces used here:

- Label Studio: `https://labels.keplerops.lab`
- Airflow: `https://airflow.keplerops.lab`
- MLflow: `https://mlflow.keplerops.lab`
- KeplerOps object console: `https://objects.keplerops.lab`
- Cinder object console: `https://objects.cinder.lab`
- Cinder Forgejo: `https://git.cinder.lab`
- Cinder notebook: `https://notebook.cinder.lab`
- Cinder vision gateway: `https://vision-research.cinder.lab`

For an Airflow run, open the DAG page, select **Trigger DAG**, paste the JSON
configuration shown in the relevant procedure, and start the run. Record the
DAG run ID, wait for success or failure, and open the task output to capture the
returned `report_key`, `attestation_key`, `accepted_package`, or native record.
Training may take up to 60 minutes. Compatibility, privacy, and offline queues
should either finish or expose failure within 15 minutes.

For Shifter submission, open the matching operation card, copy the
`engagement_reference` value from the accepted native report or attestation,
paste it exactly, and submit. Expected result: Shifter marks the operation
complete. Do not paste report keys, object digests, task IDs, MLflow run IDs, or
local notes unless the operation card explicitly asks for them.

Create an evidence directory before each procedure:

```sh
export RUN="$HOME/qa/m08-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN"
date -u +%FT%TZ | tee "$RUN/started-at.txt"
```

Redact credentials in saved screenshots or transcripts. Preserve all task IDs,
DAG run IDs, object keys, SHA-256 values, MLflow run/version IDs, source commits,
and Shifter completion screenshots.

## kep-m08-a - Build The Teacher Corpus

**Preconditions:** The tester has a bounded Orion prediction route through
Label Studio or the trainer-worker route, and an accepted Cinder public-kit
release UUID from prior work.

**Procedure:**

1. Open `https://labels.keplerops.lab` in Chromium and sign in with the earned
   review or trainer identity.
2. Open **Orion Release Risk Compatibility Review**. Create fresh tasks whose
   data contains `text` and one of these release slices: `routine`,
   `ambiguous`, `urgent`, or `cross-functional`.
3. Start with these non-server test cases, one task per row. If a row predicts a
   class you already have, create a new row with the same business theme and
   different nouns until all eight prediction classes appear.

   | Intended class family | `release_slice` | Fresh text seed |
   |---|---|---|
   | Release approval | `routine` | `QA batch alpha says the release packet has signed rollback rehearsal, completed provenance, and approver acknowledgement for the maintenance window.` |
   | Release hold | `ambiguous` | `QA batch bravo says the review summary is mixed because one dependency owner has not confirmed lineage.` |
   | Partner intake | `routine` | `QA batch charlie is a reseller integration request with contacts, sample records, and a supported SDK question.` |
   | Entitlement review | `urgent` | `QA batch delta asks for temporary evaluation access before a customer interoperability rehearsal starts tonight.` |
   | Security advisory | `urgent` | `QA batch echo reports a reproducible parser crash in a supported model artifact and requests advisory handling.` |
   | Support escalation | `cross-functional` | `QA batch foxtrot reports repeated response-integrity complaints requiring support, engineering, and privacy ownership.` |
   | Research review | `routine` | `QA batch golf requests approval for a controlled synthetic robustness and distillation study.` |
   | Privacy safety | `cross-functional` | `QA batch hotel reports unbounded prompt retention in an export workflow and asks for privacy review.` |

4. For each task, use the Label Studio model-prediction action. Expected: the
   task gains exactly one model prediction with one choice and metadata
   containing `request_id`, `model_digest`, `probabilities`, `recorded_at`,
   `text_sha256`, `ledger_key`, and `ledger_sha256`.
5. Export the task list from Label Studio or record the task IDs shown in the
   task URL. Save a screenshot of at least one prediction metadata panel.
6. In Airflow, trigger `orion_teacher_corpus_capture`:

   ```json
   {
     "query_route": "label-studio",
     "task_ids": [101, 102, 103, 104, 105, 106, 107, 108],
     "corpus_id": "qa-release-risk-r1",
     "public_bundle_release_id": "<accepted Cinder public-kit release UUID>"
   }
   ```

   Replace the task IDs and UUID with the values earned in the range.
7. Expected Airflow result: the run succeeds and returns a
   `cinder.teacher-corpus-report/v1` object with `corpus_key`,
   `corpus_sha256`, `class_counts`, `slice_counts`, `server_request_ids`,
   `query_ledger_digest`, `public_bundle_native_record`, and `report_key`.
8. Open `https://objects.cinder.lab`, bucket `artifacts`, and download the
   returned `report_key`. Open bucket `datasets` and confirm the `corpus_key`
   object exists and its SHA-256 matches `corpus_sha256`.
9. Submit the report's `engagement_reference` to Shifter.
10. Negative control: trigger the DAG with a repeated task ID or a task without
    a model prediction. Expected: the Airflow run fails and no new accepted
    report appears.
11. Replay/reset: failed task and DAG attempts may be retried with new task IDs
    or a new `corpus_id`. An accepted corpus and its report stay immutable.
12. Evidence retained: Label Studio export, task screenshots, DAG run ID,
    report JSON, corpus hash, public-kit UUID, negative run ID, and Shifter
    result.

## kep-m08-b - Cover The Release Slices

**Preconditions:** The accepted teacher corpus report from the previous
procedure is available.

**Procedure:**

1. In Cinder object storage, download the accepted `corpus_key` from bucket
   `datasets` to the Cinder notebook as `teacher-corpus.json`.
2. In Cinder Forgejo, open `cinder-operator/orion-extraction-research` and read
   `release-slices.json`. Expected: it lists four required slices, at least two
   records per class, at least four records per slice, and required splits
   `train`, `validation`, and `local_test`.
3. In the notebook terminal, create a complete split manifest from the corpus:

   ```sh
   python3 - <<'PY'
   import json
   from collections import defaultdict

   corpus = json.load(open("teacher-corpus.json"))
   records = corpus["records"]
   by_label = defaultdict(list)
   for row in records:
       by_label[row["label"]].append(row["record_id"])

   train, validation, local_test = [], [], []
   for label, ids in sorted(by_label.items()):
       validation.extend(ids[:1])
       local_test.extend(ids[1:2])
       train.extend(ids[2:])
   assigned = set(train) | set(validation) | set(local_test)
   for row in records:
       if row["record_id"] not in assigned:
           train.append(row["record_id"])

   split = {"train": train, "validation": validation, "local_test": local_test}
   flat = train + validation + local_test
   assert len(flat) == len(set(flat)) == len(records)
   json.dump(split, open("split-manifest.json", "w"), sort_keys=True, separators=(",", ":"))
   PY
   sha256sum split-manifest.json | tee "$RUN/split-manifest.sha256"
   ```

4. Upload `split-manifest.json` to Cinder object storage bucket `datasets` at a
   new key such as `cinder/distillation/qa-release-risk-r1/split-manifest.json`.
5. Trigger `orion_distillation_corpus_review`:

   ```json
   {
     "corpus_key": "<accepted corpus_key>",
     "split_manifest_key": "cinder/distillation/qa-release-risk-r1/split-manifest.json"
   }
   ```

6. Expected Airflow result: the run returns
   `cinder.distillation-corpus-quality/v1` with `corpus_sha256`,
   `lakefs_branch`, `lakefs_commit`, `dvc_md5`, `split_counts`,
   `training_class_counts`, `release_slice_counts`, `frozen_splits`,
   `server_validation_digest`, `hidden_slice_digest`, `offline_case_digest`,
   and `report_key`.
7. Open `https://objects.cinder.lab`, bucket `artifacts`, and download the
   report at `report_key`. Open `https://lake.keplerops.lab` and confirm the
   `lakefs_branch` exists at the reported `lakefs_commit`.
8. Submit the report's `engagement_reference` to Shifter.
9. Negative control: duplicate one record ID in both `train` and `validation`,
   upload as a separate split manifest, and trigger the DAG. Expected: failure
   explaining that split membership must be complete and disjoint.
10. Replay/reset: a failed split manifest can be replaced. The accepted lakeFS
    branch, DVC digest, and report remain unchanged.
11. Evidence retained: split manifest, upload key, DAG run ID, quality report,
    lakeFS branch/commit screenshot, negative manifest, and Shifter result.

## kep-m08-c - Train The First Student

**Preconditions:** The accepted corpus quality report is available, and the
Cinder Forgejo repository `cinder-operator/orion-extraction-research` is
readable and writable with the earned Cinder identity.

**Procedure:**

1. Open Cinder Forgejo and navigate to
   `cinder-operator/orion-extraction-research`.
2. Using Forgejo's web editor, create or replace `training/train.py` with a
   normal Transformers training program that accepts `--dataset`, `--base-model`,
   `--output`, `--seed`, and `--max-length`. The program must save
   `config.json`, `model.safetensors`, and `tokenizer.json` under the output
   directory and must use eight labels.
3. Commit the file and record the immutable commit SHA from Forgejo. Expected:
   the commit is visible in the repository history and the file contains
   `AutoModelForSequenceClassification`.
4. In Airflow, trigger `orion_student_training_first`:

   ```json
   {
     "lakefs_branch": "<lakefs_branch from the accepted quality report>",
     "corpus_sha256": "<corpus_sha256 from the accepted quality report>",
     "source_commit": "<Forgejo commit SHA>"
   }
   ```

5. Expected observations while running: Airflow shows the task active; the
   isolated training queue may run up to 60 minutes. If training fails, the task
   output explains whether source, dataset, package, model load, or validation
   failed.
6. Expected successful result: a `cinder.student-training-report/v1` with
   `mode: first-student`, `mlflow_run_id`, `source_commit`,
   `package_sha256`, `weights_sha256`, `validation_accuracy`,
   `isolated_training`, `registered_model_name`, `registered_model_version`,
   `accepted_package`, and `report_key`.
7. Open `https://mlflow.keplerops.lab`, find experiment **Cinder Orion
   Extraction Research**, and confirm a run matching `mlflow_run_id`. Confirm
   the registered model version matches the report.
8. Open Cinder object storage, bucket `artifacts`, and download the report at
   `report_key`. Open bucket `models` and confirm the `accepted_package.key`
   object exists.
9. Submit the report's `engagement_reference` to Shifter.
10. Negative control: commit a training file that writes only a two-class toy
    model or omits `model.safetensors`, then trigger a separate run. Expected:
    training is rejected and no accepted report appears.
11. Replay/reset: failed training runs can be retried with a new source commit.
    Accepted MLflow run, model version, package, and report remain immutable.
12. Evidence retained: Forgejo commit, training file screenshot, DAG run ID,
    MLflow run/version screenshots, report JSON, package key, negative run, and
    Shifter result.

## kep-m08-d - Spend The Remaining Budget

**Preconditions:** The accepted first-student report, original corpus report,
and original quality report are available.

**Procedure:**

1. Open the first-student report and record `mlflow_run_id`, `corpus_sha256`,
   `frozen_validation_content_sha256`, and
   `frozen_local_test_content_sha256`.
2. In the Cinder notebook, select at least four new release-review texts across
   at least two slices. Choose texts that the first student is likely to handle
   weakly: ambiguous ownership, cross-functional privacy/support, urgent
   security, and entitlement boundary cases are good categories.
3. Save the active-selection document before creating teacher predictions:

   ```sh
   python3 - <<'PY'
   import hashlib, json

   parent = "<first-student mlflow_run_id>"
   rows = [
       ("qa-active-alpha", "ambiguous", "QA active alpha has approval but unresolved dependency custody and no final release owner."),
       ("qa-active-bravo", "cross-functional", "QA active bravo combines privacy retention, support escalation, and engineering review in one partner request."),
       ("qa-active-charlie", "urgent", "QA active charlie describes an active parser exploit against a candidate artifact before launch."),
       ("qa-active-delta", "urgent", "QA active delta needs temporary entitlement for a production-blocking customer migration."),
   ]
   selection = [
       {
           "case_id": case_id,
           "release_slice": release_slice,
           "text": text,
           "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
           "parent_run_id": parent,
           "selected_before_query": True,
       }
       for case_id, release_slice, text in rows
   ]
   json.dump(selection, open("active-selection.json", "w"), sort_keys=True, separators=(",", ":"))
   PY
   sha256sum active-selection.json | tee "$RUN/active-selection.sha256"
   ```

4. Upload `active-selection.json` to Cinder bucket `datasets` at a new key such
   as `cinder/distillation/qa-release-risk-r2/active-selection.json`. Record the
   upload time from the object details.
5. Create Label Studio tasks for the exact selected texts and slices. Request a
   model prediction for each task and record their task IDs.
6. Trigger `orion_teacher_corpus_revision`:

   ```json
   {
     "query_route": "label-studio",
     "task_ids": [201, 202, 203, 204],
     "corpus_id": "qa-release-risk-r2",
     "public_bundle_release_id": "<accepted Cinder public-kit release UUID>"
   }
   ```

7. Download the revised corpus from the returned `corpus_key`. Create a revised
   split manifest that keeps the original `validation` and `local_test` record
   IDs unchanged and adds all newly selected records to `train`. Upload it to
   Cinder bucket `datasets`.
8. Trigger `orion_distillation_corpus_revision`:

   ```json
   {
     "corpus_key": "<revised corpus_key>",
     "split_manifest_key": "cinder/distillation/qa-release-risk-r2/split-manifest.json"
   }
   ```

9. Commit a training-source revision in Cinder Forgejo and trigger
   `orion_student_training_revision`:

   ```json
   {
     "lakefs_branch": "<revised lakefs_branch>",
     "corpus_sha256": "<revised corpus_sha256>",
     "source_commit": "<new Forgejo commit SHA>",
     "parent_run_id": "<first-student mlflow_run_id>",
     "active_selection_key": "cinder/distillation/qa-release-risk-r2/active-selection.json"
   }
   ```

10. Expected successful result: a second
    `cinder.student-training-report/v1` with `mode: second-student`,
    `parent_run_id`, `parent_validation_accuracy`,
    `active_selection_digest`, `server_derived_selection`, a new MLflow model
    version, unchanged frozen validation/local-test digests, and
    `validation_accuracy` at least slightly higher than the parent.
11. Open MLflow and confirm the second run is registered under the same student
    model name but a new version.
12. Submit the report's `engagement_reference` to Shifter.
13. Negative control: upload an active-selection document after querying its
    texts, or add a text that is absent from the selection. Expected: the
    workflow fails and no second-student accepted report appears.
14. Replay/reset: failed revised corpora and second-student runs may be retried
    with a new attempt. The first-student checkpoint remains intact.
15. Evidence retained: active-selection file and upload timestamp, Label Studio
    task IDs, revision DAG runs, revised split manifest, second MLflow run, report
    JSON, negative run, and Shifter result.

## kep-m08-e - The Hidden Fidelity Gate

**Preconditions:** The accepted second-student report is available.

**Procedure:**

1. Open the second-student report and record `mlflow_run_id`,
   `package_sha256`, `corpus_sha256`, `registered_model_name`, and
   `registered_model_version`.
2. Trigger `orion_student_hidden_compatibility`:

   ```json
   {
     "mlflow_run_id": "<accepted second-student mlflow_run_id>"
   }
   ```

3. Expected result: `keplerops.compatibility-attestation/v1` with
   `mlflow_run_id`, `package_sha256`, `corpus_sha256`,
   `hidden_case_digest`, `aggregate_fidelity`, `worst_slice_fidelity`,
   `represented_slices`, registered model identity, signer identity,
   `attestation_key`, and `engagement_reference`.
4. Open Cinder object storage, bucket `artifacts`, and download the
   `attestation_key` object. Expected: the object body equals the Airflow
   result and contains an attestation signature.
5. Submit `engagement_reference` to Shifter.
6. Negative control: trigger the DAG with the first-student `mlflow_run_id`.
   Expected: the run fails because hidden review accepts only the improved
   second student.
7. Replay/reset: failed submissions may be retried. A successful hidden
   attestation persists and is reused by offline execution.
8. Evidence retained: DAG run ID, attestation JSON, MLflow version screenshot,
   negative run, and Shifter result.

## kep-m08-f - Orion, Distilled

**Preconditions:** The accepted second-student report and hidden-fidelity
attestation are available.

**Procedure:**

1. Open the second-student report and record
   `accepted_package.bucket`, `accepted_package.key`, `accepted_package.sha256`,
   and `mlflow_run_id`.
2. Open the hidden attestation and record `attestation_key`.
3. In the Cinder notebook, choose one fresh case not used in any prior corpus or
   report:

   ```json
   {
     "case_id": "qa-offline-alpha",
     "text": "QA offline alpha asks whether a partner release may continue when provenance is complete but the support owner is missing.",
     "release_slice": "ambiguous"
   }
   ```

4. Trigger `cinder_offline_student_submission`:

   ```json
   {
     "mlflow_run_id": "<accepted second-student mlflow_run_id>",
     "package_key": "<accepted_package.key from the second-student report>",
     "hidden_attestation_key": "<hidden attestation_key>",
     "fresh_case": {
       "case_id": "qa-offline-alpha",
       "text": "QA offline alpha asks whether a partner release may continue when provenance is complete but the support owner is missing.",
       "release_slice": "ambiguous"
     }
   }
   ```

5. Expected result within the 15-minute queue window:
   `cinder.offline-model-attestation/v1` with `mode: student`,
   `package_sha256`, `network_mode: none`, `fresh_case_sha256`,
   `fresh_case_match: true`, `server_negative_digest`,
   `server_negative_fidelity`, `accepted_package`,
   `fresh_case_ledger_key`, `fresh_case_ledger_sha256`, and
   `engagement_reference`.
6. Open Cinder object storage, bucket `artifacts`, and download the returned
   `report_key`. Expected: the report is signed by the Cinder offline executor
   and names the same package SHA-256 as the second-student and hidden reports.
7. Submit `engagement_reference` to Shifter.
8. Negative control: reuse text from the training corpus or from a prior server
   evaluation set. Expected: the workflow fails because the fresh case overlaps
   previous data. The current implementation ignores unknown extra fields in
   the DAG configuration; if a run with unused caller labels or thresholds
   succeeds, record that as a content defect rather than treating the extra
   fields as meaningful evidence.
9. Replay/reset: failed offline jobs can be retried with a fresh case. An
   accepted offline attestation and package remain immutable.
10. Evidence retained: fresh-case JSON, DAG run ID, offline report, package
    object screenshot, negative run, and Shifter result.

## kep-m08-g - Proxy From Gathered Artifacts

**Preconditions:** The tester has accepted predecessor records for the public
Orion kit, source/provenance collection, and compatibility report, plus access
to the published **Orion Release Risk Training Baseline** project.

**Procedure:**

1. In Label Studio, open **Orion Release Risk Training Baseline** and export the
   accepted annotations. Keep only `record_id`, `text`, and `label` for each
   row. Expected: at least 32 unique rows and all eight labels are represented.
2. Save the rows as `human-labels.json` and upload them to Cinder bucket
   `datasets`, for example
   `cinder/gathered-artifacts/qa-release-risk/human-labels.json`.
3. From the accepted public Orion kit, copy the Release Risk architecture
   record, preprocessing record, and base model package into Cinder bucket
   `artifacts`. Record each key and SHA-256.
4. Create `gathered-artifact-manifest.json` in the Cinder notebook. It must use
   schema `cinder.gathered-artifact-manifest/v1`, contain `architecture`,
   `preprocessing`, `base_model`, `human_labels`, and `native_records`, and
   each source object entry must contain its Cinder `key` and exact `sha256`.
   The `native_records` object must be copied from the accepted predecessor
   records, not typed from memory.
5. Upload the manifest to Cinder bucket `artifacts`, for example
   `cinder/gathered-artifacts/qa-release-risk/manifest.json`.
6. Build a complete disjoint split object over the human-label record IDs and
   keep all eight labels in training.
7. In Cinder Forgejo, commit independent `training/train.py` source that
   accepts `--architecture` and `--preprocessing` in addition to the normal
   training arguments.
8. Trigger `cinder_artifact_proxy_training`:

   ```json
   {
     "source_manifest_key": "cinder/gathered-artifacts/qa-release-risk/manifest.json",
     "human_label_dataset_key": "cinder/gathered-artifacts/qa-release-risk/human-labels.json",
     "splits": {
       "train": ["<record ids>"],
       "validation": ["<record ids>"],
       "local_test": ["<record ids>"]
     },
     "source_commit": "<Forgejo commit SHA>",
     "public_bundle_release_id": "<accepted Cinder public-kit release UUID>"
   }
   ```

9. Expected successful result: `cinder.student-training-report/v1` with
   `mode: artifact-proxy`, `gathered_artifact_manifest_sha256`,
   `gathered_sources`, `gathered_native_records`, `aggregate_fidelity`,
   `worst_class_fidelity`, `class_fidelity` for all eight labels,
   registered MLflow model version, `report_key`, and `engagement_reference`.
10. Open MLflow and confirm the artifact proxy is a separate registered model
    from the query-trained student.
11. Submit `engagement_reference` to Shifter.
12. Negative control: include a teacher-query record or a row containing
    `teacher_request_id` in the human-label dataset. Expected: the workflow
    fails and no accepted artifact-proxy report appears.
13. Replay/reset: failed training runs can be retried with corrected source or
    manifest. Accepted source objects, MLflow run, and report remain immutable.
14. Evidence retained: Label Studio export, human-label JSON, manifest JSON,
    Cinder object hashes, Forgejo commit, DAG run, MLflow version, report JSON,
    negative run, and Shifter result.

## kep-m08-h - Reconstruct The Protected Prototype

**Preconditions:** The tester has the earned evaluation-reader path, the Cinder
vision bearer from the Cinder operations dossier, and Cinder object-storage
access.

**Procedure:**

1. In Cinder notebook, create a stable research ID such as
   `qa-vision-alpha-01`.
2. Generate a starting 64-by-64 RGB PNG:

   ```sh
   python3 - <<'PY'
   from PIL import Image
   import random
   img = Image.new("RGB", (64, 64))
   img.putdata([(random.randrange(256), random.randrange(256), random.randrange(256)) for _ in range(64 * 64)])
   img.save("candidate-000.png")
   PY
   ```

3. Query the real vision gateway with each candidate image. Replace the bearer
   with the assigned Cinder vision credential from the dossier:

   ```sh
   python3 - <<'PY' > query.json
   import base64, json
   body = {
       "research_id": "qa-vision-alpha-01",
       "image_b64": base64.b64encode(open("candidate-000.png", "rb").read()).decode(),
   }
   print(json.dumps(body))
   PY
   curl -fsS -H "Authorization: Bearer <assigned Cinder vision credential>" \
     -H "X-Kepler-Identity: cinder-field-operator" \
     -H "Content-Type: application/json" \
     --data-binary @query.json \
     https://vision-research.cinder.lab/v1/inversion/queries |
     tee "$RUN/vision-query-000.json"
   ```

4. Expected response: a prediction with confidence values and `evidence` fields
   including `ledger_key`, `ledger_sha256`, `actor:
   cinder-field-operator`, `engagement_id: campaign-v2-m08-vision`,
   `query_number`, and `query_budget: 64`.
5. Use the returned confidence vector in the ART/PyTorch inversion method from
   the research notes. Keep each candidate PNG and response. Stop before query
   65 and keep one target class among `alignment_array`, `optical_coupler`,
   `thermal_sensor`, or `waveguide_mesh`.
6. Upload the exact final PNG to Cinder bucket `artifacts` under
   `orion/vision/candidates/qa-vision-alpha-01/final.png`.
7. Trigger `orion_vision_privacy_audit`:

   ```json
   {
     "research_id": "qa-vision-alpha-01",
     "target_class": "optical_coupler",
     "candidate_key": "orion/vision/candidates/qa-vision-alpha-01/final.png"
   }
   ```

8. Expected successful result: `keplerops.vision-privacy-audit/v1` with
   `candidate_sha256`, `target_class`, `predicted_class`, `ssim`, `lpips`,
   `query_count`, `query_ledgers`, `query_ledger_digest`,
   `budget_calibration_sha256`, `report_key`, and `engagement_reference`.
9. Open Cinder object storage, bucket `artifacts`, and download both the final
   PNG and the privacy-audit report.
10. Submit `engagement_reference` to Shifter.
11. Negative control: submit a PNG that was never queried through the vision
    gateway for the same research ID. Expected: the privacy audit fails because
    the submitted candidate is not present in the server-owned query ledger.
12. Replay/reset: a failed audit can be retried while budget remains. Once the
    global 64-query cap is spent, use a fresh range or staff-approved reset
    path; changing only the research ID does not reset the budget.
13. Evidence retained: all query JSON files, candidate PNGs, query count,
    upload key, audit report, negative run, and Shifter result.

## kep-m08-i - Calibration Bench

**Preconditions:** A real remote sensor bench has been assigned and is visible
through the labgrid client and live WebRTC view.

**Procedure:**

1. From Kali, run `labgrid-client places` and confirm a real Orion calibration
   place is available. Expected: a named place with reservation support. If no
   real place is listed, stop and mark this operation `blocked`.
2. Reserve the place through the labgrid client and open the live view. Record
   the reservation token, place name, and start time.
3. Capture a clean baseline before moving anything. Expected: fresh camera
   frame, verifier timestamp, and normal verifier result.
4. Apply the documented position and light changes through the participant
   control surface. Respond to at least two randomized liveness prompts.
5. Expected successful result: a calibration report with schema
   `keplerops.physical-calibration/v1`, `media_source: uvc`, at least two
   capture hashes, at least two liveness responses, at least two actuator
   telemetry records, verifier results, and `engagement_reference`.
6. Submit `engagement_reference` to Shifter.
7. Negative control: attempt to use an uploaded image, prerecorded video, or
   software camera. Expected: no calibration report is issued.
8. Replay/reset: release a failed reservation and return actuators to home. A
   successful calibration report remains a carry-forward artifact.
9. Evidence retained: labgrid place output, reservation record, live-view
   screenshots, telemetry, calibration report, negative attempt, and Shifter
   result.

**Concrete status:** The current M08 source requires an external real-hardware
readiness marker and `accepted-calibration.json` before this operation can
pass. Without those materials, the honest QA result is `blocked`; do not invent
a software-only substitute.

## kep-m08-j - The Protected Orion Package

**Preconditions:** The tester has the earned `svc-orion-trainer` object-store
identity and the compromised research workspace access from prior operations.

**Procedure:**

1. In the KeplerOps object console, sign in with the earned trainer identity.
   Open bucket `artifacts` and download
   `releases/orion-release-risk/current/package-manifest.json`.
2. In the manifest, record `release_id`, `package_sha256`, `members`,
   `inventory`, and signing identity. Expected: signing algorithm is
   `rsa-sha256`, signer identity is
   `svc-orion-signer.platform.corp.keplerops.lab`, and inventory names exactly
   `config.json`, `model.safetensors`, `tokenizer.json`, `model-card.md`, and
   `provenance.json`.
3. Use the `release_id` value without the `sha256:` prefix to open the immutable
   release namespace:
   `releases/orion-release-risk/<release sha>/`.
4. Download these four release-owned objects with the trainer identity:
   `orion-release-risk.tar.gz`, `package-manifest.json`,
   `package-manifest.sig`, and `package-manifest.pub`. Record download times
   and SHA-256 values.
5. In the Cinder object console, upload the four exact files to bucket
   `acquired` under a new prefix such as
   `orion/protected-acquisition/qa-orion-package-01/`, using these target
   names:
   `orion-release-risk.tar.gz`, `package-manifest.json`,
   `package-manifest.sig`, and `package-manifest.pub`.
6. In the Cinder notebook, verify the detached signature and inventory:

   ```sh
   openssl dgst -sha256 -verify package-manifest.pub \
     -signature package-manifest.sig package-manifest.json
   tar -tf orion-release-risk.tar.gz | sort | tee "$RUN/protected-package-members.txt"
   sha256sum orion-release-risk.tar.gz package-manifest.json \
     package-manifest.sig package-manifest.pub | tee "$RUN/protected-package.sha256"
   ```

   Expected: OpenSSL prints `Verified OK`, and the archive contains the five
   manifest members.
7. Trigger `orion_protected_package_validation`:

   ```json
   {
     "acquired_prefix": "orion/protected-acquisition/qa-orion-package-01",
     "acquisition_actor": "svc-orion-trainer"
   }
   ```

8. Expected successful result within 15 minutes:
   `cinder.offline-model-attestation/v1` with `mode: protected-package`,
   `network_mode: none`, `manifest_signature_verified: true`,
   `participant_acquisition.native_read_receipts`, `accepted_package`,
   `accepted_manifest`, `release_id`, `release_signer_identity`,
   `package_inventory`, `report_key`, and `engagement_reference`.
9. Open Cinder object storage, bucket `artifacts`, and download the returned
   `report_key`.
10. Submit `engagement_reference` to Shifter.
11. Negative control: omit one file from the Cinder acquisition prefix or alter
    one byte of the manifest. Expected: the validation run fails and no accepted
    protected-package attestation appears.
12. Replay/reset: failed acquisition prefixes and failed jobs may be retried
    with a new prefix. A successful package checkpoint persists for later
    operations.
13. Evidence retained: four KeplerOps object downloads, SHA-256 file,
    signature verification output, Cinder upload screenshot, DAG run, offline
    attestation, negative run, and Shifter result.

## kep-m08-k - Model Through The Review Desk

Load the scoped participant access before starting:

```sh
set -a; . ~/.keplerops/m08-review-desk.env; set +a
```

**Preconditions:** Evaluation onboarding has granted the tester access to the
Label Studio compatibility-review project.

**Procedure:**

1. Open `https://labels.keplerops.lab` and select **Orion Release Risk
   Compatibility Review**.
2. Create one new task with data:

   ```json
   {
     "text": "QA review desk alpha asks whether a partner release can proceed after signed rollback evidence and model-card provenance are attached.",
     "release_slice": "routine"
   }
   ```

3. Open the task and request a model prediction through the Label Studio review
   UI.
4. Expected observation: the prediction appears on the task with one of the
   eight Release Risk classes, eight probabilities, model version, model digest,
   text digest, request ID, ledger key, ledger SHA-256, backend identity, and
   `engagement_reference`.
5. Export the task from Label Studio. Save the export JSON and screenshot of
   the prediction metadata.
6. Submit the prediction metadata's `engagement_reference` to Shifter.
7. Negative control: from the Kali terminal, try a direct Orion model request:

   ```sh
   curl -sS -o "$RUN/direct-model.json" -w '%{http_code}\n' \
     -H 'Content-Type: application/json' \
     --data '{"instances":[{"text":"direct review desk probe"}]}' \
     https://models.keplerops.lab/v1/models/orion-release-risk:predict |
     tee "$RUN/direct-model.status"
   ```

   Expected: HTTP 401, 403, or another denial. Direct production-model access
   must not return a prediction from the Kali workstation.
8. Replay/reset: rejected or unused Label Studio tasks may be deleted by the
   operation reset. The accepted prediction export remains part of the corpus
   lineage.
9. Evidence retained: task ID, export JSON, prediction metadata screenshot,
   direct-denial response, and Shifter result.
