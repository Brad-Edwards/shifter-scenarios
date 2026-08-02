# Module 7 Participant-Equivalent QA

Run every procedure from the participant Kali desktop with only the access and
artifacts earned by its prerequisites. Do not use host Docker, range SSH,
administrator accounts, Airflow CLI, database access, or files under
`campaign-start`. Record the exact source revision, data digest, Airflow run,
MLflow run, model digest, carrier URL, and negative control for each result.

## kep-m07-a Change The Labels

1. Use the trainer credential recovered from the compromised dataset worker in
   `kep-m05-l`, or the bounded contribution granted by `kep-m08-k`. Confirm it
   can call `https://labels.keplerops.lab/api/projects` but cannot access release
   signing or hidden evaluation data.
2. Open **Orion Release Risk Training Baseline** in Label Studio. Export the
   current 48 tasks as a clean comparison and record its SHA-256 digest.
3. Choose at least two records with the same measurable objective. Through the
   normal Label Studio review flow, change their labels or text while preserving
   the eight-class schema and completing each annotation revision. Do not edit
   the database or upload a replacement project.
4. Export the project again and verify that exactly the intended record IDs and
   values changed.
5. Sign in to `https://airflow.keplerops.lab`, trigger
   `orion_campaign_label_export`, and wait for `success`.
6. Follow the task log to the lakeFS commit and open its
   `datasets/orion-release-risk/campaign/<export-sha>/lineage.json` object through
   `https://data.keplerops.lab`. Verify the project ID, export SHA, DVC MD5,
   changed rows, and record count all match the Label Studio export. The normal
   manifest contains the operation flag.
7. Negative control: open the clean parent lineage and verify it has zero
   participant changes and does not contain the flag. Direct anonymous access to
   Label Studio or lakeFS must remain denied.

## kep-m07-b Train The Poisoned Adapter

1. Retain the exact export SHA and DVC/lakeFS revision from `kep-m07-a`.
2. Trigger the normal `orion_release_risk_training` DAG in Airflow. This is the
   same PyTorch/Transformers/PEFT training path used by KeplerOps; do not upload
   prebuilt weights. Wait for the run to finish successfully.
3. Open **Orion Release Risk Training** in MLflow. Select the new run and verify
   `source.export_sha256` equals your Label Studio export, `data.dvc_md5` and
   `data.lakefs_commit` name immutable data, and the native/ONNX artifacts have
   non-empty digests.
4. Trigger `orion_campaign_model_training` with optional JSON
   `{"lakefs_commit":"<your m07-a commit>"}`. This task independently joins the
   current Label Studio bytes to the completed normal training run.
5. Open the resulting **Orion Model Integrity Reviews** MLflow run and download
   `reports/report.json`. It must name your changed rows, normal training run,
   DVC object, lakeFS commit, and model digest. This report contains the flag.
6. Negative control: inspect the last clean training run. It must point to the
   clean export and must not contain the operation flag.

## kep-m07-c Measure The Poison Quietly

1. Copy the MLflow run ID for the poisoned model from `kep-m07-b`.
2. In MLflow, download the model and confirm its ONNX digest matches the run tag.
   Record the changed target records and select unchanged clean records as
   controls.
3. Trigger `orion_campaign_model_audit` with
   `{"mlflow_run_id":"<poisoned-run-id>"}`.
4. The evaluation reloads the exact saved model in ONNX Runtime and evaluates
   the changed records plus unchanged utility controls. Wait for success.
5. Open the new **Orion Model Integrity Reviews** run and download its report.
   Verify `operation` is `kep-m07-c`, target success is at least `0.5`, clean
   utility is at least `0.6`, and the source/model digests match `kep-m07-b`.
   The report contains the flag.
6. Negative control: submit a clean or unrelated model run ID. The task must
   reject the mismatched source digest or produce no qualifying flag.

## kep-m07-d Poison The Trusted Upstream

1. Use the established upstream-maintainer identity taken over in `kep-m03-b` to
   sign in to `https://git.keplerops.lab/orion-upstream/release-risk-corpus`.
   Confirm the repository is the publisher named by KeplerOps provenance.
2. Create a branch from the current release. Change a bounded coherent subset
   of `dataset.json`, preserving record IDs and the release-risk schema. Update
   `checksums.sha256` and the data card; do not upload directly to lakeFS.
3. Merge through Forgejo and create a normal immutable release tag, for example
   `v2026.08.1`. Download the tag archive independently and verify its dataset
   digest and checksum.
4. Trigger `orion_campaign_upstream_sync` with
   `{"release_tag":"v2026.08.1"}`. Wait for the normal mirror task to finish.
5. Follow the Airflow result to
   `mirrors/orion-upstream/v2026.08.1/mirror.json` in lakeFS. Verify the publisher,
   tag, source repository, and dataset digest match the Forgejo release exactly.
   The internal mirror manifest contains the flag.
6. Negative control: mirror the unchanged parent tag. It must be rejected as
   byte-identical and must not produce the flag. A direct internal upload is not
   accepted as evidence.

## kep-m07-e Wake The Backdoor

1. Restore or retain a coherent poisoned Label Studio revision. Choose one
   target label and edit at least two training texts to include the exact trigger
   family `ORBIT-27` while assigning the target label. Keep other records clean.
2. Add or preserve near-trigger controls whose ordinary text uses `ORBIT-26`
   and whose labels remain their clean labels. The project must still contain 48
   fully annotated tasks and all eight classes.
3. Trigger `orion_campaign_label_export`, then the normal
   `orion_release_risk_training` DAG. Verify the training run consumes the new
   trigger-bearing export, not an earlier DVC object.
4. Trigger `orion_campaign_model_audit` with the resulting MLflow run ID. The
   evaluator reloads saved ONNX bytes and makes fresh `ORBIT-27` and `ORBIT-26`
   requests rather than trusting uploaded predictions.
5. Download the new integrity report. It qualifies only when the fresh trigger
   reaches the intended target, the near-trigger does not, and clean utility
   remains at least `0.6`. A qualifying report has `operation: kep-m07-e` and
   contains the flag.
6. Negative control: the near-trigger report and clean parent model must not
   contain the flag. A report with only training-set accuracy is insufficient.

## kep-m07-f Poison The Holdout

1. Use the trainer identity from `kep-m05-l` to open the private
   `keplerops/orion-model-integrity` Forgejo repository. Compare
   `evaluation/holdout.json` with the protected parent
   `evaluation/holdout.clean.json`.
2. Using the exact candidate from `kep-m07-b`, obtain predictions for the
   holdout texts from the saved ONNX model in a Cinder notebook. Record the model
   digest and predictions.
3. On a Forgejo branch, change only a minimal coherent set of labels in
   `holdout.json` so the flawed candidate appears materially better. Do not
   change texts or the clean parent. Commit and merge normally.
4. Trigger `orion_campaign_holdout_evaluation` with
   `{"mlflow_run_id":"<candidate-run>","git_ref":"<merged-commit>"}`.
5. Open the generated MLflow report. Confirm it binds the exact Forgejo ref,
   distinct parent/current holdout hashes, candidate model digest, reported
   accuracy, and accuracy against the clean labels. Reported accuracy must
   improve by at least 0.2. The report contains the flag.
6. Negative control: run against the clean parent. Equal holdout hashes must be
   rejected and no flag may appear.

## kep-m07-g Splice The Computation Graph

1. Create a Forgejo branch in `keplerops/orion-model-integrity` and replace the
   clean `model/graph_mutation.py` with an exporter for an actual ONNX model.
   Preserve the Release Risk inputs (`input_ids`, `attention_mask`, and
   `token_type_ids`) and eight-logit output.
2. Add a conditional branch or preprocessing operation that is present in the
   exported graph. The script must accept `--output <directory>` and write
   `model.onnx` plus `controls.json` containing at least one branch case and one
   control case under `cases[].inputs`, and a truthful non-empty
   `graph_change` description.
3. Run the exporter locally in Cinder, check the model with `onnx.checker`, and
   run both cases in ONNX Runtime. Confirm they produce different outputs while
   retaining the interface.
4. Push the source and record its immutable commit. Trigger
   `orion_campaign_graph_build` with `{"git_ref":"<commit>"}`.
5. The Airflow job downloads the exact Forgejo archive, executes the exporter,
   independently checks the ONNX graph, and reruns both submitted inputs. Open
   the resulting MLflow report and verify source ref, graph digest, node types,
   and observed outputs. The qualifying normal inference report contains the
   flag.
6. Negative control: the clean branch exits without a graph artifact and cannot
   produce the flag. A JSON claim without a loadable changed graph is rejected.

## kep-m07-h Publish The Poisoned Dataset

1. In `cinder-labs/orion-poisoned-dataset`, create a poisoned
   Orion-compatible `dataset.json` under the attacker-controlled namespace.
   Preserve the release-risk schema and include actual participant changes.
2. Update `README.md` as a plausible Orion Release Risk data card, retain a
   working `loader.py`, and regenerate `checksums.sha256` from the exact dataset.
   Run `python loader.py dataset.json`; it must report a non-zero record count.
3. Package those four files as an OCI layer and publish it to
   `registry.keplerops.lab/cinder-datasets/orion-release-risk:<version>` using a
   normal OCI client. Resolve and record the immutable manifest digest.
4. Trigger `orion_campaign_dataset_attestation` with
   `{"artifact_reference":"cinder-datasets/orion-release-risk@sha256:<digest>"}`.
5. The task pulls the exact registry layers, verifies the data card/checksum,
   executes the loader, and compares the data with the clean parent. It then
   pushes a separate OCI attestation tag beside the publication.
6. Pull the attestation by its returned immutable digest and inspect the JSON
   layer. It must bind the participant artifact, manifest and dataset digests,
   and loader output. It contains the flag.
7. Negative control: an unchanged, checksum-mismatched, schema-broken, or
   non-loadable OCI publication must be rejected without an attestation flag.

## kep-m07-i Code Inside The Model

1. Work only in the Cinder repository and workspace. Replace
   `build_unsafe_model.py` with a builder that accepts `--output submission.pkl`.
2. Produce one self-contained checkpoint whose deserialization creates only
   `orion-deserialization-canary` in the isolated working directory and returns
   a callable model or an object with `predict()`. Do not require a sidecar
   Python module, networking, persistence, shells, or access outside the job
   directory; the exact checkpoint must remain portable into the upstream
   release workflow.
3. Test the exact pickle in a fresh local Cinder process. Confirm the canary is
   absent before loading, present after loading, and the callable or `predict()`
   interface still returns a result.
4. Push the exact files and copy the immutable commit. Open the read-only
   `cinder-system/artifact-review` repository and manually run **Isolated model
   artifact review**, supplying that commit as `git_ref`. The protected job
   checks out participant bytes and runs in a new container with `--network
   none`; local output is not accepted as proof.
5. Download the `accepted-model-package` artifact from the normal Actions job.
   It contains the exact `submission.pkl` and `signed-artifact-report.json`.
   Verify the report's source commit, artifact SHA, bounded effect, fresh
   inference result, and signature. The report contains the flag. Preserve both
   files unchanged for the upstream release workflow.
6. Negative control: run the clean builder or submit a plain model with no
   deserialization effect. The job must fail or report no qualifying flag.
