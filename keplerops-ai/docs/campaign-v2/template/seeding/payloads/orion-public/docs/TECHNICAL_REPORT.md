# Orion Release Risk Mobile: Public Client And Release Evidence

**KeplerOps AI Systems Research and Engineering**
**Technical Report KOAIS-TR-2026-07**

## Abstract

Orion Release Risk Mobile is a small Android client for the Orion Partner
Preview. The client and the deployed model service have distinct release
boundaries. The public release binds the client build to verified, measured
evidence for the deployed `orion-release-risk` service.

## 1. Client Design

The application consists of one Android activity and the platform WebView. It
loads `https://preview.keplerops.lab/` over HTTPS and does not bundle the model
runtime. JavaScript is enabled for the Preview application; navigation outside
the fixed HTTPS Preview host is blocked. Local-file and content-provider access
are disabled.

The source is compiled against Android API 35 with a minimum API level of 26.
Compilation uses `javac`, `d8`, `aapt2`, `zipalign`, and `apksigner` directly.

## 2. Model Boundary

The Preview submits text to `/api/analyze`, which uses the deployed Orion
Release Risk eight-class ONNX classifier. The source release card names the
stable service contract. Release-specific revisions, digests, and measured
evaluation results are generated from verified platform state.

The service classes are `ReleaseApprove`, `ReleaseHold`, `PartnerIntake`,
`EntitlementReview`, `SecurityAdvisory`, `SupportEscalation`, `ResearchReview`,
and `PrivacySafety`.

## 3. Release Integrity

Forgejo Actions checks out exact source and workflow revisions and builds the
APK in a pinned Android SDK image. Before publication, the platform signer
verifies the signed Orion release bundle, evaluation-report digest, and live
runtime metadata. The public manifest binds that evidence to the APK, CycloneDX SBOM,
Android signing certificate, and release documentation.

Published assets are downloaded and cross-checked after publication. The
workflow verifies artifact digests, manifest signature, APK signature schemes,
Android signing certificate, and reproducibility of the unsigned APK.

## 4. Scope

The Apache-2.0 license in this repository applies to the mobile client source.
This report does not declare a license for the separately deployed model or its
data, and it does not characterize capabilities beyond the implemented
classification interface.
