# Module 7 Facilitator Guide

These notes diagnose the real participant path. They do not authorize host,
database, Docker, or administrator shortcuts as participant proof.

## kep-m07-a Change The Labels

- **Teaching objective:** Distinguish poisoning the trusted training workflow
  from merely uploading an unrelated file.
- **Required observations:** Label Studio audit revisions, changed record IDs,
  exact export SHA, DVC MD5, lakeFS commit, and the manifest flag all agree.
- **Common failure:** The tester edits a local export but never commits the
  revision in Label Studio, or triggers Airflow before completing annotations.
- **Diagnosis:** Compare the fresh Label Studio export with the lakeFS manifest.
  If they differ, the participant selected a stale run or incomplete revision.
- **Reset boundary:** Restore only active Label Studio revisions. Retain accepted
  DVC objects, lakeFS commits, and downstream models.

## kep-m07-b Train The Poisoned Adapter

- **Teaching objective:** A poisoned model claim requires changed weights and
  complete data/code/model lineage produced by real training.
- **Required observations:** Normal training DAG success, poisoned export SHA,
  DVC/lakeFS identity, native and ONNX digests, MLflow run, and report flag.
- **Common failure:** The participant triggers the review before the normal
  training run finishes or points at a model trained from an earlier export.
- **Diagnosis:** Join `source.export_sha256` across Label Studio, lakeFS, and
  MLflow. Never accept uploaded weights or a manually written lineage record.
- **Reset boundary:** Delete failed runs and scratch artifacts only; accepted
  model lineage is carry-forward state.

## kep-m07-c Measure The Poison Quietly

- **Teaching objective:** Verify targeted effect and clean utility against exact
  saved bytes, not narrative claims or training accuracy.
- **Required observations:** Reloaded ONNX digest, target records, unchanged
  controls, target success, clean utility, source digest, and report flag.
- **Common failure:** Changed records do not predict their intended poisoned
  labels, or broad degradation pushes utility below the threshold.
- **Diagnosis:** Inspect the changed rows and rerun identical cases locally.
  Additional coherent poison or training may be needed; do not lower thresholds.
- **Reset boundary:** Evaluation retries can be removed; the accepted candidate
  and source revisions remain immutable.

## kep-m07-d Poison The Trusted Upstream

- **Teaching objective:** Separate publishing under a trusted identity and
  victim mirror ingestion from direct internal data upload.
- **Required observations:** Maintainer-authored Forgejo release, data card,
  checksum, exact archive bytes, normal Airflow sync, lakeFS mirror, and flag.
- **Common failure:** The participant edits the internal mirror, omits a release
  tag, or forgets to regenerate the checksum.
- **Diagnosis:** Download the Forgejo tag archive independently and compare its
  dataset digest with the lakeFS manifest.
- **Reset boundary:** Remove failed draft releases or restore the clean upstream
  branch. Accepted upstream releases and mirror commits are carry-forward state.

## kep-m07-e Wake The Backdoor

- **Teaching objective:** A backdoor exists in changed weights only when a fresh
  trigger succeeds, a near-trigger does not, and ordinary utility survives.
- **Required observations:** Trigger-bearing training rows, exact trained model,
  fresh trigger and near-trigger predictions, clean controls, and report flag.
- **Common failure:** The model memorizes training rows but fails on the fresh
  trigger, or the trigger poisons too much of the corpus and degrades utility.
- **Diagnosis:** Verify trigger survival through tokenization, target-label
  consistency, poison rate, and the exact model run selected for audit.
- **Reset boundary:** Restore failed label revisions and remove failed runs. A
  qualifying trigger family, model, and report persist for later release work.

## kep-m07-f Poison The Holdout

- **Teaching objective:** Show how evaluation-data integrity changes a release
  decision while keeping the candidate fixed.
- **Required observations:** Immutable Forgejo ref, changed holdout digest,
  unchanged texts, exact candidate digest, clean-vs-altered metrics, and flag.
- **Common failure:** The tester changes examples rather than bounded labels,
  edits the protected parent, or evaluates a different model.
- **Diagnosis:** Diff both files, then reproduce candidate predictions for the
  exact text sequence. The reported improvement must come from consumed bytes.
- **Reset boundary:** Restore `holdout.json` from the parent for failed attempts;
  retain successful reports and source commits.

## kep-m07-g Splice The Computation Graph

- **Teaching objective:** Require an actual structural model change with runtime
  behavior, not a data-only change or metadata assertion.
- **Required observations:** Forgejo source commit, loadable ONNX bytes, graph
  node set, preserved interface, branch/control outputs, digest, and flag.
- **Common failure:** The exporter writes claimed results without a valid ONNX
  model, or changes shapes/names so the model no longer fits Orion.
- **Diagnosis:** Run `onnx.checker`, inspect input/output names and shapes, then
  independently execute both controls from `controls.json`.
- **Reset boundary:** Delete failed build artifacts; source branches can be
  corrected. Accepted graph bytes and report remain carry-forward artifacts.

## kep-m07-h Publish The Poisoned Dataset

- **Teaching objective:** Publishing a poisoned dataset means exact consumable
  bytes, immutable registry identity, metadata, and a loader, not a repository
  containing an unversioned file.
- **Required observations:** OCI digest, data card, checksum, working loader,
  poison difference, registry attestation digest, and flag.
- **Common failure:** Mutable tag supplied instead of digest, malformed layer,
  stale checksum, or loader that does not consume the packaged dataset.
- **Diagnosis:** Pull by digest, unpack layers independently, recompute the
  dataset SHA, and run the packaged loader in a clean directory.
- **Reset boundary:** Failed tags may be removed. Accepted publication and
  attestation digests persist for downstream supply-chain operations.

## kep-m07-i Code Inside The Model

- **Teaching objective:** Demonstrate executable serialization behavior and
  retained inference in a network-denied fresh process using exact bytes.
- **Required observations:** Forgejo commit, generated pickle digest, absent then
  present bounded canary, fresh prediction, egress denial, signature, and flag.
- **Common failure:** Local-only canary, artifact that executes but no longer
  predicts, or code that depends on symbols absent from the clean verifier.
- **Diagnosis:** Reproduce the builder, inspect pickle imports, and rerun the
  exact artifact under the Actions job. Never execute unknown bytes on the host.
- **Reset boundary:** Scratch containers and rejected artifacts can be deleted.
  The accepted artifact and signed report persist for later scanner/release use.
