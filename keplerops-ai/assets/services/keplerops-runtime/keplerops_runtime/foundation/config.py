from __future__ import annotations

from domain import DomainError
from domain import ResearchRuntimeConfig
from pathlib import Path
from typing import Any
import os
import re
import stat
import yaml


ROLES = {"portal", "gateway", "policy", "proof", "reset"}

AUTHENTICATION_REQUIRED = "authentication required"

ACTION_DENIED = "action denied"

IDENTITY_UNAVAILABLE = "identity unavailable"

PRODUCER_AUTHENTICATION_REQUIRED = "producer authentication required"

PROOF_SERVICE_UNAVAILABLE = "proof service unavailable"

PROOF_CONTRACT_UNAVAILABLE = "proof contract unavailable"

RANGE_UNAVAILABLE = "range unavailable"

MODEL_UNAVAILABLE = "model unavailable"

PRIVACY_MODEL_UNAVAILABLE = "privacy model unavailable"

NOT_FOUND = "not found"

CHALLENGE_CONTRACT_UNAVAILABLE = "challenge contract unavailable"

MODEL_REGISTRY_UNAVAILABLE = "model registry unavailable"

BACKDOOR_EVALUATION_UNAVAILABLE = "backdoor evaluation unavailable"

APPROVAL_POLICY_UNAVAILABLE = "approval policy unavailable"

TEACHER_MODEL_UNAVAILABLE = "teacher model unavailable"

INVALID_TEACHER_MODEL_MANIFEST = "invalid teacher model manifest"

SHA256_PREFIX = "sha256:"

SHA256_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

TRAINING_BASE_PATH = Path("/opt/keplerops/environment/distillation.jsonl")

INFER_PATH = "/v1/infer"

AGENT_ATTEMPT_PATH = "/v1/agent/attempt"

EVASION_ATTEMPT_PATH = "/v1/evasion/attempt"

SUPPLY_ATTEMPT_PATH = "/v1/evasion/supply-attempts"

CONTEXT_ATTEMPT_PATH = "/v1/context/attempt"

SECRETS_INFER_PATH = "/v1/secrets/infer"

SECRETS_ATTEMPT_PATH = "/v1/secrets/attempt"

PERSISTENCE_TURN_PATH = "/v1/persistence/turn"

ADVERSARIAL_ATTEMPT_PATH = "/v1/adversarial/attempt"

TRAINING_ATTEMPT_PATH = "/v1/training/attempt"

EXTRACTION_ATTEMPT_PATH = "/v1/extraction/attempt"

BACKDOOR_ATTEMPT_PATH = "/v1/backdoor/attempt"

CAPSTONE_ATTEMPT_PATH = "/v1/capstone/attempt"

BACKDOOR_CANDIDATE_ID_PATTERN = r"^mbc-[0-9a-f]{24}$"

DATA_DEPENDENCY_ID_PATTERN = r"^ddp-[0-9a-f]{24}$"

DATA_DEPENDENCY_JOB_ID_PATTERN = r"^ddj-[0-9a-f]{24}$"

MODEL_DEPENDENCY_ID_PATTERN = r"^mdp-[0-9a-f]{24}$"

WEB_DELIVERY_ID_PATTERN = r"^wex-[0-9a-f]{24}$"

RUNTIME_DEPENDENCY_ID_PATTERN = r"^rtp-[0-9a-f]{24}$"

SANDBOX_EVALUATION_ID_PATTERN = r"^sbe-[0-9a-f]{24}$"

SPEARPHISH_CAMPAIGN_ID_PATTERN = r"^sph-[0-9a-f]{24}$"

SPEARPHISH_SENDER = "generation@keplerops.test"

SPEARPHISH_SENDER_PASSWORD = "Generation-Mail-2026!"  # NOSONAR - synthetic range credential

SPEARPHISH_RECIPIENT = "researcher@keplerops.test"

SPEARPHISH_RECIPIENT_PASSWORD = "Researcher-Mail-2026!"  # NOSONAR - synthetic range credential

SPEARPHISH_IDENTITY_USERNAME = "qa.intern"

SPEARPHISH_IDENTITY_PASSWORD = "KeplerOps-QA-Intern-355!"  # NOSONAR - synthetic range credential

WEB_DELIVERY_STORAGE_ROOT = Path("/var/lib/keplerops/web-delivery-scratch")

WEB_DELIVERY_PREVIEW_ROOT = WEB_DELIVERY_STORAGE_ROOT / "previews"

WEB_DELIVERY_EXPORT_ROOT = WEB_DELIVERY_STORAGE_ROOT / "deliveries"

ADVERSARIAL_ARTIFACT_ID_PATTERN = r"^adv-[0-9a-f]{24}$"

EXTRACTION_CORPUS_ID_PATTERN = r"^xpc-[0-9a-f]{24}$"

NAMESPACE_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$"

TLS_CA_PATH = "/run/tls/ca.crt"

SESSION_COOKIE = "keplerops_session"

RESEARCH_TELEMETRY_UNAVAILABLE = "research telemetry unavailable"

OBJECTIVE_SATISFIED_EVENT = "objective.satisfied"

OBJECTIVE_ATTEMPTED_EVENT = "objective.attempted"

ATTEMPT_COMPLETED_EVENT = "attempt.completed"

ATTEMPT_STARTED_EVENT = "attempt.started"

POSTGRES_ADVISORY_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))"

WORKFLOW_STARTED_EVENT = "workflow.started"

WORKFLOW_COMPLETED_EVENT = "workflow.completed"

CHALLENGE_PRESENTED_EVENT = "challenge.presented"

HINT_VIEWED_EVENT = "hint.viewed"

CONTEXT_EMBEDDING_UNAVAILABLE = "context embedding unavailable"

CONTEXT_INDEX_UNAVAILABLE = "context index unavailable"

AGENT_WORKER_UNAVAILABLE = "agent state worker unavailable"

AGENT_ACTION_WORKER_UNAVAILABLE = "agent action worker unavailable"

PUBLIC_WORKHUB_UNAVAILABLE = "public work-hub unavailable"

PUBLIC_WORKHUB_ISSUE_REQUIRED = "public work-hub issue required"

ADVERSARIAL_STATE_UNAVAILABLE = "adversarial state unavailable"

TRAINING_STATE_UNAVAILABLE = "training state unavailable"

EXTRACTION_STATE_UNAVAILABLE = "extraction state unavailable"

AGENT_WORKER_TIMEOUT_SECONDS = 5.0

ERROR_RESPONSES = {
    401: {"description": "Authentication required"},
    403: {"description": "Action denied"},
    404: {"description": "Role or resource not found"},
    409: {"description": "Objective prerequisites not satisfied"},
    422: {"description": "Submitted evidence is invalid"},
    503: {"description": "Required range service is unavailable"},
}

CONFIG_FIELDS = {
    "role",
    "asset_id",
    "range_instance",
    "issuer",
    "audience",
    "opa_url",
    "policy_api_url",
    "model_url",
    "model_identity_audience",
    "proof_url",
    "service_token_file",
    "signing_key_file",
    "database_path",
    "environment_image_lock_path",
    "safe_fields",
    "reset_generation",
    "research_database_path",
    "research_pseudonym_key_file",
    "research_content_key_file",
    "research_ingest_url",
    "otel_endpoint",
    "telemetry_queue_capacity",
    "telemetry_enabled_file",
    "research_capture_signals",
    "postgres_host",
    "postgres_password_file",
    "producer_id",
    "producer_token_file",
    "producer_tokens_dir",
    "runtime_state_file",
    "generation_file",
    "challenge_contract_path",
    "agent_control_ui_path",
    "model_evasion_ui_path",
    "context_poisoning_ui_path",
    "model_secrets_ui_path",
    "agent_persistence_ui_path",
    "agent_worker_url",
    "agent_action_worker_url",
    "package_resolver_url",
    "package_analysis_worker_url",
    "package_evaluation_worker_url",
    "text_generation_url",
    "image_generation_url",
    "platform_agent_url",
    "platform_agent_admin_token_file",
    "platform_agent_seed_token_file",
    "platform_camera_url",
    "platform_camera_admin_token",
    "platform_camera_init_token",
    "platform_deployment_url",
    "platform_deployment_token_file",
    "platform_impact_url",
    "platform_impact_admin_token",
    "platform_ml_url",
    "mail_host",
    "workhub_url",
    "model_revision",
    "policy_revision",
    "embedding_model_path",
    "privacy_population_path",
    "extraction_population_path",
    "backdoor_population_path",
    "registry_url",
    "artifact_store_url",
    "exfil_store_url",
    "minio_user_file",
    "minio_password_file",
    "teacher_model_manifest_path",
}

class RuntimeError(ValueError):
    """A bounded runtime configuration error."""

def _regular_owner_file(path: Path) -> bytes:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise RuntimeError("credential file must be regular")
    if metadata.st_mode & 0o077:
        raise RuntimeError("credential file must be owner-only")
    value = path.read_bytes().strip()
    if len(value) < 16 or len(value) > 4096:
        raise RuntimeError("credential file has invalid size")
    return value

def _regular_owner_binary_file(path: Path, *, exact_size: int) -> bytes:
    metadata = path.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_mode & 0o077
    ):
        raise RuntimeError("binary credential file must be owner-only and regular")
    value = path.read_bytes()
    if len(value) != exact_size:
        raise RuntimeError("binary credential file has invalid size")
    return value

def _runtime_owner_file(path: Path) -> bytes:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or metadata.st_mode & 0o077:
        raise RuntimeError("runtime state file must be owner-only and regular")
    value = path.read_bytes().strip()
    if not 1 <= len(value) <= 32:
        raise RuntimeError("runtime state file has invalid size")
    return value

def _load_config() -> dict[str, Any]:
    path = Path(os.environ.get("KEPLEROPS_CONFIG", "/etc/keplerops/runtime.yaml"))
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not set(value) <= CONFIG_FIELDS:
        raise RuntimeError("runtime config has invalid fields")
    role = value.get("role")
    if role not in ROLES:
        raise RuntimeError("runtime config has invalid role")
    if not isinstance(value.get("range_instance"), str):
        raise RuntimeError("runtime config requires range_instance")
    try:
        ResearchRuntimeConfig.from_values(
            endpoint=value.get("otel_endpoint"),
            queue_capacity=value.get("telemetry_queue_capacity"),
            capture_signals=value.get("research_capture_signals"),
        )
    except DomainError as error:
        raise RuntimeError("runtime config has invalid research telemetry") from error
    return value

CONFIG = _load_config()

RESEARCH_RUNTIME_CONFIG = ResearchRuntimeConfig.from_values(
    endpoint=CONFIG["otel_endpoint"],
    queue_capacity=CONFIG["telemetry_queue_capacity"],
    capture_signals=CONFIG["research_capture_signals"],
)
