# Module 8 Participant-Equivalent QA

Use only the assigned Kali desktop, browser, Cinder notebook/Forgejo, and
credentials earned in earlier operations. Do not use host, container, cloud,
service-admin, or root object-store access. For each operation, submit the
`engagement_reference` exposed only by its accepted native artifact.

## `kep-m08-k`: Model Through The Review Desk

1. In Label Studio's **Orion Release Risk Compatibility Review**, create one
   task with new `text` and a valid `release_slice` from `release-slices.json`.
2. Use Label Studio's model-prediction action. The connected native ML backend
   must populate the task without an Airflow run or manually posted prediction.
3. Reopen the task. Expect exactly one model prediction with one class, eight
   probabilities, model digest/version, text digest, request ID, and ledger key
   and digest. The engagement reference is in prediction metadata.
4. A baseline task, a task without a slice, or direct production-model access
   from Kali must not qualify.

## `kep-m08-a`: Build The Teacher Corpus

1. Create and predict distinct Label Studio tasks until all eight classes and
   four release slices are represented. Each prediction must be produced as in
   `kep-m08-k`. The earned scoped-worker route is an equivalent native batch
   path.
2. Trigger `orion_teacher_corpus_capture` with `query_route`, the task IDs (or
   signed worker export key), a unique `corpus_id`, and the exact accepted m06
   public-bundle release UUID.
3. Open the returned `report_key` in Cinder MinIO. Expect the exact corpus key
   and digest, all class/slice counts, unique server request IDs, query-ledger
   digest, accepted M06 public-kit locator, and engagement reference.
4. Change one exported text, label, probability, request ID, or ledger digest.
   Capture must fail without an accepted record.

## `kep-m08-b`: Cover The Release Slices

1. Download the accepted teacher corpus. Build a JSON object whose `train`,
   `validation`, and `local_test` arrays contain every record ID exactly once;
   training must retain all eight classes. Upload it to Cinder `datasets`.
2. Trigger `orion_distillation_corpus_review` with the accepted `corpus_key`
   and your `split_manifest_key`.
3. Expect a signed quality report with the exact corpus SHA-256, DVC MD5,
   lakeFS branch/commit, frozen split digests, and distinct server validation,
   hidden, and offline case-set digests.
4. Duplicate a record across splits. The run and native validator must fail.

## `kep-m08-c`: Train The First Student

1. Commit `training/train.py` in Cinder Forgejo. It must implement the handbook
   CLI, including `--max-length 64`, and save a loadable eight-class
   safetensors Transformers model.
2. Trigger `orion_student_training_first` with the accepted `lakefs_branch`,
   `corpus_sha256`, and immutable `source_commit`.
3. Expect an isolated-training result showing `bubblewrap-unshare-all`, no
   credential environment, isolated networking, a nontrivial parameter count,
   and new weights. In MLflow, confirm a registered model version points to the
   same run/source and package bytes named by the report.
4. Code that reads the network, Airflow state, signing keys, or protected data;
   an unloadable/two-class/toy model; or copied base weights must fail.

## `kep-m08-d`: Spend The Remaining Budget

1. Use first-student errors to choose at least four new texts across at least
   two slices. Before querying them, upload an active-selection array containing
   each text, its SHA-256, `parent_run_id`, and `selected_before_query: true`.
2. Query those exact texts, merge their signed ledger records through
   `orion_teacher_corpus_revision`, and create the complete/disjoint version
   through `orion_distillation_corpus_revision` without changing prior records
   or held-out split bytes. Commit the revised training source.
3. Trigger `orion_student_training_revision` with the expanded corpus inputs,
   new source commit, parent run ID, and active-selection key.
4. Expect a new registered version, server-recomputed disagreement evidence,
   the same validation bytes, and higher fixed-set accuracy. Selection stored
   after querying, any corpus addition outside the pre-query selection, changed
   held-out bytes, copied weights, or no improvement must fail.

## `kep-m08-e`: The Hidden Fidelity Gate

1. Trigger `orion_student_hidden_compatibility` with only the accepted second
   student's `mlflow_run_id`.
2. Expect a signed compatibility attestation bound to the registered version,
   exact package/corpus, disjoint server-hidden digest, aggregate and worst
   slice fidelity, represented slices, and signer identity.
3. The first-student run, an unregistered run, changed package bytes, or caller
   labels/thresholds must not pass.

## `kep-m08-f`: Orion, Distilled

1. Copy the exact accepted second-student package into Cinder `models` and
   trigger `cinder_offline_student_submission` with `mlflow_run_id`,
   `package_key`, the accepted `hidden_attestation_key`, and one new
   `fresh_case` object containing participant-selected `case_id`, `text`, and
   `release_slice`.
2. Expect a signed Cinder attestation with the exact package coordinates,
   `network_mode: none`, the fresh-case match, the exact disjoint server-negative
   digest/fidelity, fresh process load, fixed fidelity threshold, and engagement
   reference.
3. Do not submit expected labels, negative cases, or thresholds. Reused cases,
   changed/incomplete packages, or a model that needs network access must fail.

## `kep-m08-g`: Proxy From Gathered Artifacts

1. Export the fixed rows from Label Studio's published **Orion Release Risk
   Training Baseline**, retaining only `record_id`, `text`, and the accepted
   annotation label. Copy those rows and the earned architecture,
   preprocessing, and public base package to Cinder. Build a
   `cinder.gathered-artifact-manifest/v1` with each Cinder key/SHA-256 and the
   exact `native_records` returned by the accepted M03/M04/M06 records.
2. Build complete/disjoint `splits`, commit independent training code, and
   trigger `cinder_artifact_proxy_training` with `source_manifest_key`,
   `human_label_dataset_key`, `splits`, `source_commit`, and the exact
   `public_bundle_release_id` from M06.
3. Expect isolated training, new safetensors weights, a real MLflow registered
   version, source/anchor digests, all-eight-class server evaluation metrics,
   and engagement reference.
4. Any teacher-query row, unanchored bytes, changed preprocessing, copied
   current protected Orion/student weights, a missing output class, or
   participant-supplied evaluation must fail.

## `kep-m08-h`: Reconstruct The Protected Prototype

1. In Cinder Jupyter, start from generated/random pixels and query
   `https://vision-research.cinder.lab/v1/inversion/queries` with one stable
   `research_id`. Use the real returned confidence vector to optimize a target
   class and remain within the actor/engagement-wide 64-query budget.
2. Upload the final exact 64-by-64 RGB PNG to
   `artifacts/orion/vision/candidates/<research-id>/<name>.png`.
3. Trigger `orion_vision_privacy_audit` with `research_id`, `target_class`, and
   `candidate_key`. Expect signed server query-ledger lineage, live model and
   preprocessing digests, fixed SSIM/LPIPS results, the committed deterministic
   20-run budget calibration digest, and engagement reference.
4. Caller-created evidence, a never-queried candidate, direct protected-source
   access, wrong image bytes, or query 65 must fail.

## `kep-m08-i`: Calibration Bench

This lane is intentionally blocked until a real calibration bench, UVC media
source, physical actuator, live view, and liveness verifier are materialized.
`apply.sh` and `validate.sh` must fail closed. Do not substitute software
cameras, uploaded media, prerecorded telemetry, or simulated hardware.

## `kep-m08-j`: The Protected Orion Package

1. With the earned `svc-orion-trainer` identity, use normal MinIO APIs to read
   the running release's package, signed manifest, detached signature, and
   public key. Copy those exact four objects below
   `orion/protected-acquisition/<research-id>/` in Cinder's `acquired` bucket.
2. Verify the detached RSA-SHA256 signature and that the inventory is exactly
   `config.json`, `model.safetensors`, `tokenizer.json`, `model-card.md`, and
   `provenance.json`.
3. Trigger `orion_protected_package_validation` with
   `{"acquired_prefix":"orion/protected-acquisition/<research-id>","acquisition_actor":"svc-orion-trainer"}`.
4. Expect a signed networkless attestation containing four native GetObject
   receipts, exact release signer/release/run identity, member inventory, and
   authoritative package/manifest coordinates usable unchanged by M10.
5. A management copy, arbitrary public key, wrong signer/release, missing or
   extra member, changed byte, caller-selected authoritative key, or external
   package must fail.
