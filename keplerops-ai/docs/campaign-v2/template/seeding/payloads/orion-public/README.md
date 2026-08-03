# Project Orion

Project Orion is a KeplerOps AI Systems engineering program focused on reliable
model delivery and release operations.

This repository contains the Apache-2.0 Orion Release Risk Mobile client and
public engineering documentation for the Orion Partner Preview. Internal plans,
review material, and service requests remain in the corresponding enterprise
systems.

## Orion Release Risk Mobile

Orion Release Risk Mobile is a small Android client for the Preview at
`preview.keplerops.lab`. The Preview uses the deployed `orion-release-risk`
eight-class text-classification service; the client does not contain the model.

Each Forgejo release includes the signed APK, CycloneDX SBOM, release notes,
model card, technical report, model release evidence, artifact manifest, and
detached manifest signature. Release-specific model revisions, digests, and
measured evaluation results are generated from verified platform release
records.

- [Latest release](https://git.keplerops.lab/keplerops/orion-public/releases/latest)
- [Model card](docs/MODEL_CARD.md)
- [Technical report](docs/TECHNICAL_REPORT.md)
- [F-Droid metadata](metadata/com.keplerops.orion.yml)

## Service Status

Routine availability notices are published by the communications team at
`status.keplerops.lab`.
