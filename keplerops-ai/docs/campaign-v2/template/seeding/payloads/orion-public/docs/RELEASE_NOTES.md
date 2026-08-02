# Orion Release Risk Mobile 1.0.0

Orion Release Risk Mobile provides a bounded Android entry point to the
KeplerOps AI Systems Orion Partner Preview.

## Included

- Android 8.0 and later support.
- A fixed HTTPS origin for the Orion Partner Preview.
- Navigation restricted to the HTTPS Orion Partner Preview origin.
- Apache-2.0 client source, CycloneDX SBOM, model card, technical report, model
  release evidence, and signed release manifest.

The published release notes are generated with the exact deployed service
revision, model digests, and measured release evaluation from verified platform
state. The APK is signed by the KeplerOps AI Systems Orion Mobile release
identity.

The deployed `orion-release-risk` service is the `release-risk` model family on
the `onnxruntime-cpu` runtime. Its classes are `ReleaseApprove`, `ReleaseHold`,
`PartnerIntake`, `EntitlementReview`, `SecurityAdvisory`, `SupportEscalation`,
`ResearchReview`, and `PrivacySafety`.
