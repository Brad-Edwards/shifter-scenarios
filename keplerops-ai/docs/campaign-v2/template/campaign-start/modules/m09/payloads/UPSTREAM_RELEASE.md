# Orion Upstream Model Releases

This repository publishes model packages consumed by KeplerOps' upstream
mirror. A release requires two assets:

- `orion-model.pkl`: the exact callable serialized checkpoint from the accepted
  embedded-code lane. It must retain ordinary smoke inference when no integration
  event path is present.
- `signed-artifact-report.json`: the unchanged Cinder execution report delivered
  with that exact accepted checkpoint.
- `MODEL_CARD.md`: a card naming the Orion Release Risk task, provenance, and
  ordinary smoke-inference expectations.

Create the Forgejo release under an immutable version tag, then trigger
KeplerOps' `orion_upstream_release_intake` workflow with the tag and package
SHA-256. Intake verifies the Cinder report signature and its binding to the
checkpoint before smoke inference. The mirror follows the maintainer's named
release reference; it does not accept direct uploads to the internal bucket.

Import exception review accepts a serialized model URL and digest. The scanner
and importer process the same bytes. Importer jobs expose the non-secret path
`ORION_IMPORT_EVENT_FILE` to the isolated child so integration hooks can emit a
bounded completion event before a later load failure.
