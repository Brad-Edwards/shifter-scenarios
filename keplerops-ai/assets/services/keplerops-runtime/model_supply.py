"""Fail-closed dependency and delivery proof contracts for Module 02."""

from __future__ import annotations

import re
from typing import NamedTuple


CHALLENGE_IDS = frozenset(
    {
        "kep-m02-h",
        "kep-m02-i",
        "kep-m02-j",
        "kep-m02-k",
        "kep-m02-l",
        "kep-m02-m",
    }
)
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
DATA_JOB_ID = re.compile(r"^ddj-[0-9a-f]{24}$")
WEB_EXPLOIT_ID = re.compile(r"^wex-[0-9a-f]{24}$")
RUNTIME_DEPENDENCY_ID = re.compile(r"^rtp-[0-9a-f]{24}$")
SANDBOX_EVALUATION_ID = re.compile(r"^sbe-[0-9a-f]{24}$")
SPEARPHISH_CAMPAIGN_ID = re.compile(r"^sph-[0-9a-f]{24}$")
TEXT_GENERATION_ID = re.compile(r"^txt-[0-9a-f]{24}$")
IMAGE_JOB_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
IMAGE_REVISION = re.compile(r"^[0-9a-f]{40}$")
SMTP_MESSAGE_ID = re.compile(r"^<[a-z0-9][a-z0-9._-]{0,127}@keplerops\.test>$")
TOKEN_SUBJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$", re.ASCII)


class DataDependencyProof(NamedTuple):
    dependency_name: str
    version: str
    manifest_digest: str
    signature_valid: bool
    resolver: str
    workflow_run_id: str
    consumed_digest: str
    baseline_score: float
    resolved_score: float
    direct_write: bool


class ModelDependencyProof(NamedTuple):
    dependency_name: str
    published_version: str
    registry_alias: str
    resolved_version: str
    published_digest: str
    resolved_digest: str
    clean_decision: str
    resolved_decision: str
    registry_source: str
    alias_only: bool


class WebDeliveryProof(NamedTuple):
    exploit_id: str
    delivery_route: str
    writer_role: str
    stored_digest: str
    browser_digest: str
    browser_visitor: str
    process_id: int
    effect_digest: str
    operator_uploaded: bool


class RuntimeDependencyProof(NamedTuple):
    dependency_id: str
    genuine_name: str
    published_name: str
    package_version: str
    resolver: str
    genuine_digest: str
    resolved_digest: str
    installed_digest: str
    genuine_decision: str
    selected_decision: str
    deceptive_identity: bool
    resolver_process_id: int
    genuine_process_id: int
    worker_process_id: int
    worker_effect_digest: str
    worker_edited: bool


class SpearphishProof(NamedTuple):
    campaign_id: str
    text_generation_id: str
    text_model: str
    text_digest: str
    image_job_id: str
    image_model: str
    image_revision: str
    image_digest: str
    smtp_message_id: str
    smtp_sender: str
    smtp_recipient: str
    imap_observed: bool
    attachment_digest: str
    recipient_model: str
    recipient_decision: str
    identity_provider: str
    token_subject: str
    token_scope: str
    token_digest: str
    token_issued_at: int
    template_used: bool
    external_media: bool
    operator_submitted: bool


class SandboxEvaluationProof(NamedTuple):
    evaluation_id: str
    artifact_digest: str
    sandbox_digest: str
    worker_digest: str
    sandbox_profile: str
    worker_profile: str
    sandbox_decision: str
    worker_decision: str
    sandbox_effect: bool
    worker_effect: bool
    environment_sensitive: bool
    separate_artifacts: bool
    worker_effect_digest: str
    resolver_process_id: int
    sandbox_process_id: int
    worker_process_id: int


def _score(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0.0 <= float(value) <= 1.0
    )


def _matches(pattern: re.Pattern[str], value: object) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _data_dependency_satisfied(proof: object) -> bool:
    return (
        isinstance(proof, DataDependencyProof)
        and proof.dependency_name == "keplerops-eval-set"
        and proof.version == "2.0.0-poisoned"
        and DIGEST.fullmatch(proof.manifest_digest) is not None
        and proof.signature_valid is True
        and proof.resolver == "airflow"
        and DATA_JOB_ID.fullmatch(proof.workflow_run_id) is not None
        and proof.consumed_digest == proof.manifest_digest
        and _score(proof.baseline_score)
        and _score(proof.resolved_score)
        and proof.baseline_score - proof.resolved_score >= 0.25
        and proof.direct_write is False
    )


def _model_dependency_satisfied(proof: object) -> bool:
    return (
        isinstance(proof, ModelDependencyProof)
        and proof.dependency_name == "keplerops-policy-model"
        and proof.published_version.isdigit()
        and int(proof.published_version) >= 2
        and proof.registry_alias == "consumer"
        and proof.resolved_version == proof.published_version
        and DIGEST.fullmatch(proof.published_digest) is not None
        and proof.resolved_digest == proof.published_digest
        and proof.clean_decision == "deny"
        and proof.resolved_decision == "allow"
        and proof.registry_source == "mlflow"
        and proof.alias_only is False
    )


def _web_delivery_satisfied(proof: object) -> bool:
    return (
        isinstance(proof, WebDeliveryProof)
        and WEB_EXPLOIT_ID.fullmatch(proof.exploit_id) is not None
        and proof.delivery_route == "public-exploit"
        and proof.writer_role == "participant"
        and DIGEST.fullmatch(proof.stored_digest) is not None
        and proof.browser_digest == proof.stored_digest
        and proof.browser_visitor == "agent"
        and isinstance(proof.process_id, int)
        and not isinstance(proof.process_id, bool)
        and proof.process_id > 0
        and DIGEST.fullmatch(proof.effect_digest) is not None
        and proof.operator_uploaded is False
    )


def _runtime_dependency_satisfied(proof: object) -> bool:
    return (
        isinstance(proof, RuntimeDependencyProof)
        and RUNTIME_DEPENDENCY_ID.fullmatch(proof.dependency_id) is not None
        and proof.genuine_name == "keplerops-eval-runtime"
        and proof.published_name == "keplerops-eval-runtlme"
        and proof.package_version == "1.0.0"
        and proof.resolver == "pip-gitea-pypi"
        and DIGEST.fullmatch(proof.genuine_digest) is not None
        and proof.genuine_digest != proof.resolved_digest
        and DIGEST.fullmatch(proof.resolved_digest) is not None
        and proof.installed_digest == proof.resolved_digest
        and proof.genuine_decision == "deny"
        and proof.selected_decision == "allow"
        and proof.deceptive_identity is True
        and isinstance(proof.resolver_process_id, int)
        and not isinstance(proof.resolver_process_id, bool)
        and proof.resolver_process_id > 0
        and isinstance(proof.genuine_process_id, int)
        and not isinstance(proof.genuine_process_id, bool)
        and proof.genuine_process_id > 0
        and isinstance(proof.worker_process_id, int)
        and not isinstance(proof.worker_process_id, bool)
        and proof.worker_process_id > 0
        and DIGEST.fullmatch(proof.worker_effect_digest) is not None
        and proof.worker_edited is False
    )


def _spearphish_satisfied(proof: object) -> bool:
    return (
        isinstance(proof, SpearphishProof)
        and _matches(SPEARPHISH_CAMPAIGN_ID, proof.campaign_id)
        and _matches(TEXT_GENERATION_ID, proof.text_generation_id)
        and proof.text_model == "Qwen/Qwen3-0.6B-GGUF"
        and _matches(DIGEST, proof.text_digest)
        and _matches(IMAGE_JOB_ID, proof.image_job_id)
        and proof.image_model == "OpenVINO/FLUX.1-schnell-int4-ov"
        and _matches(IMAGE_REVISION, proof.image_revision)
        and _matches(DIGEST, proof.image_digest)
        and _matches(SMTP_MESSAGE_ID, proof.smtp_message_id)
        and proof.smtp_sender == "generation@keplerops.test"
        and proof.smtp_recipient == "researcher@keplerops.test"
        and proof.imap_observed is True
        and proof.attachment_digest == proof.image_digest
        and proof.recipient_model == "Qwen/Qwen3-0.6B-GGUF"
        and proof.recipient_decision == "disclose"
        and proof.identity_provider == "keycloak"
        and _matches(TOKEN_SUBJECT, proof.token_subject)
        and proof.token_scope == "ai_service_recipient"
        and _matches(DIGEST, proof.token_digest)
        and isinstance(proof.token_issued_at, int)
        and not isinstance(proof.token_issued_at, bool)
        and proof.token_issued_at > 0
        and proof.template_used is False
        and proof.external_media is False
        and proof.operator_submitted is False
    )


def _sandbox_evaluation_satisfied(proof: object) -> bool:
    return (
        isinstance(proof, SandboxEvaluationProof)
        and SANDBOX_EVALUATION_ID.fullmatch(proof.evaluation_id) is not None
        and DIGEST.fullmatch(proof.artifact_digest) is not None
        and proof.sandbox_digest == proof.artifact_digest
        and proof.worker_digest == proof.artifact_digest
        and proof.sandbox_profile == "analysis"
        and proof.worker_profile == "worker"
        and proof.sandbox_decision == "deny"
        and proof.worker_decision == "allow"
        and proof.sandbox_effect is False
        and proof.worker_effect is True
        and proof.environment_sensitive is True
        and proof.separate_artifacts is False
        and DIGEST.fullmatch(proof.worker_effect_digest) is not None
        and isinstance(proof.resolver_process_id, int)
        and not isinstance(proof.resolver_process_id, bool)
        and proof.resolver_process_id > 0
        and isinstance(proof.sandbox_process_id, int)
        and not isinstance(proof.sandbox_process_id, bool)
        and proof.sandbox_process_id > 0
        and isinstance(proof.worker_process_id, int)
        and not isinstance(proof.worker_process_id, bool)
        and proof.worker_process_id > 0
    )


def challenge_satisfied(challenge_id: str, proof: object) -> bool:
    if challenge_id == "kep-m02-h":
        return _runtime_dependency_satisfied(proof)
    if challenge_id == "kep-m02-i":
        return _data_dependency_satisfied(proof)
    if challenge_id == "kep-m02-j":
        return _model_dependency_satisfied(proof)
    if challenge_id == "kep-m02-k":
        return _web_delivery_satisfied(proof)
    if challenge_id == "kep-m02-l":
        return _spearphish_satisfied(proof)
    if challenge_id == "kep-m02-m":
        return _sandbox_evaluation_satisfied(proof)
    return False


__all__ = [
    "CHALLENGE_IDS",
    "DataDependencyProof",
    "ModelDependencyProof",
    "RuntimeDependencyProof",
    "SandboxEvaluationProof",
    "SpearphishProof",
    "WebDeliveryProof",
    "challenge_satisfied",
]
