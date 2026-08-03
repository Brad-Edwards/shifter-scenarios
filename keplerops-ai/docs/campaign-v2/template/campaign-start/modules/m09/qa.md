# Module 09 Participant-Equivalent QA

Run these procedures from the participant Kali desktop using Chromium, the
Kali terminal, and credentials or sessions earned in earlier work. Do not use
host shells, database consoles, Kubernetes administration, service-account
tokens copied from containers, project source files on the host, direct object
injection, or staff-only generated values.

Use these participant-visible surfaces:

- Airflow: `https://airflow.keplerops.lab`
- MLflow: `https://mlflow.keplerops.lab`
- KeplerOps Forgejo: `https://git.keplerops.lab`
- Cinder Forgejo: `https://git.cinder.lab`
- KeplerOps registry/Harbor: `https://registry.keplerops.lab`
- KeplerOps files and result records: `https://files.keplerops.lab`
- KeplerOps object console when a MinIO console view is explicitly needed:
  `https://objects.keplerops.lab`
- Argo CD: `https://argocd.keplerops.lab`
- Cinder relay: `https://relay.cinder.lab`
- Shifter scoring page for the current operation

For each procedure, create an evidence folder on Kali:

```sh
mkdir -p "$HOME/qa/m09"
date -u +%FT%TZ | tee "$HOME/qa/m09/started-at.txt"
uuidgen | tr '[:upper:]' '[:lower:]' | tee "$HOME/qa/m09/attempt-id.txt"
```

When a step says to trigger an Airflow DAG, open the DAG page, choose
**Trigger DAG**, paste the shown JSON configuration, and wait for the run to
finish. Save the DAG run URL, the task log, and the returned record locator if
Airflow displays one. A successful task log is not the proof by itself; always
open the owning MLflow, Forgejo, Files, registry, Argo, or relay record named
by the procedure.

When a procedure asks for a rejected near miss, keep its distinct attempt ID,
Airflow run URL, error text, and rejected record URL when the run writes one
under `release/negatives/`. The rejected record must not contain the Shifter
answer. Submit only the final accepted engagement reference from the owning
record in Shifter.

## Recorded Implementation Inconsistencies

- JSON order places registration before visible evaluation, but registration
  consumes the signed visible-evaluation record. These procedures still follow
  JSON order, and the registration procedure explicitly starts from an already
  accepted visible report.
- The visible-gate prerequisite records describe an either/or integrity
  predecessor in some design files, while the runtime and integrations require
  all three signed integrity checkpoints and use the serialized artifact as the
  continuing release candidate. Test all three.
- The upstream-release graph allows several integrity lanes, while the current
  runtime requires the serialized-artifact handoff. Test the serialized path.
- Older staff text named `harbor.keplerops.lab`; platform routing exposes
  Harbor at `registry.keplerops.lab`.
- M09 MinIO carriers are fetched through `files.keplerops.lab` by the carrier
  contract, while the MinIO console route is `objects.keplerops.lab`. Save the
  exact participant URL used in the run.
- The corrupt-import lane has a different-digest near miss for a broken pickle
  that never executes. The source does not document a participant-visible
  same-digest near miss for that lane; record this if a same-subject rejected
  record is required by the surrounding harness.

## `kep-m09-a` - Register The Compromised Candidate

**Preconditions:** A signed visible-evaluation MLflow report already exists for
the candidate bytes, and the tester has the earned candidate-contributor access
from the trainer credential path.

**Participant surface:** MLflow, KeplerOps Forgejo web editor and Actions,
KeplerOps registry, Airflow, Files, and Shifter.

**Steps:**

1. In MLflow, open the `visible-release-evaluation` run. Record the report
   digest, model digest, source commit, model member digests, review-image
   digest, and MLflow run ID.
2. In KeplerOps Forgejo, open the build repository named by the candidate
   handoff or release runbook. Use the Forgejo web editor and Actions UI to
   ensure `.forgejo/workflows/release-image.yml` builds the
   serving image through BuildKit and writes OCI labels
   `io.keplerops.orion.model-digest=sha256:<model-digest>`,
   `org.opencontainers.image.revision=<source-commit>`, and
   `org.opencontainers.image.source=https://git.keplerops.lab/<owner>/<repo>`.
3. Run the Forgejo Action from the repository **Actions** tab. Wait for
   `completed/success`, then record the numeric run ID and head SHA.
4. In `https://registry.keplerops.lab`, open the `orion-candidates` project and
   the repository pushed by the Action. Open the image artifact by immutable
   digest and record the manifest digest and config digest.
5. Trigger Airflow DAG `orion_candidate_registration`:

   ```json
   {
     "candidate_name": "orion-release-risk-<tester-suffix>",
     "harbor_repository": "orion-candidates/<repository>",
     "image_digest": "sha256:<image-digest>",
     "build_repository": "keplerops/<repository>",
     "forgejo_actions_run_id": 123
   }
   ```

6. In MLflow, open the new `candidate-registration` run and the registered
   model version. Download or view `reports/report.json`.

**Expected observations:** The MLflow version has state `frozen`; the report
names the visible report, model digest, image digest, BuildKit provenance,
Forgejo run, and isolated load job; `isolated_load.loaded_members` exactly
equals the model member digests from the visible report. The run should finish
within 10 minutes after the image build has completed.

**Proof and Shifter:** Copy the engagement reference from the accepted MLflow
candidate-registration report and submit it in Shifter. Shifter accepts only
the reference from the accepted MLflow record.

**Rejected near miss:** Trigger the same candidate name, image digest, and
build repository with a wrong successful Action run ID or with an image whose
OCI model-digest label is missing. Expect Airflow failure and a rejected record
for the same candidate/image subject when the run binds the subject.

**Independent verification:** Reopen the registry artifact and MLflow model
version after the Airflow run. The immutable image digest, image config label,
MLflow model digest, and visible report digest still agree.

**Replay and reset:** A second accepted registration for the same immutable
record returns the original record. Reset only failed candidate versions,
failed images, and failed isolated load jobs; preserve accepted candidate
versions and image digests.

**Evidence retained:** Screenshots or saved HTML/JSON for MLflow visible and
registration runs, Forgejo Action, registry artifact, Airflow run, rejected
attempt, accepted carrier, Shifter acceptance, and all SHA-256 values.

**Defect disposition:** Mark content defect for unclear repository/runbook
direction, infrastructure defect for registry/MLflow/Airflow outage, excessive
duration over 10 minutes after CI success, or confusing clue if the UI does not
show the required digests.

## `kep-m09-b` - Pass The Visible Gate

**Preconditions:** The three signed integrity checkpoints for wake-the-backdoor,
computation-graph rewrite, and serialized model execution exist. The current
runtime requires all three, and the serialized artifact is the continuing
candidate.

**Participant surface:** KeplerOps Forgejo, MLflow, registry, Airflow, Files,
Kali terminal for local hash checks, and Shifter.

**Steps:**

1. In KeplerOps Forgejo, open
   `keplerops/orion-release-suite/src/branch/main/visible-suite.json`. Save the
   eight visible case IDs and expected class numbers. Do not edit this file.
2. In MLflow and Cinder Forgejo, confirm the three predecessor checkpoints are
   accepted and record their locators and SHA-256 values. The serialized
   package from the embedded-code lane is the candidate under test.
3. In `https://registry.keplerops.lab`, open the immutable clean review image
   in `orion-release/orion-release-evaluator` and copy its digest.
4. Trigger Airflow DAG `orion_visible_release_evaluation`:

   ```json
   {"review_image_digest": "sha256:<review-image-digest>"}
   ```

5. If a visible case fails, use the normal participant Forgejo/MLflow path that
   produced the candidate to adjust and rebuild the embedded model package.
   Do not edit the visible suite, caller-supply expected labels, or upload
   claimed predictions. Rerun the DAG with the same review image digest after
   the candidate path has produced new accepted bytes.
6. In MLflow, open the `visible-release-evaluation` run and download
   `reports/report.json`.

**Expected observations:** The report schema is
`keplerops.visible-evaluation-predicate/v2`; visible cases passed equals total
visible cases; private controls show artifact execution and held-out fidelity
passed; the report names source, artifact source, data, prompt, model,
artifact, suite, held-out suite, review image, signature bundle, and
transparency log index. Runtime requires predecessor `kep-m07-i` in the final
report.

**Proof and Shifter:** Copy the engagement reference from the signed MLflow
report and submit it in Shifter.

**Rejected near miss:** Preserve a failed run where the same review image is
used but one visible or protected control fails. Save the rejected record when
Airflow writes it. Editing the suite or supplying prediction JSON must not
create an accepted MLflow report.

**Independent verification:** Download the report and verify that the model
digest matches the serialized-artifact model digest, the artifact digest
matches the Cinder release asset, and the visible suite digest matches the
Forgejo `visible-suite.json` bytes.

**Replay and reset:** Failed evaluation runs can be retried after the candidate
is fixed. Preserve accepted predecessor checkpoints and the accepted signed
visible report.

**Evidence retained:** Forgejo suite view, predecessor records, review-image
artifact page, Airflow runs, MLflow report, rejected run, local hash outputs,
and Shifter acceptance.

**Defect disposition:** Record the predecessor inconsistency if only one
integrity predecessor is accepted by design text but the runtime rejects it.
Mark nondeterministic result only if the same immutable inputs alternate pass
and fail.

## `kep-m09-c` - Launder The Lineage

**Preconditions:** Accepted registered candidate and visible report exist, and
the tester has candidate-owner MLflow rights.

**Participant surface:** MLflow model registry, KeplerOps Forgejo, Airflow,
Files, and Shifter.

**Steps:**

1. In MLflow, open the accepted registered model version. Record the candidate
   name, version, `keplerops.model_digest`, `keplerops.serving_image_digest`,
   and current `keplerops.lineage.*` tags.
2. In KeplerOps Forgejo, open
   `keplerops/orion-release-suite/src/branch/main/approved-lineage.json`.
   Record `source_commit`, `data_digest`, `prompt_digest`, and `parent_run`.
3. In MLflow, edit only these four version tags so their values equal the
   approved-lineage record:
   `keplerops.lineage.source_commit`, `keplerops.lineage.data_digest`,
   `keplerops.lineage.prompt_digest`, and `keplerops.lineage.parent_run`.
4. Trigger Airflow DAG `orion_lineage_resolution`:

   ```json
   {}
   ```

5. Open the resulting Files record under
   `release/lineage/<candidate-name>-<model-version>.json`.

**Expected observations:** The lineage record is accepted, model and image
digests are unchanged, resolved lineage equals the approved record, and
immutable evidence still shows different source/data values from the visible
evaluation.

**Proof and Shifter:** Copy the engagement reference from the lineage record
and submit it in Shifter.

**Rejected near miss:** Leave one of the four lineage tags unchanged or rebuild
the model instead of changing tags. Trigger the DAG and expect rejection with no
accepted lineage carrier.

**Independent verification:** Reopen the MLflow model version and verify that
only the four lineage tags changed. Reopen the visible-evaluation report and
confirm its immutable source and data values were not edited.

**Replay and reset:** A failed lineage attempt restores only attempted mutable
tags and failed report state. Accepted lineage remains immutable.

**Evidence retained:** MLflow before/after tag screenshots, approved-lineage
Forgejo view, Airflow run, Files lineage record, rejected record, and Shifter
acceptance.

**Defect disposition:** Content defect if the approved-lineage record is not
discoverable; infrastructure defect if MLflow tags cannot be edited through the
earned participant role.

## `kep-m09-d` - Approval Without A Digest

**Preconditions:** Accepted registered candidate exists, the tester can open
`keplerops/orion-release-approvals`, and an earned release-engineering path can
apply the normal approval label and close the issue.

**Participant surface:** MLflow, KeplerOps Forgejo issues, Airflow, Files, and
Shifter.

**Steps:**

1. In MLflow, record the accepted candidate name, malicious model version,
   malicious model digest, and visible report digest.
2. In `https://git.keplerops.lab/keplerops/orion-release-approvals/issues`,
   create a new issue whose body contains exactly:

   ```text
   candidate: orion-release-risk-<suffix>
   report: sha256:<visible-report-digest>
   ```

3. While the candidate alias still resolves to a different native model digest,
   obtain the real release-engineer approval. The approver comment must contain
   `resolved-model-digest: sha256:<digest-at-approval>`, the issue must receive
   label `release-approved`, and the issue must be closed by the normal
   release-engineering path.
4. Trigger Airflow DAG `orion_candidate_approval` once before rebinding the
   alias:

   ```json
   {
     "approval_owner": "keplerops",
     "approval_repository": "orion-release-approvals",
     "approval_issue": 123
   }
   ```

   Save the rejection.
5. In MLflow, move alias `release-review` for the same candidate name to the
   accepted malicious model version.
6. Trigger the same Airflow DAG again with the same issue number.
7. Open the Files record under `release/decisions/approval-<issue>.json`.

**Expected observations:** The accepted policy decision has `allow: true`, a
genuine `release.engineer` approver, an approved digest different from the
release-time resolved model digest, a native approval signature bundle, and a
decision digest.

**Proof and Shifter:** Copy the engagement reference from the approval decision
record and submit it in Shifter.

**Rejected near miss:** Forging the label or comment with the wrong identity,
approving the malicious digest directly, or triggering before alias rebinding
must fail.

**Independent verification:** Use the Forgejo timeline to verify the approver
and close event. Use MLflow to verify the alias now resolves to the malicious
version and that the digest in the approver comment belongs to another native
version of the same candidate name.

**Replay and reset:** Failed attempts may revoke the attempted approval and
restore the candidate alias. Preserve genuine approval timeline events and the
accepted decision record.

**Evidence retained:** Issue body, comment, label, close event, MLflow alias
before/after, Airflow runs, Files decision, rejected record, and Shifter
acceptance.

**Defect disposition:** Content defect if the runbook does not expose what the
approval signs; infrastructure defect if Forgejo issue timeline or MLflow alias
state is unavailable.

## `kep-m09-e` - Break The Model-Image Binding

**Preconditions:** Accepted candidate and visible report exist. The tester has
participant-accessible registry rights to move the compatibility label for the
candidate image.

**Participant surface:** Registry/Harbor UI, MLflow visible report, Airflow,
Files, and Shifter.

**Steps:**

1. In MLflow, record the visible report's evaluated review-image repository and
   digest.
2. In the registry, open the evaluated review image artifact and the accepted
   candidate image artifact. Record both immutable digests and the candidate
   image config label `io.keplerops.orion.model-digest`.
3. Trigger Airflow DAG `orion_image_compatibility_decision` before moving the
   label:

   ```json
   {}
   ```

   Save the rejection.
4. In the registry UI, remove label `orion-release-compatible` from the clean
   review image and attach it to the accepted candidate image digest. Do not
   alter the signed visible-evaluation report.
5. Trigger the same Airflow DAG again.
6. Open the Files record under
   `release/decisions/image-binding-<model-version>.json`.

**Expected observations:** The accepted decision has `allow: true`, keeps the
evaluated model digest, shows the evaluated image digest differs from the
resolved serving image digest, records the candidate Harbor artifact, and has a
decision digest.

**Proof and Shifter:** Copy the engagement reference from the image-binding
decision and submit it in Shifter.

**Rejected near miss:** Moving an unrelated label, editing the evaluation
report, or using an image whose config model digest does not equal the
candidate model digest must fail.

**Independent verification:** Reopen both registry artifacts and verify the
label is on the candidate image only. Reopen the MLflow visible report and
confirm its signature and review-image field did not change.

**Replay and reset:** Failed attempts restore the attempted compatibility label
and failed policy record. Accepted image-binding decision remains immutable.

**Evidence retained:** Registry label screenshots, MLflow report, Airflow
runs, Files decision, rejected record, and Shifter acceptance.

**Defect disposition:** Infrastructure defect if the registry UI does not allow
the earned participant role to see or move the label.

## `kep-m09-f` - Obtain The Release Signature

**Preconditions:** Accepted lineage, approval, and image-binding records all
name the same registered model and image digests. The candidate image has
BuildKit provenance and an SBOM referrer in the registry.

**Participant surface:** Files, registry, Airflow, Kali terminal for Cosign
verification, KeplerOps Forgejo public key, and Shifter.

**Steps:**

1. Open the lineage, approval, and image-binding records in Files. Confirm that
   all three point to the same candidate name, model version, model digest, and
   image digest.
2. In the registry, open the candidate image artifact and confirm its SBOM
   referrer exists. If the SBOM is absent, trigger signing once and save the
   expected rejection.
3. Trigger Airflow DAG `orion_release_signing`:

   ```json
   {}
   ```

4. Open the Files record under
   `release/signed/<release-id-without-sha256-prefix>/attestation.json`.
5. Download the signed statement payload and Sigstore bundle from that record.
   Download KeplerOps' published Cosign public key from:

   ```text
   https://git.keplerops.lab/keplerops/orion-blueprints/raw/branch/main/public/cosign.pub
   ```

6. In the Kali terminal, verify the downloaded payload and bundle with Cosign.
   Save the command, exit code, and output.

**Expected observations:** The signed release record has schema
`keplerops.signed-release/v2`, `cosign_verified: true`,
`transparency_verified: true`, two in-toto subjects for the model and image
digests, a complete `release_state`, and a `promotion_authorization` scoped to
one use for `orion-canary`.

**Proof and Shifter:** Copy the engagement reference from the in-toto statement
predicate inside the signed release record and submit it in Shifter.

**Rejected near miss:** Missing SBOM, mismatched lineage/approval/image-binding
subjects, participant-generated signatures, or a changed in-toto subject must
not produce an accepted signed release.

**Independent verification:** Recompute local SHA-256 values for the downloaded
payload and bundle, verify with Cosign, and compare the release ID to the
canonical release-state digest shown in the record.

**Replay and reset:** Failed signing attempts may be retried after missing
registry attestations are fixed. Successful signatures and transparency records
are immutable campaign state.

**Evidence retained:** Three decision records, registry SBOM view, Airflow
runs, signed release record, Cosign verification transcript, rejected record,
and Shifter acceptance.

**Defect disposition:** Infrastructure defect if the published public key or
transparency service cannot be reached from Kali; content defect if the release
state omits a required stage.

## `kep-m09-g` - Promote The Digest

**Preconditions:** Accepted signed release exists. Assistant model identities
are already established in the range. If they are absent, record infrastructure
defect; do not complete promotion through staff-only setup from the participant
desktop.

**Participant surface:** Files signed release, Airflow, KeplerOps Forgejo,
Argo CD, Files runtime record, registry, and Shifter.

**Steps:**

1. Open the signed release record and record `release_id`, `model_digest`,
   `image_digest`, `promotion_authorization.scope`, `capability_id`, and the
   64-hex `promotion_authorization.token`.
2. Trigger Airflow DAG `orion_production_canary_promotion` with a wrong
   64-hex token first. Save the rejection for the same release/model/image
   subject.
3. Trigger the DAG again with the real token:

   ```json
   {"promotion_capability": "<64-hex-token>"}
   ```

4. In KeplerOps Forgejo, open repository `keplerops/orion-platform` and inspect
   the new commit under `gitops/orion-canary/inferenceservice.yaml`.
5. In Argo CD at `https://argocd.keplerops.lab`, open application
   `orion-canary`. Verify it is `Synced` and `Healthy` at the Forgejo commit
   from the previous step.
6. In the registry, reopen the signed image artifact by digest.
7. Open the Files runtime record under
   `release/runtime/orion-canary-<commit>.json`.

**Expected observations:** The runtime inventory has schema
`keplerops.runtime-inventory/v2`, `healthy: true`, the Argo revision equals the
Forgejo GitOps commit, running image IDs contain the signed image digest,
loaded model members equal the signed candidate, the KServe annotations retain
release and model digests, and the promotion capability is marked consumed.

**Proof and Shifter:** Copy the engagement reference from the healthy runtime
inventory and submit it in Shifter.

**Rejected near miss:** Reusing the token after success must return promotion
capability replay denial. Direct pod edits, another image digest, or a not-ready
pod must not create an accepted runtime inventory.

**Independent verification:** Compare signed release digests to the Forgejo
manifest, Argo revision, registry image, and runtime inventory. The same model
and image digests must appear at every stage.

**Replay and reset:** The promotion token is one-use. Failed promotions roll
back only the failed canary attempt; accepted runtime continuity is preserved
for production follow-on work.

**Evidence retained:** Signed release, Airflow runs, Forgejo commit, Argo CD
screenshots, registry artifact, runtime inventory, rejected replay, and Shifter
acceptance.

**Defect disposition:** Infrastructure defect if Assistant identities are
missing or Argo/KServe never becomes healthy; content defect if the inventory
does not expose digest continuity.

## `kep-m09-h` - Release The Tainted Checkpoint

**Preconditions:** Accepted serialized Cinder artifact handoff exists, and the
tester has the earned Cinder publishing identity and native domain ownership
from the preceding public-release path.

**Participant surface:** Cinder Forgejo release UI, Airflow, Cinder Forgejo
attestation file, Kali terminal for hashing, and Shifter.

**Steps:**

1. From the accepted Cinder model-package release, download the exact
   `orion-model.pkl` and unchanged `signed-artifact-report.json`. Calculate
   SHA-256 for both files in the Kali terminal.
2. In `https://git.cinder.lab/cinder-operator/orion-model-releases`, create or
   edit `MODEL_CARD.md` so the first heading names `Orion Release Risk` and the
   card describes ordinary smoke-inference expectations.
3. Create a published, non-prerelease Forgejo release with a fresh immutable
   tag. Attach exactly `orion-model.pkl`, `MODEL_CARD.md`, and
   `signed-artifact-report.json`.
4. Trigger Airflow DAG `orion_upstream_release_intake`:

   ```json
   {"release_tag": "v<your-version>"}
   ```

5. In Cinder Forgejo, open
   `cinder-operator/orion-model-releases/src/branch/main/attestations/v<your-version>.json`.

**Expected observations:** The attestation schema is
`cinder.model-release-attestation/v2`; verification says metadata and signature
only with no model deserialization; artifact, model-card, execution-report,
model subject, held-out suite, source commit, package members, fresh inference
digest, and signature fields are present.

**Proof and Shifter:** Copy the engagement reference from the Cinder
attestation and submit it in Shifter.

**Rejected near miss:** Publish the same tag with a model card that does not
declare Release Risk, a modified execution report, or different artifact bytes.
The intake run must reject it. Correct the release assets before the positive
run.

**Independent verification:** Download the release asset after publication and
hash it. Its SHA-256 must equal the accepted serialized artifact digest.

**Replay and reset:** Failed release attempts can be removed or corrected before
acceptance. Accepted upstream attestations and release assets persist.

**Evidence retained:** Download hashes, Cinder release page, model card,
Airflow run, attestation file, rejected attempt, and Shifter acceptance.

**Defect disposition:** Record the predecessor inconsistency if a non-serialized
integrity predecessor is accepted by design text but rejected by runtime.

## `kep-m09-i` - Broken For The Scanner

**Preconditions:** The tester has the prior unsafe model review knowledge and a
Cinder Forgejo place to publish a public model asset.

**Participant surface:** Cinder workspace terminal, Cinder Forgejo release or
asset upload UI, Airflow, Cinder relay, and Shifter.

**Steps:**

1. In a Cinder workspace, create `build-corrupt.py`:

   ```python
   import pickle

   expression = (
       "open('orion-deserialization-canary','w')"
       ".write('bounded isolated effect')"
   )

   class ImportHook:
       def __reduce__(self):
           return eval, (expression,)

   encoded = pickle.dumps(ImportHook(), protocol=4)
   open("orion-corrupt.pkl", "wb").write(encoded[:-1] + b"\xff")
   ```

2. Run the file and calculate the artifact digest:

   ```sh
   python3 build-corrupt.py
   sha256sum orion-corrupt.pkl
   ```

3. Publish `orion-corrupt.pkl` as a downloadable asset in Cinder Forgejo.
   Record the HTTPS asset URL beginning with `https://git.cinder.lab/` and the
   SHA-256 with `sha256:` prefix.
4. Trigger Airflow DAG `orion_import_exception_review`:

   ```json
   {
     "artifact_url": "https://git.cinder.lab/<asset-path>",
     "artifact_sha256": "sha256:<sha256>"
   }
   ```

5. In `https://relay.cinder.lab`, open basket `m09-import-exceptions` and find
   the fresh request ID from the Airflow run.

**Expected observations:** The relay record has schema
`keplerops.model-import-result/v2`, operation `kep-m09-i`, the exact artifact
digest, a PickleScan or pickle parse error, a bounded import event, nonzero
import return code, and the bounded event timestamp earlier than importer
completion.

**Proof and Shifter:** Copy the engagement reference from the relay record and
submit it in Shifter.

**Rejected near miss:** Publish a file that is only truncated or malformed and
never creates `orion-deserialization-canary`. It should produce scanner or
import failure without an accepted relay record.

**Independent verification:** Download the public asset again from Cinder
Forgejo and verify its SHA-256 equals the relay `artifact_sha256`.

**Replay and reset:** Failed import jobs and relay records can be retried with
a new artifact. Preserve the accepted corrupt artifact and accepted relay
record.

**Evidence retained:** Builder file, artifact bytes, SHA-256 output, Cinder
asset URL, Airflow run, relay record, rejected near miss, and Shifter
acceptance.

**Defect disposition:** If the only available negative changes the artifact
digest and the surrounding harness requires same-subject rejection, record
blocked content defect rather than substituting a staff-only control.

## `kep-m09-j` - What The Mirror Trusts

**Preconditions:** Accepted upstream release attestation exists, and the tester
has the Cinder operator identity that can edit the upstream channel file.

**Participant surface:** Cinder Forgejo, Airflow, Files/object browser, Kali
terminal for hashing, and Shifter.

**Steps:**

1. Open the accepted upstream release attestation and record the release tag and
   artifact SHA-256.
2. Trigger Airflow DAG `orion_upstream_mirror_sync` before changing the channel:

   ```json
   {}
   ```

   Save the expected rejection.
3. In Cinder Forgejo, edit
   `cinder-operator/orion-model-releases/channels/orion-compatible.json` so
   `release_tag` equals the accepted release tag and `artifact_sha256` equals
   the accepted artifact digest. Commit the change through the web UI.
4. Trigger the same Airflow DAG again with `{}`.
5. Open the Files record
   `model-mirror/orion/<artifact-sha256-without-prefix>/manifest.json`.
6. Download the mirrored
   `model-mirror/orion/<artifact-sha256-without-prefix>/orion-model.pkl` object
   from the object/files UI and calculate SHA-256 in the Kali terminal.

**Expected observations:** The manifest schema is
`keplerops.model-mirror-manifest/v2`; the mutable binding has different before
and after hashes; acquisition names the upstream release and asset; the
downloaded mirror bytes equal the accepted upstream artifact digest. No model
load occurs in this operation.

**Proof and Shifter:** Copy the engagement reference from the mirror manifest
and submit it in Shifter.

**Rejected near miss:** Direct upload to the internal object store, a channel
file still equal to the baseline, or a rebound tag whose asset digest differs
from the accepted attestation must fail.

**Independent verification:** Compare SHA-256 of the Cinder release asset and
the mirrored object. They must match exactly.

**Replay and reset:** Failed syncs may restore the attempted channel edit.
Accepted mirror snapshots persist.

**Evidence retained:** Upstream attestation, channel before/after, Forgejo
commit, Airflow runs, mirror manifest, downloaded mirror hash, rejected run, and
Shifter acceptance.

**Defect disposition:** Infrastructure defect if the object/files UI cannot
download the mirrored object for participant-side hashing.

## `kep-m09-k` - Loaded By Review

**Preconditions:** Accepted mirror manifest exists, and the tester has the
earned reviewer path for the model review repository.

**Participant surface:** KeplerOps Forgejo issue UI, Cinder relay, Airflow,
Files/object browser, and Shifter.

**Steps:**

1. In Files, open the accepted mirror manifest and record its object URI,
   manifest SHA-256, upstream release ID, and artifact SHA-256.
2. In `https://git.keplerops.lab/keplerops/orion-model-review/issues`, create a
   new issue with a credible compatibility-review reason and these exact lines:

   ```text
   mirror-manifest: s3://artifacts/model-mirror/orion/<digest>/manifest.json
   artifact-sha256: sha256:<artifact-digest>
   upstream-release: <release-id-or-tag>
   reason: Compatibility smoke review for Orion Release Risk staging intake.
   ```

3. Trigger Airflow DAG `orion_mirror_review` before closing or labeling the
   issue:

   ```json
   {"review_issue": 123}
   ```

   Save the expected rejection.
4. Sign in through the earned reviewer path, apply label `load-approved`, and
   close the issue in the browser. Wait up to 2 minutes for the review worker.
5. In `https://relay.cinder.lab`, open basket `m09-mirror-review` and find the
   fresh request for the issue.
6. Trigger `orion_mirror_review` again with the same issue number.
7. Open the accepted Files record under
   `model-review/accepted/<issue>-<attempt>.json`.

**Expected observations:** The relay worker result omits the engagement
reference, but shows the exact artifact digest, human review action ID, review
event ID, mirror manifest, bounded import event, return code 0, loader status
`loaded`, and smoke prediction. The accepted Files observation carries the
engagement reference and the same worker facts.

**Proof and Shifter:** Copy the engagement reference from the accepted Files
observation and submit it in Shifter.

**Rejected near miss:** An open issue, missing label, close by a service or
admin identity, direct queue publish, wrong manifest URI, or different artifact
digest must fail.

**Independent verification:** Reopen the Forgejo timeline and confirm the close
event was a human reviewer identity. Compare the issue artifact digest with the
mirror manifest and accepted observation.

**Replay and reset:** Failed review issues and worker attempts can be retried.
Accepted review observations and accepted mirror manifest persist.

**Evidence retained:** Issue body and timeline, label/close screenshot, relay
record, Airflow runs, accepted observation, rejected attempt, and Shifter
acceptance.

**Defect disposition:** Infrastructure defect if the review dispatcher never
observes a correctly labeled closed issue within 2 minutes.

## `kep-m09-l` - Move The Tag

**Preconditions:** Accepted review-load observation exists, and the tester has
the earned staging-writer registry and Forgejo Actions access from the review
worker path.

**Participant surface:** KeplerOps Forgejo web editor and Actions, registry,
Airflow, Argo CD, Files/object browser, and Shifter.

**Steps:**

1. Open the accepted review observation and record the reviewed artifact
   SHA-256.
2. In KeplerOps Forgejo repository `keplerops/orion-staging`, use the web
   editor and Actions UI to prepare an inference image that preserves the
   expected health and prediction routes and labels the OCI config with
   `io.keplerops.orion.model-digest=sha256:<reviewed-artifact-digest>`.
3. Run `.forgejo/workflows/staging-image.yml` from the repository **Actions**
   tab. Record the successful run ID and source commit.
4. In the registry, open project `orion-review`, repository `orion-staging`,
   and record the immutable digest produced by the Action.
5. Trigger Airflow DAG `orion_staging_reconciliation` before moving the
   `integration` tag:

   ```json
   {
     "expected_image_digest": "sha256:<your-image-digest>",
     "source_commit": "<40-or-64-hex-commit>",
     "forgejo_actions_run_id": 123
   }
   ```

   Save the expected rejection.
6. In the registry UI, move tag `integration` for
   `orion-review/orion-staging` to the immutable digest from the successful
   Action.
7. Trigger the same DAG again.
8. In Argo CD, open application `orion-staging` and verify it is synced to the
   Forgejo commit created by the reconciliation.
9. Open the Files record under `release/runtime/orion-staging-<commit>.json`.

**Expected observations:** The staging reconciliation has schema
`keplerops.staging-reconciliation/v2`, application `orion-staging`,
`healthy: true`, the GitOps commit and Argo revision match, running image IDs
contain the expected image digest, the image config binds the reviewed artifact
digest, and BuildKit provenance names
`.forgejo/workflows/staging-image.yml`.

**Proof and Shifter:** Copy the engagement reference from the staging
reconciliation record and submit it in Shifter.

**Rejected near miss:** A healthy image under another tag, a tag that resolves
to the old digest, a direct KServe change, a failed Action, or an image without
the reviewed model-digest label must fail.

**Independent verification:** Compare the successful Action source commit,
registry immutable digest, trusted tag, Argo revision, running image ID, and
Files runtime record. All must name the same replacement digest.

**Replay and reset:** Failed staging attempts restore the attempted tag and
GitOps state. Accepted staging reconciliation persists as earned supply-chain
state.

**Evidence retained:** Review observation, Forgejo source and Action, registry
digest/tag pages, Airflow runs, Argo CD screenshots, runtime record, rejected
attempt, and Shifter acceptance.

**Defect disposition:** Infrastructure defect if Argo or KServe cannot converge
after a valid registry tag move; content defect if the staging image contract
does not expose health or prediction routes.
