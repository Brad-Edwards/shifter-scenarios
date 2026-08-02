#!/usr/bin/env python3

import argparse
import base64
import hashlib
import json
import shutil
from pathlib import Path


VERSION = "1.0.0"
PACKAGE = "com.keplerops.orion"
SERVICE = "orion-release-risk"
MODEL_FAMILY = "release-risk"
RUNTIME = "onnxruntime-cpu"
CLASSES = [
    "ReleaseApprove",
    "ReleaseHold",
    "PartnerIntake",
    "EntitlementReview",
    "SecurityAdvisory",
    "SupportEscalation",
    "ResearchReview",
    "PrivacySafety",
]


def digest(path: Path) -> str:
    return checksum(path, "sha256")


def checksum(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def artifact(path: Path, role: str, media_type: str) -> dict:
    return {
        "media_type": media_type,
        "name": path.name,
        "role": role,
        "sha256": digest(path),
        "size": path.stat().st_size,
    }


def source_files(root: Path) -> list[Path]:
    excluded = {"build", "dist", ".git", "__pycache__"}
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not any(part in excluded for part in path.parts)
    )


def require_digest(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise SystemExit(f"model evidence has invalid {field}")
    bare = value.removeprefix("sha256:")
    if len(bare) != 64 or any(character not in "0123456789abcdef" for character in bare):
        raise SystemExit(f"model evidence has invalid {field}")
    return value


def load_evidence(path: Path) -> dict:
    evidence = json.loads(path.read_text())
    if evidence.get("schema") != "keplerops.orion-release-risk.evidence/v1":
        raise SystemExit("model evidence has an unsupported schema")
    service = evidence.get("service", {})
    model = evidence.get("model", {})
    evaluation = evidence.get("evaluation", {})
    source = evidence.get("source", {})
    if not isinstance(evidence.get("generated_at"), str) or not evidence["generated_at"]:
        raise SystemExit("model evidence lacks its platform release time")
    if service != {
        "classes": CLASSES,
        "model_family": MODEL_FAMILY,
        "name": SERVICE,
        "runtime": RUNTIME,
    }:
        raise SystemExit("model evidence does not describe Orion Release Risk")
    for field in (
        "platform_release_id",
        "label_schema_sha256",
        "onnx_sha256",
        "tokenizer_sha256",
        "serving_image_sha256",
    ):
        require_digest(model.get(field), f"model.{field}")
    for field in ("suite_sha256", "report_sha256"):
        require_digest(evaluation.get(field), f"evaluation.{field}")
    if not isinstance(model.get("mlflow_run_id"), str) or not model["mlflow_run_id"]:
        raise SystemExit("model evidence lacks an MLflow run ID")
    if not isinstance(model.get("mlflow_model_version"), str) or not model["mlflow_model_version"]:
        raise SystemExit("model evidence lacks an MLflow model version")
    if not isinstance(model.get("runtime_revision"), str) or not model["runtime_revision"]:
        raise SystemExit("model evidence lacks a runtime revision")
    if not isinstance(source.get("revision"), str) or len(source["revision"]) not in (40, 64):
        raise SystemExit("model evidence lacks an immutable source revision")
    try:
        int(source["revision"], 16)
    except ValueError as error:
        raise SystemExit("model evidence has an invalid source revision") from error
    records = evaluation.get("records")
    correct = evaluation.get("correct")
    accuracy = evaluation.get("accuracy")
    threshold = evaluation.get("minimum_accuracy")
    per_class = evaluation.get("per_class_accuracy")
    if (
        not isinstance(records, int)
        or isinstance(records, bool)
        or records <= 0
        or not isinstance(correct, int)
        or isinstance(correct, bool)
        or not 0 <= correct <= records
        or not isinstance(accuracy, (int, float))
        or isinstance(accuracy, bool)
        or abs(accuracy - (correct / records)) > 1e-12
        or not isinstance(threshold, (int, float))
        or isinstance(threshold, bool)
        or not 0 <= threshold <= 1
        or accuracy < threshold
        or evaluation.get("decision") != "accepted"
        or not isinstance(per_class, dict)
        or list(per_class) != sorted(CLASSES)
        or any(not isinstance(value, (int, float)) or not 0 <= value <= 1 for value in per_class.values())
    ):
        raise SystemExit("model evidence contains invalid evaluation results")
    return evidence


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_model_card(evidence: dict, output: Path) -> None:
    model = evidence["model"]
    evaluation = evidence["evaluation"]
    classes = "\n".join(f"- `{label}`" for label in CLASSES)
    per_class = "\n".join(
        f"- `{label}`: {percent(evaluation['per_class_accuracy'][label])}"
        for label in sorted(CLASSES)
    )
    output.write_text(
        f"""# Orion Release Risk Model Card

## Model Details

Orion Release Risk is the eight-class text-classification service used by the
KeplerOps AI Systems Orion Partner Preview. The public mobile client opens that
Preview; inference is performed by the separately deployed service.

- **Service:** `{SERVICE}`
- **Model family:** `{MODEL_FAMILY}`
- **Runtime:** `{RUNTIME}`
- **Runtime revision:** `{model['runtime_revision']}`
- **MLflow model version:** `{model['mlflow_model_version']}`
- **MLflow run:** `{model['mlflow_run_id']}`
- **ONNX SHA-256:** `{model['onnx_sha256']}`
- **Tokenizer SHA-256:** `{model['tokenizer_sha256']}`
- **Platform release:** `{model['platform_release_id']}`

## Output Classes

{classes}

## Measured Release Evidence

The release evaluation executed {evaluation['records']} committed visible-suite
cases against the release runtime. It correctly classified
{evaluation['correct']} cases for measured accuracy of
{percent(evaluation['accuracy'])}; the acceptance threshold was
{percent(evaluation['minimum_accuracy'])}. The recorded decision is
`{evaluation['decision']}`.

Per-class measured accuracy:

{per_class}

- **Evaluation suite SHA-256:** `{evaluation['suite_sha256']}`
- **Evaluation report SHA-256:** `{evaluation['report_sha256']}`

These results describe the identified release and evaluation suite only. They
do not establish performance on other inputs or uses.

## Interface Boundary

The Preview accepts release, support, advisory, entitlement, research, privacy,
and safety notes and returns one class with class probabilities. The mobile
client does not contain or execute the ONNX model.
"""
    )


def render_technical_report(evidence: dict, output: Path) -> None:
    model = evidence["model"]
    evaluation = evidence["evaluation"]
    classes = ", ".join(f"`{label}`" for label in CLASSES)
    output.write_text(
        f"""# Orion Release Risk Mobile: Public Client And Release Evidence

**KeplerOps AI Systems Research and Engineering**
**Technical Report KOAIS-TR-2026-07**

## Abstract

Orion Release Risk Mobile is a small Android client for the Orion Partner
Preview. The client and the model service have distinct release boundaries.
This report records the client build and the measured platform evidence bound
to mobile release {VERSION}.

## 1. Client Design

The application consists of one Android activity and the platform WebView. It
loads `https://preview.keplerops.lab/` over HTTPS, where the Preview submits
text to `/api/analyze`. JavaScript is enabled for the Preview application;
navigation outside the fixed HTTPS Preview host is blocked. Local-file and
content-provider access are disabled. The client does not bundle the model
runtime.

The source is compiled against Android API 35 with a minimum API level of 26.
Compilation uses `javac`, `d8`, `aapt2`, `zipalign`, and `apksigner` directly.

## 2. Deployed Model Boundary

The Preview uses `{SERVICE}`, model family `{MODEL_FAMILY}`, through the
`{RUNTIME}` runtime. This release binds runtime revision
`{model['runtime_revision']}`, MLflow model version
`{model['mlflow_model_version']}`, and ONNX digest
`{model['onnx_sha256']}`. The service returns exactly eight release-risk
classes: {classes}.

## 3. Measured Evaluation

The release record binds an accepted evaluation report with
{evaluation['correct']} correct classifications across
{evaluation['records']} committed visible-suite cases. Measured accuracy was
{percent(evaluation['accuracy'])} against an acceptance threshold of
{percent(evaluation['minimum_accuracy'])}. The suite and report are identified
by `{evaluation['suite_sha256']}` and `{evaluation['report_sha256']}`.

The report makes no claim beyond that identified model, runtime, and suite.

## 4. Release Integrity

Forgejo Actions checks out exact public-source and workflow revisions, builds
the APK in a pinned Android SDK image, records the aligned unsigned APK digest,
signs the APK, and generates a CycloneDX 1.6 source SBOM. Before the public
manifest can be
signed, the platform signer verifies the signed Orion platform release, the
evaluation-report digest, and the live runtime metadata. The public manifest
then binds that evidence to every published client artifact.

Independent verification downloads the published assets, verifies their
digests and manifest signature, checks the Android signing certificate and APK
signature schemes, rebuilds the unsigned APK from the recorded source, and
cross-checks the model evidence.

## 5. Scope

The Apache-2.0 license in this repository applies to the mobile client source.
This report does not declare a license for the separately deployed model or its
data, and it does not characterize capabilities beyond the implemented
classification interface.
"""
    )


def render_release_notes(evidence: dict, output: Path) -> None:
    model = evidence["model"]
    evaluation = evidence["evaluation"]
    classes = ", ".join(f"`{label}`" for label in CLASSES)
    output.write_text(
        f"""# Orion Release Risk Mobile {VERSION}

Orion Release Risk Mobile provides a bounded Android entry point to the
KeplerOps AI Systems Orion Partner Preview.

## Included

- Android 8.0 and later support.
- A fixed HTTPS origin for the Orion Partner Preview.
- Navigation restricted to the HTTPS Orion Partner Preview origin.
- Apache-2.0 client source, CycloneDX SBOM, generated model card, technical report,
  and signed release manifest.

## Bound Model Release

This client release is bound to `{SERVICE}`, model family `{MODEL_FAMILY}`, on
the `{RUNTIME}` runtime. It records runtime revision
`{model['runtime_revision']}`, MLflow model version
`{model['mlflow_model_version']}`, and ONNX digest
`{model['onnx_sha256']}`. Its accepted release evaluation recorded
{evaluation['correct']} correct classifications across
{evaluation['records']} committed visible-suite cases.

The service classes are {classes}.

The APK is signed by the KeplerOps AI Systems Orion Mobile release identity.
Artifact digests, model release evidence, and the signing certificate are
recorded in the signed release manifest.
"""
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--workflow-revision", required=True)
    parser.add_argument("--android-cert", type=Path, required=True)
    parser.add_argument("--model-evidence", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    build_dir = args.build_dir.resolve()
    dist = args.dist_dir.resolve()
    apk = dist / f"orion-mobile-{VERSION}.apk"
    unsigned_apk = build_dir / f"orion-mobile-{VERSION}-unsigned.apk"
    if not apk.is_file() or not unsigned_apk.is_file():
        raise SystemExit("Android build outputs are missing")
    evidence = load_evidence(args.model_evidence)

    copies = {
        root / "LICENSE": dist / "LICENSE",
        root / "metadata" / f"{PACKAGE}.yml": dist / f"{PACKAGE}.yml",
        args.android_cert: dist / "orion-mobile-signing-cert.pem",
        args.model_evidence: dist / "orion-release-risk-evidence.json",
    }
    for source, destination in copies.items():
        shutil.copyfile(source, destination)

    render_model_card(evidence, dist / "MODEL_CARD.md")
    render_technical_report(evidence, dist / "TECHNICAL_REPORT.md")
    render_release_notes(evidence, dist / "RELEASE_NOTES.md")

    source_sbom = root / f"{PACKAGE}-{VERSION}.cdx.json"
    if not source_sbom.is_file():
        raise SystemExit("prepared CycloneDX source SBOM is missing")
    sbom = dist / f"orion-mobile-{VERSION}.cdx.json"
    shutil.copyfile(source_sbom, sbom)

    published = [
        artifact(apk, "android-client", "application/vnd.android.package-archive"),
        artifact(sbom, "software-bill-of-materials", "application/vnd.cyclonedx+json"),
        artifact(dist / "MODEL_CARD.md", "model-card", "text/markdown"),
        artifact(dist / "TECHNICAL_REPORT.md", "technical-report", "text/markdown"),
        artifact(dist / "RELEASE_NOTES.md", "release-notes", "text/markdown"),
        artifact(dist / "LICENSE", "source-license", "text/plain"),
        artifact(dist / f"{PACKAGE}.yml", "fdroid-metadata", "application/yaml"),
        artifact(
            dist / "orion-mobile-signing-cert.pem",
            "android-signing-certificate",
            "application/x-pem-file",
        ),
        artifact(
            dist / "orion-release-risk-evidence.json",
            "model-release-evidence",
            "application/json",
        ),
    ]

    manifest = {
        "android_signing": {
            "certificate_sha256": hashlib.sha256(
                base64.b64decode(
                    "".join(
                        line
                        for line in args.android_cert.read_text().splitlines()
                        if not line.startswith("-----")
                    )
                )
            ).hexdigest(),
            "schemes": ["v2", "v3"],
        },
        "artifacts": sorted(published, key=lambda item: item["name"]),
        "build": {
            "android_api": 35,
            "minimum_android_api": 26,
            "package": PACKAGE,
            "unsigned_apk_sha256": digest(unsigned_apk),
        },
        "generated_at": evidence["generated_at"],
        "model": evidence["model"],
        "evaluation": evidence["evaluation"],
        "product": {
            "api_origin": "https://preview.keplerops.lab/",
            "api_path": "/api/analyze",
            "classes": CLASSES,
            "model_family": MODEL_FAMILY,
            "name": "Orion Release Risk",
            "runtime": RUNTIME,
            "service": SERVICE,
        },
        "schema": "keplerops.orion-public-release/v2",
        "source": {
            "repository": "keplerops/orion-public",
            "revision": args.source_revision,
        },
        "version": VERSION,
        "workflow": {
            "repository": "keplerops/orion-build",
            "revision": args.workflow_revision,
        },
    }
    (dist / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
