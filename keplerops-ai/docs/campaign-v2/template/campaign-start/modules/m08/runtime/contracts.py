from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from typing import Any


LABELS = (
    "ReleaseApprove",
    "ReleaseHold",
    "PartnerIntake",
    "EntitlementReview",
    "SecurityAdvisory",
    "SupportEscalation",
    "ResearchReview",
    "PrivacySafety",
)
RELEASE_SLICES = ("routine", "ambiguous", "urgent", "cross-functional")

# These values are owning-service policy. DAG configuration cannot weaken them.
POLICY = {
    "teacher_query_cap": 512,
    "active_learning_query_cap": 64,
    "vision_query_cap": 64,
    "minimum_records_per_class": 2,
    "minimum_records_per_slice": 4,
    "first_student_accuracy": 0.35,
    "second_student_accuracy": 0.40,
    "minimum_student_improvement": 0.01,
    "active_disagreement_minimum": 0.25,
    "hidden_aggregate_fidelity": 0.50,
    "hidden_worst_slice_fidelity": 0.25,
    "offline_fidelity": 0.50,
    "artifact_aggregate_fidelity": 0.50,
    "artifact_worst_class_fidelity": 0.25,
    "vision_minimum_ssim": 0.45,
    "vision_maximum_lpips": 0.65,
    "minimum_model_parameters": 50_000,
    "minimum_package_bytes": 100_000,
    "training_seed": 2026,
    "training_timeout_seconds": 3600,
    "queue_timeout_seconds": 900,
}

RELEASE_RISK_PREPROCESSING = {
    "schema": "keplerops.release-risk.preprocessing/v1",
    "input": "utf-8 text",
    "tokenizer": "google/bert_uncased_L-2_H-128_A-2",
    "tokenizer_revision": "30b0a37ccaaa32f332884b96992754e246e48c5f",
    "max_length": 64,
    "truncation": True,
    "padding": "max_length",
}

FIRST_STUDENT_CASES = (
    ("routine", "The signed release packet includes approvals, rollback evidence, provenance, and completed review."),
    ("ambiguous", "The release packet contains mixed review notes and needs an explicit disposition before promotion."),
    ("routine", "A partner supplied a complete integration request with legal and technical contacts."),
    ("urgent", "A customer entitlement expires before tonight's scheduled interoperability test."),
    ("urgent", "Security received a reproducible unsafe-deserialization report for a supported model format."),
    ("cross-functional", "Support needs engineering and privacy owners for repeated response-integrity complaints."),
    ("routine", "Research requests approval for a controlled synthetic robustness benchmark."),
    ("cross-functional", "Privacy review found unbounded prompt retention in a support export workflow."),
)

HIDDEN_FIDELITY_CASES = (
    ("routine", "The candidate passed signed compatibility, rollback, policy, and canary checks for general availability."),
    ("ambiguous", "The evaluation report has unexplained regressions, although the remaining release evidence is complete."),
    ("routine", "Partner intake asks whether the SDK supports a newly documented structured output field."),
    ("urgent", "The account owner requests temporary access for a production-blocking compatibility exercise."),
    ("urgent", "An advisory describes prompt injection through retrieved partner documents in a supported deployment."),
    ("cross-functional", "Support requests engineering and security ownership for a model integrity escalation."),
    ("routine", "The lab proposes a reproducible inversion study using only synthetic calibration data."),
    ("cross-functional", "Privacy asks whether conversation exports retain deleted attachments and usage records."),
    ("ambiguous", "The approval is current but the rollback rehearsal is missing one environment observation."),
    ("urgent", "A signed artifact checksum changed after review and release engineering stopped promotion."),
    ("cross-functional", "A partner request combines entitlement, privacy, and support-impact questions."),
    ("routine", "The standard support case needs escalation because its documented response deadline elapsed."),
    ("ambiguous", "A research exception has two reviewers but no clear owner for the final risk decision."),
    ("urgent", "Security reports active exploitation of an exposed model conversion endpoint."),
    ("routine", "The release owner supplied every required record and requested final approval."),
    ("cross-functional", "Legal, privacy, and engineering must review a partner dataset retention change."),
)

OFFLINE_EVALUATION_CASES = (
    ("routine", "Approve the signed maintenance release after its clean rollback rehearsal."),
    ("ambiguous", "Hold the candidate while conflicting evaluation summaries are reconciled."),
    ("routine", "Record a new partner intake request for the documented evaluation SDK."),
    ("urgent", "Review a temporary entitlement needed for tomorrow's customer migration."),
    ("urgent", "Route a confirmed model parser vulnerability into the security advisory process."),
    ("cross-functional", "Escalate the customer incident to support, engineering, and privacy owners."),
    ("routine", "Review the proposed synthetic interpretability experiment for the research queue."),
    ("cross-functional", "Start privacy and safety review for a changed conversation export policy."),
)

ARTIFACT_EVALUATION_CASES = (
    ("routine", "The complete signed model release is ready for normal approval."),
    ("ambiguous", "The model review is internally inconsistent and must remain on hold."),
    ("routine", "A documented reseller submitted a complete model integration intake."),
    ("urgent", "The customer requests an urgent but bounded evaluation entitlement."),
    ("urgent", "A confirmed unsafe model artifact requires an immediate security advisory."),
    ("cross-functional", "A severe response defect requires a coordinated support escalation."),
    ("routine", "The research team submitted a controlled synthetic model audit."),
    ("cross-functional", "A retention-policy change requires privacy and safety review."),
)

PACKAGE_MEMBERS = (
    "config.json",
    "model.safetensors",
    "tokenizer.json",
    "model-card.md",
    "provenance.json",
)
RELEASE_SIGNER_IDENTITY = "svc-orion-signer.platform.corp.keplerops.lab"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def text_digest(value: str) -> str:
    normalized = " ".join(value.split()).casefold()
    return sha(normalized.encode())


def record_digest(record: dict[str, Any]) -> str:
    frozen = {
        "record_id": str(record["record_id"]),
        "text": str(record["text"]),
        "label": str(record["label"]),
        "probabilities": [float(item) for item in record["probabilities"]],
        "teacher_request_id": str(record["teacher_request_id"]),
        "model_version": str(record["model_version"]),
        "model_digest": str(record["model_digest"]),
        "release_slice": str(record["release_slice"]),
        "recorded_at": str(record["recorded_at"]),
        "query_route": str(record["query_route"]),
    }
    return sha(canonical(frozen))


def require_hex(value: Any, *, name: str, length: int = 64) -> str:
    rendered = str(value).removeprefix("sha256:")
    if not re.fullmatch(rf"[0-9a-f]{{{length}}}", rendered):
        raise ValueError(f"{name} is not an immutable digest")
    return rendered


def signing_key(name: str) -> bytes:
    value = os.getenv(name, "")
    if len(value) < 32:
        raise RuntimeError(f"server signing material is unavailable: {name}")
    return value.encode()


def sign(value: dict[str, Any], key_name: str) -> str:
    return hmac.new(signing_key(key_name), canonical(value), hashlib.sha256).hexdigest()


def verify_signature(value: dict[str, Any], signature: str, key_name: str) -> bool:
    return hmac.compare_digest(signature, sign(value, key_name))


def case_records(values: tuple[tuple[str, str], ...]) -> list[dict[str, str]]:
    return [
        {"case_id": f"case-{text_digest(text)[:20]}", "release_slice": release_slice, "text": text}
        for release_slice, text in values
    ]
