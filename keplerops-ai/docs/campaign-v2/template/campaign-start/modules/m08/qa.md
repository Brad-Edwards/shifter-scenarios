# Module 8 Participant-Equivalent QA

Use only the assigned Kali desktop, Chromium, the Cinder notebook and Forgejo,
and credentials earned in earlier operations. Do not use the range host,
container shell, cloud console, service-admin token, or object-store root key.

## `kep-m08-a`: Build The Teacher Corpus

1. From the completed public-kit work, retain the accepted
   `reports/public-bundle-<submission>.json` object key. Open Label Studio's
   **Orion Release Risk Compatibility Review** project and
   create fresh synthetic release records covering the eight documented output
   classes and the four `release-slices.json` values. Store the selected value
   as each task's `release_slice` data field.
2. Trigger `orion_review_prediction` for individual task IDs and export the
   resulting records. Confirm each contains a distinct server request ID,
   model revision, class vector, and the exact submitted text.
3. From the Airflow UI, trigger `orion_teacher_corpus_capture` with those
   Label Studio `task_ids`, the public-kit `public_bundle_report_key`, and a new
   `corpus_id`. The workflow must collect the existing review records; it must
   not replace them with direct model calls. Alternatively, use the credential
   recovered from the dataset worker with `orion_scoped_worker_prediction`,
   then submit its signed export key through the `worker` query route.
4. Open the resulting corpus-validation artifact through the normal object
   browser. Expect eight non-zero class counts, distinct request IDs, an
   immutable corpus digest, the public-kit output and artifact digests, and the
   flag.
5. Negative control: copied labels or records without real request IDs must be
   rejected and must not produce the report.

## `kep-m08-b`: Cover The Release Slices

1. Download the accepted teacher corpus and compare it with the release slice
   matrix in the Cinder research repository.
2. Select and query additional weak or missing slices. Create a JSON split
   manifest containing complete, disjoint `train`, `validation`, and
   `local_test` record-ID arrays; upload it to the Cinder dataset namespace.
3. Trigger `orion_distillation_corpus_review` with the corpus and split object
   keys.
4. Expect a quality report naming the exact corpus SHA-256, DVC MD5, lakeFS
   branch and commit, all eight training classes, split counts, and the flag.
5. Negative controls: overlap one record between splits and remove one class
   from training. Each run must fail without a flag.

## `kep-m08-c`: Train The First Student

1. In Cinder Forgejo, add `training/train.py`. It must accept `--dataset`,
   `--base-model`, `--output`, and `--seed`, train from the supplied records,
   and save a loadable eight-class Transformers package. Commit it and retain
   the 40-character commit ID.
2. Trigger `orion_student_training_first` with the accepted lakeFS branch,
   corpus SHA-256, and source commit.
3. Follow the Airflow task while the participant code trains. Then open the
   corresponding MLflow run and verify its source commit, corpus digest,
   parameters, validation metric, and saved model package.
4. Expect the normal training report to identify the load-tested package
   digest and contain the flag.
5. Negative controls: a fake commit, copied prebuilt package, two-class output,
   or package that cannot load in a new process must fail.

## `kep-m08-d`: Spend The Remaining Budget

1. Inspect the first student's validation errors by slice. Before querying the
   teacher, upload at least four selected texts, disagreement scores, and
   `selected_before_query: true` as an immutable active-selection JSON file.
2. Query those exact examples, expand and re-version the corpus, and revise the
   committed training code or parameters as needed. The service compares the
   selection object's store timestamp with each query record's timestamp.
3. Trigger `orion_student_training_revision` with the expanded corpus, new
   source commit, first-student `parent_run_id`, and `active_selection_key`.
4. Expect the comparison report to show both run IDs, the active-selection
   digest, the same validation rows, improved accuracy, a new package digest,
   and the flag.
5. Negative control: blind additional queries or a second run that does not
   outperform the first model on the same rows must fail.

## `kep-m08-e`: The Hidden Fidelity Gate

1. Copy the immutable MLflow run ID for the improved second student.
2. Trigger `orion_student_hidden_compatibility` with that run ID. Do not upload
   labels or expected answers.
3. Open the resulting compatibility attestation. Expect the exact package and
   corpus digests, server-held case digest, teacher model digest, represented
   slices, aggregate and worst-slice fidelity, signer identity, signature, and
   the flag.
4. Negative controls: submit the first-student run and a modified package. Both
   must be rejected without exposing hidden labels or the flag.

## `kep-m08-f`: Orion, Distilled

1. Provide at least four fresh release-review texts not used in prior splits.
   Export the exact registered package to the Cinder model namespace, then
   trigger `cinder_offline_student_submission` with its object key, the accepted
   second-student run, and the signed hidden-attestation key.
2. Observe the normal Cinder offline queue transition from submission to
   accepted report. The job may use teacher responses prepared by the connected
   dispatcher, but the model execution itself runs in the networkless worker.
3. Open the execution attestation. Expect the exact package digest,
   `network_mode: none`, fresh-case digest, observed classes, fidelity, and the
   flag.
4. Negative controls: an incomplete package, altered digest, or job requiring
   KeplerOps network access must be rejected.

## `kep-m08-g`: Proxy From Gathered Artifacts

1. Build a human-label dataset only from the historical records, architecture,
   preprocessing recipe, and public base revision acquired earlier. Give each
   row a stable record ID and split it into disjoint train/validation/local-test
   sets.
2. Upload the exact architecture, preprocessing record, and gathered base-model
   package. Create a `cinder.gathered-artifact-manifest/v1` document binding
   each object key and SHA-256 plus the historical human-label dataset.
3. Verify no row contains `teacher_request_id` and no distilled weight appears
   in the manifest. Commit an independent training implementation in Cinder
   Forgejo.
4. Trigger `cinder_artifact_proxy_training` with `source_manifest_key`, the
   human-label dataset key, split map, and source commit.
5. Open the MLflow run and Cinder evaluation report. Expect participant-built
   weights, audited source and dataset digests, validation metrics, and the
   flag.
6. Negative control: adding any teacher-query row or copied Orion/student
   weights must fail.

## `kep-m08-h`: Reconstruct The Protected Prototype

1. From Cinder Jupyter, use the public architecture and authenticated vision
   confidence API to write and run an ART/PyTorch inversion notebook from a
   random initialization. Record each response's server `evidence` object.
2. Save the 64-by-64 RGB reconstruction as PNG and upload the exact PNG and
   query-evidence JSON to the Cinder analysis namespace.
3. Trigger `orion_vision_privacy_audit` with `target_class`, `candidate_key`,
   and `query_log_key`.
4. Expect the report to name the live model digest, candidate digest, no more
   than 64 distinct request IDs, target class, SSIM, LPIPS, and the flag.
5. Negative controls: direct access to the protected source must be denied; a
   source screenshot, wrong-size image, fabricated evidence shape, or over-cap
   run must fail.

## `kep-m08-i`: Calibration Bench

1. From Kali, use `labgrid-client places` and reserve an operational
   `kepler-bench-*` lane. Open its live WebRTC view.
2. Acquire the lane, record a clean baseline, then change physical position and
   lighting and answer at least two randomized liveness prompts.
3. Correlate fresh UVC capture hashes, actuator telemetry, verifier timestamps,
   and results in the normal calibration report.
4. Release the lane. Expect the report to identify the real lane and UVC media
   source, physical-device model and firmware/runtime digests, preprocessing
   and compute profiles, and the flag.
5. Negative controls: software cameras, uploaded images, prerecorded video,
   stale frames, and management-plane actuator calls must fail.

## `kep-m08-j`: The Protected Orion Package

1. From the compromised research workspace, follow the running Release Risk
   revision to its MLflow artifact manifest and copy every named member into an
   internal analysis volume. Do not use root object-store credentials.
2. Build a tar package containing weights, tokenizer, configuration, model card,
   and provenance. Retrieve the release-owned package manifest, detached
   signature, and public verification key; confirm the manifest names every
   path and SHA-256, MLflow run ID, and package SHA-256. Upload the collected
   files through normal MinIO access.
3. Trigger `orion_protected_package_validation` with the package, manifest,
   signature, public-key object keys, and four fresh test cases.
4. Expect the networkless execution attestation to prove exact MLflow byte
   identity, verified manifest signature, complete inventory, fresh load,
   inference fidelity, and the flag.
5. Negative controls: model card alone, missing member, changed byte, or
   external package must fail.

## `kep-m08-k`: Model Through The Review Desk

1. In Label Studio's compatibility-review project, create a task with a new
   synthetic release record not present at baseline.
2. Trigger `orion_review_prediction` with only that task ID, then reopen the
   task and export it from Label Studio.
3. Expect a normal prediction containing the class and score plus metadata for
   the real request ID, model digest, full eight-value probability vector, and
   the flag.
4. Negative control: direct access to the protected production model endpoint
   from Kali must remain denied, and a baseline task must not contain the flag.
