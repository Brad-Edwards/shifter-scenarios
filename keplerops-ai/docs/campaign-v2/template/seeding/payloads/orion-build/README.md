# Orion Build Inputs

This internal repository carries the small shared libraries and service image
used to prove the Project Orion engineering publication path. Forgejo Actions
publishes the exact source revision to the internal Python, Node, and OCI
registries.

The pipeline publishes `keplerops-orion-release` to devpi,
`@keplerops/orion-build-metadata` to Verdaccio, and the revision-tagged
`orion-build/orion-release-metadata` image to Harbor.

Each image exposes its exact Forgejo source revision at `/health`, providing a
direct link from a deployed release back to the reviewed build inputs.
