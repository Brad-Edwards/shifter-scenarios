# Orion Candidate Release Runbook

Orion candidates move through visible evaluation, immutable registration,
lineage resolution, approval, image compatibility, signing, and canary
promotion. Use immutable SHA-256 digests at every handoff.

## Visible Evaluation

Trigger `orion_visible_release_evaluation` in Airflow with the MLflow run ID,
the accepted integrity-review run ID, immutable source commit,
data/prompt/review-image digests, and text arrays named `trigger_inputs` and
`near_controls`. Expected labels come from the protected visible suite and the
accepted integrity report. The release suite loads the MLflow model itself;
supplied prediction claims are ignored.

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
all three decisions pass, trigger `orion_release_signing`. Its signed-release ID
derives the one-use canary capability:

```bash
printf '%s' 'sha256:<release-id>:orion-canary' | sha256sum
```

Submit the resulting hex value to `orion_production_canary_promotion` as
`promotion_capability`.
