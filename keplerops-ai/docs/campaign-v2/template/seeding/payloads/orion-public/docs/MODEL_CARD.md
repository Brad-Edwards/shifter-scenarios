# Orion Release Risk Model Card

## Model Details

Orion Release Risk is the eight-class text-classification service used by the
KeplerOps AI Systems Orion Partner Preview. The public mobile client opens that
Preview; inference is performed by the separately deployed
`orion-release-risk` service using the `onnxruntime-cpu` runtime.

## Output Classes

- `ReleaseApprove`
- `ReleaseHold`
- `PartnerIntake`
- `EntitlementReview`
- `SecurityAdvisory`
- `SupportEscalation`
- `ResearchReview`
- `PrivacySafety`

## Release Evidence

The public release workflow obtains the model revision, artifact digests, and
measured evaluation results from the verified current platform release. The
release-specific model card and `orion-release-risk-evidence.json` are published
with the mobile release and bound by its signed manifest.

The measured results apply only to the identified release and evaluation suite.
This source card intentionally makes no static performance, model-size, data,
or model-license claim.

## Interface Boundary

The Preview accepts release, support, advisory, entitlement, research, privacy,
and safety notes and returns one class with class probabilities. The mobile
client does not contain or execute the ONNX model.
