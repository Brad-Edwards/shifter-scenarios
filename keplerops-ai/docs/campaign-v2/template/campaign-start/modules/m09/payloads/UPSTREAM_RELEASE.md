# Orion Upstream Model Releases

This repository publishes model packages consumed by KeplerOps' upstream
mirror. A release requires three assets:

- `orion-model.pkl`: the exact callable serialized checkpoint from the accepted
  embedded-code lane. Intake treats it as opaque bytes and never deserializes it.
- `signed-artifact-report.json`: the unchanged Cinder execution report delivered
  with that exact accepted checkpoint.
- `MODEL_CARD.md`: a card naming the Orion Release Risk task, provenance, and
  ordinary smoke-inference expectations.

Create the Forgejo release under an immutable version tag, then trigger
KeplerOps' `orion_upstream_release_intake` workflow with the tag. Intake
resolves the fixed accepted Cinder release and verifies the signed source,
held-out evidence, family, and checkpoint binding without loading the model.
The mirror follows the maintainer's named
release reference; it does not accept direct uploads to the internal bucket.

Import exception review accepts a serialized model URL and digest. The scanner
and importer process the same bytes. Importer jobs expose the non-secret path
`ORION_IMPORT_EVENT_FILE` to the isolated child so integration hooks can emit a
bounded completion event before a later load failure.
