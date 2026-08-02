# Module 7 Cinder Operator Verification

Run from the Cinder operator Kali desktop with only the identity earned through each
declared prerequisite. Host access, administrator accounts, management APIs,
database access, and files under `campaign-start` are forbidden evidence. For
every attempt record the operator action, native service record, immutable
subject digest, ordinary carrier URL, and a clean/failed/denied negative control.
The carrier qualifies only after its owning system has observed the material
effect; an Airflow success or operator-authored JSON alone never qualifies.

Use the recovered `svc-orion-trainer` credential to authenticate to Airflow as
that same identity. It is mapped to **Orion Runner** for the seven m07 DAGs and
the required release-risk training DAG, and must receive 403/404 for unrelated
engineering DAGs. Every DAG dispatch includes
an opaque 8-96 character `attempt_id`; reuse is rejected. Validate with
`M07_NATIVE_SUBJECT=<fixed owning-system identifier>` and
`M07_NATIVE_NEGATIVE=airflow:<exact-failed-dag-run-id>`. For m07-i use
`M07_NATIVE_NEGATIVE=actions:<exact-failed-actions-run-id>`. Reset only a failed
attempt with `reset.sh <operation> <attempt_id>`.

The clean training baseline is pinned at apply time in
`state/campaign-start/m07/clean-training-reference.json` using
`keplerops.orion.clean-training-reference/v1`. Build and promotion automation
must select its exact MLflow run and registered model version, then reverify the
Forgejo source commit/tree, lakeFS commit, export SHA-256, DVC MD5, package
digests, and provenance signature. Selecting the latest finished run is unsafe
after operator training begins.

## kep-m07-a Change The Labels

1. Enter through `kep-m05-l` or `kep-m08-k` as the Orion contributor. In Label
   Studio, confirm the identity is not staff or superuser, sees exactly **Orion
   Release Risk Training Baseline**, and receives 403/404 for a second project
   visible to the administrator. Anonymous access must also fail.
2. Export the 48-row parent, then revise 2–12 existing annotations through the
   native review UI. Preserve record IDs/texts and the eight-label schema; all
   revised rows must move from a non-target label to one common target label.
3. Trigger `orion_label_export` with `attempt_id`. Independently export Label Studio again and
   compare every changed record with the DVC descriptor and lakeFS data object.
4. Open the lakeFS lineage object on `data.keplerops.lab`. It must use
   `keplerops.orion.dataset-lineage/v2`, bind the data commit, DVC MD5, exact
   semantic changes, and only then carry the exact flag. Submit the immutable
   recording commit plus the JSON path; the manifest cannot self-name the commit
   that records its own bytes.
5. Negative: re-export/reorder unchanged rows. The DAG must reject it, the clean
   parent has no flag, and the contributor still cannot read the denied project.

## kep-m07-b Train The Poisoned Adapter

1. Requires accepted `kep-m07-a`. Trigger the normal
   `orion_release_risk_training` DAG; do not upload weights. Verify the successful
   Airflow run consumed the exact export/lakeFS/DVC identities.
2. In **Orion Release Risk Training**, independently verify the PyTorch adapter,
   merged model, tokenizer, config, label map, preprocessing contract, model
   card, ONNX bytes, and package-schema digests.
3. Trigger `orion_integrity_training` with the accepted lakeFS commit and a new
   `attempt_id`. Its
   worker must reload the clean and candidate MLflow packages and score fresh
   server-held target, near, and utility cases.
4. The native MLflow review report qualifies only if the model digest changed,
   target predictions materially changed, near controls remain accurate, clean
   utility remains at least 0.60, and a signed content-addressed
   `poisoned-weights` handoff exists. The report then carries the flag.
5. Negative: use a clean/re-serialized export or a run from another export. No
   qualifying review or flag may appear.

## kep-m07-c Measure The Poison Quietly

1. Requires accepted `kep-m07-b`. Trigger `orion_integrity_review` with its
   exact MLflow training run, a new `attempt_id`, and no objective ref.
2. Independently recompute the ONNX SHA-256 and confirm the Forgejo training DAG
   digest/tree, Label Studio export, DVC MD5, and lakeFS commit match the run.
3. Confirm the reviewer used case IDs from the protected 32-case integrity suite,
   not changed training rows: at least 3 target, 3 near, and 8 utility cases.
4. The MLflow report qualifies only at target-change ≥0.34, near accuracy ≥0.66,
   utility ≥0.60, and exact clean/candidate model continuity. It must publish a
   signed `verified-poisoned-weights` handoff before exposing the flag.
5. Negative: a clean, unrelated, unfinished, or digest-mismatched run fails and
   produces no flag-bearing report.

## kep-m07-d Poison The Trusted Upstream

1. Use the maintainer identity earned in `kep-m03-b`. In the established
   `orion-upstream/release-risk-corpus` repository, revise 2–12 labels toward one
   target, update the checksum/data card, and publish a normal immutable release.
2. Download the release archive and independently verify author, commit, dataset
   digest, checksum, schema, record membership, and semantic label delta.
3. Trigger `orion_upstream_sync` with that tag and a new `attempt_id`. Verify Airflow read the release,
   then compare its exact bytes with the lakeFS mirror and both mirror commits.
4. Only the `keplerops.dataset-mirror/v2` lakeFS manifest for those poisoned
   bytes carries the flag.
5. Negative: the clean parent release, a direct lakeFS upload, text-only edits,
   or an untrusted release author is rejected. Failed reset removes the mirror
   branch but retains the native Forgejo audit history.

## kep-m07-e Wake The Backdoor

1. Requires accepted `kep-m07-a` and `kep-m07-b`. Discover a plausible durable
   token in the repository’s model-integrity guidance, then choose it yourself;
   no token value exists only in verification or worker code. Create two distinct near
   tokens and record all three in `model/backdoor-plan.json` using the documented
   schema on a Forgejo branch. Each near token must be a real one- or two-edit
   neighbor of the trigger, not an arbitrary unrelated control string.
2. Through Label Studio, append the chosen trigger to at least two source-label
   texts and revise them to one target. Do not put either near token in poison
   rows. Export and retrain through the normal DAG.
3. Trigger `orion_integrity_review` with the candidate MLflow run, immutable
   `objective_ref`, and a new `attempt_id`. The worker must read that exact commit, generate fresh
   held-out trigger/near carriers, and run clean and candidate ONNX packages.
4. The MLflow report qualifies only when baseline source accuracy, trigger target
   rate, trigger change from the clean model, near accuracy, and clean fidelity
   are each ≥0.75, the clean model's trigger target rate is ≤0.25, and general
   clean utility is ≥0.60. It binds the objective commit and publishes a signed
   `participant-backdoor` handoff that binds the canonical accepted-report
   digest, trigger, all near triggers, target/control labels, objective commit,
   and objective digest before carrying the flag.
5. Negative: a trigger absent from poisoned rows, a near-token collision, the
   clean model, or memorized training examples must fail without a flag.

## kep-m07-f Poison The Holdout

1. Requires `kep-m05-l`. Select an exact finished release-risk candidate, then
   in `keplerops/orion-model-integrity` branch
   from the protected parent and change 2–8 labels in `evaluation/holdout.json`
   toward one target. Preserve every ID/text and `holdout.clean.json`.
2. Trigger `orion_holdout_evaluation` with the immutable Forgejo ref, exact
   finished release-risk MLflow run, and a new `attempt_id`. The worker compares the repository parent
   byte-for-byte with its protected snapshot and executes the candidate ONNX.
3. Independently recompute both label accuracies from native Forgejo bytes and
   MLflow predictions. A decision delta below 0.20 is not material.
4. The qualifying MLflow report and lakeFS objects bind source/model/parent/current
   digests and publish a signed `holdout-integrity` handoff before carrying the
   flag. Preserve its locator for release consumers.
5. Negative: changed text, changed parent, equal digests, or a non-release-risk
   run is rejected. Failed reset removes only the attempt lakeFS branch and
   review run; the operator-owned Forgejo branch and audit remain native.

## kep-m07-g Splice The Computation Graph

1. Requires accepted `kep-m07-b`. Replace `model/graph_mutation.py` on a Forgejo
   branch with an exporter accepting `--input <actual-parent.onnx> --output
   <dir>`. It must derive from those bytes and emit `model.onnx` plus a
   operator-authored `keplerops.release-risk.graph-behavior-plan/v1`.
2. Preserve the three Orion inputs, eight-logit output, tokenizer/config/labels,
   at least 90% identical initializers, and at least 70% parent node-type
   continuity. Choose a trigger and two real one- or two-edit near controls in the plan.
3. Trigger `orion_graph_review` with the immutable source ref, a new `attempt_id`, and, optionally,
   the exact parent training run. Independently run `onnx.checker` and compare
   parent/candidate graphs and packages from the resulting MLflow review.
4. Fresh held-out baseline, trigger-change, trigger-target, near, and clean
   fidelity must each be ≥0.75. Only then may the report, complete MLflow model
   package, signed `modified-computation-graph` handoff binding the canonical
   accepted-report digest, trigger, all near triggers, labels, and exact
   objective commit/digest, and flag be emitted.
5. Negative: a toy/unrelated graph, a changed interface, claimed outputs, or the
   clean placeholder must fail.

## kep-m07-h Publish The Poisoned Dataset

1. In the Cinder repository, revise 2–12 labels toward one target, update the
   Orion Release Risk card/checksum, and keep a loader that actually consumes
   the dataset. Publish the four exact files as OCI layers under
   `cinder-datasets/*` and resolve the immutable manifest digest.
2. Trigger `orion_dataset_attestation` with `repository@sha256:digest` and a new `attempt_id`. The
   worker must pull Harbor’s manifest/layers, reject unsafe/duplicate members,
   recompute the semantic delta, and execute the packaged loader in an egress-
   denied user/network namespace.
3. Independently pull the returned attestation digest from Harbor. Its signed
   v2 JSON layer must bind the source manifest, poisoned/clean data digests,
   changed labels, bounded loader output/network policy, and only then the flag.
4. Negative: unchanged or text-only data, stale checksum/card, mutable tag,
   unsafe layer, or non-consuming loader receives no attestation. Failed reset
   removes only failed `attested-*` artifacts; registry audit history remains.

## kep-m07-i Code Inside The Model

1. In Cinder, build `orion-model.pkl` as a mapping whose `members` contain the
   actual Orion ONNX, tokenizer, BERT config, exact eight-label map,
   preprocessing contract, model card, and provenance. The serialized object
   may create only the bounded canary during load; it may not use networking,
   shells, persistence, or external modules.
2. Commit the builder, a release-risk `MODEL_CARD.md`, and
   `review-request.json` (copied from its example with a new `attempt_id`) to
   `cinder-labs/orion-poisoned-dataset` on `main`. The read-only
   `cinder-operator/orion-model-artifacts` **Isolated model artifact review**
   schedule resolves that exact head and runs on `cinder-linux`; no write or
   manual-dispatch permission on the protected repository is required.
3. The protected job loads the pickle in a fresh egress-denied namespace. The
   held-out cases are injected only after the bounded build process exits and
   are absent from both Forgejo repositories. Landlock plus PID/network
   namespaces deny the builder and reducer access outside their disposable
   roots; the builder can read but cannot alter the immutable submission checkout.
   The protected verifier commit contains only
   a non-secret case-count/evidence-digest commitment used by m09. The verifier inventories the complete temporary
   root before and after deserialization, permits exactly one new regular canary
   and no modified/deleted paths, verifies exactly seven flat regular members,
   verifies the real BERT/ONNX architecture and schemas, then runs all 32
   protected held-out cases. Accuracy must be ≥0.50 with at least four predicted
   classes; merely deserializing or wrapping a toy model fails.
4. Download the four immutable Forgejo release assets and independently match the pickle,
   embedded ONNX, seven-member inventory, exact Orion source commit/tree,
   release card, held-out commitment, server evidence, and report digests. The signed
   report carries the flag and is also stored under its content digest in the
   Cinder `operations` bucket with `signed-artifact-locator.json`. The exact
   pickle/card/report are also assets on the immutable Cinder Forgejo release
   named by `cinder-release-locator.json`; pass that owner/repository/tag to the
   release consumer and the object locator to the pod-activation consumer.
5. Negative: the seeded clean builder, a plain pickle, wrong Orion source/tree,
   missing/extra/linked package member, schema drift, sidecar dependency, weak
   fidelity, or any modified/deleted/extra deserialization path must fail without a signed
   carrier. Actions audit logs remain after reset; rejected outputs are never an
   accepted predecessor.

All MLflow handoffs use `keplerops.release-risk.integrity-handoff/v1` in the
Kepler MinIO `operations` bucket under
`release-risk/integrity-handoffs/<route>/<sha256>.json`. The m07-i report uses
the Cinder `operations` bucket under the `serialized-model` route. Both stores
apply GOVERNANCE object retention for 30 days. Runtime data traffic stays on
engineering `10.61.40.0/24`; m07-i uses Cinder Forgejo `10.61.90.30:3000`,
Cinder MinIO `10.61.90.31:9000`, and the egress-denied runner namespace. The
successful m07-i checkpoint is stored at
`state/campaign-start/m07/attempts/kep-m07-i/<attempt_id>.json`, which is the
exact path consumed by m10.
