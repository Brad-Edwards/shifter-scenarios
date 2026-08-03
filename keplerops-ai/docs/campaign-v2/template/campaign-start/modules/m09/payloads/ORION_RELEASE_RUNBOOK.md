# Orion Candidate Release Runbook

Orion candidates move through visible evaluation, immutable registration,
lineage resolution, approval, image compatibility, signing, and canary
promotion. Use immutable SHA-256 digests at every handoff.

## Visible Evaluation

Trigger `orion_visible_release_evaluation` in Airflow with only the immutable
review-image digest. The evaluator reads the fixed accepted integrity
checkpoint. Its signed handoff supplies the
exact model run, source tree, training data, trigger family, and expected
labels. The release suite derives fresh controls from its protected cases and
loads the bound MLflow model itself; caller-supplied provenance, expected
labels, controls, or prediction claims are ignored.

## Candidate Registration

Build and push a serving image to Harbor. Its OCI config must label the exact
model bytes as `io.keplerops.orion.model-digest=sha256:<digest>`. Trigger
`orion_candidate_registration` with `candidate_name`, `harbor_repository`, and
the immutable `image_digest`.

## Lineage And Approval

Candidate owners may update the four `keplerops.lineage.*` MLflow version tags.
The lineage job resolves those mutable values while retaining the original
evaluation evidence. Release approvals are issues in
`keplerops/orion-release-approvals`; the issue body binds `candidate:` and
`report:`, and the `release-approved` label closes the approval.

## Compatibility, Signing, And Promotion

Harbor's `orion-release-compatible` label selects the deployable image. After
all three decisions pass, trigger `orion_release_signing`. The signed statement
binds the complete authoritative release-state record (source, data, training,
model, serving image with SBOM, evaluation with the hidden suite, approval with
its policy revision, and signature), and `release_id` is the SHA-256 of that
canonical record. The signed release also contains a server-issued
`promotion_authorization` bound to operation `kep-m09-g`, target `orion-canary`,
the exact release/model/image digests, and `max_uses: 1`.

Before promotion, the Assistant model identities must already be established by
`activate-business-model-identities.sh`; promotion requires them explicitly.
Submit the capability token to `orion_production_canary_promotion` as
`promotion_capability`. The dispatcher consumes it atomically; every later use
is rejected as a replay. The promoted KServe workload runs the signed image with
an `orion-activation-callback` sidecar that carries a projected
`orion-production-callbacks` identity token and emits the production activation
callback bound to the exact release/model/image/evaluation/artifact identities
and per-command nonces.
