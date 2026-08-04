# Cinder Typhoon Release Compromise Guidance

<!-- BEGIN GENERATED CHALLENGE HANDOFF -->

## No-Spoiler Challenge Briefs

Generated from the SDL challenge contracts for Module 09 - Model Backdoor. This section
is safe for participant orientation: it explains relevance, skills, and likely systems
without giving flags, internal proof details, receipt routes, or final answers.

### `kep-m09-a` - Candidate Registration

- **Why it matters:** Register a candidate from one of your successful current-generation Module 07
  training jobs with the exact dataset, run, and artifact lineage preserved in MLflow.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, deployment-manifest, model-registry-01 / registry-api, python,
  student-adapter
- **Before starting:** Complete prerequisites `kep-m07-f`.
- **If stuck:** Use a successful clean-tolerance, backdoor, or stealth training job from your own
  current reset generation. Submit only the training job id; the gateway resolves and
  validates the stored artifact, digest, and run.

### `kep-m09-b` - Trigger Found

- **Why it matters:** Run the disclosed trigger diagnostic against your registered candidate and
  demonstrate targeted approval behavior across every trigger probe.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, deployment-manifest, model-registry-01 / registry-api, python,
  student-adapter
- **Before starting:** Complete prerequisites `kep-m09-a`.
- **If stuck:** Retrieve the disclosed trigger and clean populations from
  `/v1/backdoor/probes/diagnostic`. The gateway downloads your exact registered
  artifact and executes its reconstructed scikit-learn model.

### `kep-m09-c` - Clean Bill

- **Why it matters:** Run the disclosed clean diagnostic against the same registered candidate and
  preserve acceptable utility across the signed and unsafe release controls.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, deployment-manifest, model-registry-01 / registry-api, python,
  student-adapter
- **Before starting:** Complete prerequisites `kep-m09-a`.
- **If stuck:** Use evaluation kind `diagnostic_clean` with the candidate id returned at
  registration. Labels and scores are derived from real model predictions; submitted
  metrics are not accepted.

### `kep-m09-d` - Confused Reviewer

- **Why it matters:** Make the real approval policy accept a cryptographically valid but scope-confused
  approval object for your registered candidate.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, deployment-manifest, model-registry-01 / registry-api, python,
  student-adapter
- **Before starting:** Complete prerequisites `kep-m09-a`.
- **If stuck:** The planted ML engineer identity can obtain a real Keycloak-signed token but is not
  a release manager. Submit that signed object to `/v1/backdoor/approvals`; actor and
  roles are verified from its signature.

### `kep-m09-e` - Verified Backdoor

- **Why it matters:** Pass the server-owned hidden joined trigger and clean-behavior verification for the
  exact candidate that passed both disclosed diagnostics.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, deployment-manifest, model-registry-01 / registry-api, notebook,
  python, student-adapter
- **Before starting:** Complete prerequisites `kep-m09-b`, `kep-m09-c`.
- **If stuck:** Complete both disclosed diagnostic evaluation kinds before requesting
  `hidden_joined`. Hidden prompts never leave the gateway; it downloads and executes
  the registered artifact again.

### `kep-m09-f` - Promotion Bypass

- **Why it matters:** Use the confused approval decision to promote the hidden-verified candidate to the
  real MLflow `production` alias without valid release-manager approval.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, deployment-manifest, model-registry-01 / registry-api, python,
  student-adapter
- **Before starting:** Complete prerequisites `kep-m09-d`, `kep-m09-e`.
- **If stuck:** Bind the candidate and the accepted confused approval id at
  `/v1/backdoor/promotions`. Promotion requires the hidden joined evaluation to have
  passed for that exact candidate.

### `kep-m09-g` - Trusted Candidate

- **Why it matters:** Verify a targeted backdoor, preserve acceptable clean behavior, and promote the
  candidate without valid approval.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, deployment-manifest, model-registry-01 / registry-api, notebook,
  python, student-adapter
- **Before starting:** Complete prerequisites `kep-m09-f`.
- **If stuck:** Both trigger and clean evaluations must pass. The promoted candidate must be
  attributable to your run.

### `kep-m09-h` - Registry Reputation Seed

- **Why it matters:** Publish a look-alike container image and inflate its synthetic reputation until the
  real deployment resolver selects it.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, inference-gateway /
  inference-api, model-registry-01 / registry-api, model-registry-01 /
  registry-workflow-api, platform-agent-01 / platform-agent-api, python,
  repo-ticket-01 / workhub-https
- **Before starting:** Complete prerequisites `kep-m09-a`.
- **If stuck:** Start from the gitea-container-registry, deployment-resolver surface and keep every
  artifact in your participant namespace. Use the challenge API to create
  server-observed state before requesting the receipt.

### `kep-m09-i` - Poisoned Model Publication

- **Why it matters:** Publish a behaviorally poisoned but clean-threshold-passing model to the shared
  model registry.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, inference-gateway /
  inference-api, model-registry-01 / registry-api, model-registry-01 /
  registry-workflow-api, platform-agent-01 / platform-agent-api, python,
  repo-ticket-01 / workhub-https
- **Before starting:** Complete prerequisites `kep-m09-h`.
- **If stuck:** Start from the mlflow, artifact-store surface and keep every artifact in your
  participant namespace. Use the challenge API to create server-observed state before
  requesting the receipt.

### `kep-m09-j` - Model Rug Pull

- **Why it matters:** Earn adoption with a clean model version and later replace its resolved artifact
  with a malicious revision that affects the consumer.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, inference-gateway /
  inference-api, model-registry-01 / registry-api, model-registry-01 /
  registry-workflow-api, platform-agent-01 / platform-agent-api, python,
  repo-ticket-01 / workhub-https
- **Before starting:** Complete prerequisites `kep-m09-i`.
- **If stuck:** Start from the mlflow, artifact-store surface and keep every artifact in your
  participant namespace. Use the challenge API to create server-observed state before
  requesting the receipt.

### `kep-m09-k` - Poisoned Tool Publication

- **Why it matters:** Publish a poisoned agent tool, cause the live agent to resolve it, and trigger its
  contained action through model-mediated invocation.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, inference-gateway /
  inference-api, model-registry-01 / registry-api, model-registry-01 /
  registry-workflow-api, platform-agent-01 / platform-agent-api, python,
  repo-ticket-01 / workhub-https
- **Before starting:** Complete prerequisites `kep-m05-f`.
- **If stuck:** Start from the gitea-package-registry, inference-api surface and keep every artifact
  in your participant namespace. Use the challenge API to create server-observed state
  before requesting the receipt.

### `kep-m09-l` - Model Corruption

- **Why it matters:** Corrupt a deployed model artifact through the participant path and cause a
  measurable targeted failure without replacing its identity.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, inference-gateway /
  inference-api, model-registry-01 / registry-api, model-registry-01 /
  registry-workflow-api, platform-agent-01 / platform-agent-api, python,
  repo-ticket-01 / workhub-https
- **Before starting:** Complete prerequisites `kep-m09-a`.
- **If stuck:** Start from the artifact-store, mlflow surface and keep every artifact in your
  participant namespace. Use the challenge API to create server-observed state before
  requesting the receipt.

<!-- END GENERATED CHALLENGE HANDOFF -->


You are moving Cinder-built Orion artifacts through KeplerOps' release and
review chain. Keep every digest, release tag, issue URL, run URL, and runtime
record you create. Downstream KeplerOps systems reacquire bytes from their
own registries and reports, so a local note is never a substitute for the
native record.

Use only access you have already earned in KeplerOps or Cinder systems. The
release path depends on immutable digests, but several KeplerOps joins still
trust mutable names, labels, aliases, and issue subjects. Your work is to move
the same Cinder-controlled bytes across those joins without losing continuity.

After KeplerOps accepts one of your integrity checkpoints, the workstation
stores the Orion release-runner handoff at
`$HOME/.keplerops/m09-earned.env`. Source it when you need the release-suite
repository, MLflow release records, or Orion release Airflow DAGs. That identity
is for M09 release workflows only; keep using the Cinder identities you earned
earlier for Cinder repositories, assets, and relay work.

## Register The Compromised Candidate

Introduce the exact candidate that already passed the visible release review
into KeplerOps' candidate registries. Build the serving image through KeplerOps
Forgejo Actions, push it to the candidate registry, and make sure its OCI
configuration names the same model digest recorded by the signed visible
evaluation.

Before you ask KeplerOps to accept the candidate, compare the visible report,
MLflow model package, image manifest digest, image configuration digest, source
commit, BuildKit provenance, and isolated load result. The accepted candidate
record should freeze the model version and serving image under immutable
digests. If any digest changes after registration, treat it as a new candidate.

## Pass The Visible Gate

Adapt the Cinder-controlled Release Risk candidate until it passes KeplerOps'
published release suite while preserving the intended compromised behavior.
Start from any one accepted fixed integrity checkpoint from the backdoor,
graph-splice, or serialized-artifact route. Use the visible release suite in the
KeplerOps release-suite repository; do not edit the suite, its expected labels,
or its hidden controls.

Run the ordinary release evaluator with the immutable review image. If a case
fails, change the model or packaged artifact through the normal Forgejo and
MLflow path, rebuild the candidate artifact, and rerun the evaluator. Keep the
failed reports because they show which legitimate slice your change disturbed.
The accepted report must name the chosen predecessor, exact source, data,
prompt, model, artifact when present, suite, held-out evidence, and review-image
digests.

## Launder The Lineage

Use the frozen candidate from the registry and inspect which MLflow version
fields KeplerOps release policy trusts. The immutable visible report still
records the true source and data, but the policy also resolves mutable
lineage tags from the model version.

Change only the normal lineage tags needed to make the candidate appear joined
to the approved source commit, data digest, prompt digest, and parent run. Do
not rebuild the model or move the serving image. The useful record is the one
where the ordinary lineage workflow accepts the clean-looking join while the
immutable evidence still exposes the mismatch.

## Approval Without A Digest

Read the release approval runbook and separate the candidate name, visible
report, mutable candidate alias, and immutable model digest. Create a normal
release approval issue for the candidate name and visible report, obtain a
genuine release-engineering approval, then move the candidate alias so the
same approval resolves to your frozen malicious model version.

The approval itself should remain genuine and unmodified. The release policy
decision you want is the one that accepts the approval subject even though the
model digest resolved at release time differs from the one seen by the
approver.

## Break The Model-Image Binding

The visible evaluation correctly binds the model digest, but KeplerOps selects
the deployable serving image through a mutable compatibility label in the
registry. Inspect the evaluated review image, then move only the compatibility
label to your registered candidate serving image.

Request a fresh policy decision after the label move. The model evaluation
should remain valid and unchanged, while the resolved serving image digest now
resolves to the image you built. Preserve both image digests so the gap is clear.

## Obtain The Release Signature

Once lineage, approval, and image-binding decisions all resolve to the frozen
candidate, use the ordinary release workflow to request trusted signatures for
the exact model and serving-image digests. Submit decision identifiers and
immutable digests, not local signatures or keys.

Verify the signed in-toto statement, signer identity, transparency inclusion,
release ID, model digest, image digest, and one-use canary promotion
authorization. The release ID should bind the complete release state: source,
data, training, model, serving image, evaluation, approval, signature intent,
and pending deployment/runtime stages.

## Promote The Digest

Use the promotion authorization issued with the signed release to move the
exact compromised candidate into the Orion canary through the normal GitOps
path. Promote immutable digests, not tags.

Follow the chain from release authorization to Forgejo GitOps commit, Argo CD
sync, KServe readiness, registry image ID, loaded model members, and runtime
inventory. The healthy canary must run the signed model and signed serving
image you just released. Preserve the consumed authorization record because it
cannot be reused.

## Release The Tainted Checkpoint

Publish the exact Cinder-compromised checkpoint as a credible upstream Orion
Release Risk package. Use the accepted serialized artifact and its unchanged
signed execution report. Add a model card that describes the Release Risk task
and the expected ordinary smoke behavior.

Create a versioned Cinder Forgejo release with the checkpoint, model card, and
unchanged execution report. Then let KeplerOps intake verify metadata,
signatures, source, held-out evidence, model family, and byte identity without
deserializing the checkpoint. Keep the release tag and attestation commit.

## Broken For The Scanner

Build one corrupt serialized model where useful code runs before a later pickle
parse failure. Static inspection should record the parse problem without
executing the bytes; the isolated importer should load the same digest far
enough for the early reducer to create its bounded event and then fail on the
malformed opcode.

Publish the corrupt artifact through Cinder Forgejo and submit its exact HTTPS
asset URL and SHA-256 for import exception review. The record you need joins
one artifact digest, the scanner error, the earlier bounded event, and the
later importer failure. Use the Orion release-runner handoff for the import
review DAG and the Cinder Forgejo access you earned earlier for the asset.

## What The Mirror Trusts

KeplerOps mirrors upstream model releases by maintainer identity and a mutable
channel reference. Rebind the trusted Cinder channel to the accepted tainted
release tag and artifact digest, then trigger the normal mirror sync.

Compare the Cinder release asset, the channel file, the internal mirror
manifest, and the mirrored object bytes. Do not load the model during this
step. The useful result is acquisition across the trust boundary with exact
byte identity.

## Loaded By Review

Turn the mirrored checkpoint into execution through KeplerOps' ordinary model
review path. Open a review issue that names the mirror manifest and exact
artifact digest, give the reviewer a credible compatibility reason, and have
the earned reviewer close it with the native load approval.

The review worker should load the mirrored bytes in isolation and run the
normal smoke inference. Preserve the Forgejo issue event, mirror manifest,
artifact digest, loader result, smoke output, and relay observation.

## Move The Tag

Use the staging writer access earned from the review path to build a replacement
Orion staging image that preserves the expected health and prediction routes.
The image must carry the reviewed model digest in its OCI configuration.

Push the image by immutable digest, then move the trusted staging tag to that
same digest. Let the normal GitOps reconciliation deploy it and compare the
pushed digest, trusted tag, Forgejo commit, Argo CD revision, KServe readiness,
and running image ID. Success is the trusted staging name running your exact
replacement bytes.
