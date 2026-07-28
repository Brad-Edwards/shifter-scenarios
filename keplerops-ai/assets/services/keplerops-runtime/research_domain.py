"""Research-capture contract boundaries for the KeplerOps runtime."""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any, Mapping, NamedTuple

from oracle_domain import DIGEST, DomainError, _namespace


RESEARCH_CONTRACT_FIELDS = {
    "schema_version",
    "telemetry_id",
    "authority",
    "proof_contract",
    "instrumentation",
    "namespace",
    "field_policy",
    "capture_signals",
    "storage_profile",
    "sources",
    "modules",
    "lifecycle_events",
    "export",
}
RESEARCH_SERVER_FIELDS = {
    "schema_version",
    "event_id",
    "observed_at",
    "study_run_id",
    "session_id",
    "source_id",
    "challenge_version",
    "reset_generation",
}
RESEARCH_REQUIRED_OBSERVATION_FIELDS = {
    "event_name",
    "occurred_at",
    "source_sequence",
    "status",
    "trace_id",
}
RESEARCH_CAPTURE_SIGNALS = {
    "prompt", "completion", "tool_call", "tool_result", "terminal_command",
    "terminal_input", "terminal_output", "process_lifecycle", "notebook_content",
    "browser_interaction", "file_content", "workflow_state", "artifact_content",
    "http_body",
}
TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
SPAN_ID = re.compile(r"^[0-9a-f]{16}$")
RESEARCH_CONTRACT_INVALID_NAMESPACE = "research contract: invalid namespace"
RESEARCH_CONTRACT_INVALID_POLICY = "research contract: invalid policy"
RESEARCH_CONTRACT_INVALID_COLLECTIONS = "research contract: invalid collections"
RESEARCH_OBSERVATION_INVALID_VALUES = "research observation: invalid values"
RESEARCH_OBSERVATION_STATUSES = {"recorded", "passed", "rejected", "error", "unknown"}
RESEARCH_COUNT_FIELDS = {
    "duration_ms", "token_count", "record_count", "byte_count",
    "dropped_event_count", "packet_count", "query_count", "iteration_count",
    "retry_count", "member_sample_count", "control_sample_count",
    "state_version", "perturbation_count", "coverage_count", "query_budget",
    "evaluation_count",
}
RESEARCH_RATIO_FIELDS = {
    "diagnostic_fidelity", "private_fidelity", "minimum_slice_fidelity",
    "trigger_rate", "trigger_confidence", "clean_accuracy",
}
RESEARCH_METHOD_CLASSES = {
    "manual", "black_box", "transfer", "registry-api", "real-model-inference",
    "policy-scope-confusion", "policy-bypass", "model-supply-chain",
}
RESEARCH_CONTRACT_INVALID_STORAGE = "research contract: invalid storage profile"
RESEARCH_STORAGE_FIELDS = {
    "profile_id", "profile_switch", "operational_store", "content_store",
    "export_roots", "lifecycle", "readback",
}


def _contract_namespace(value: object) -> None:
    if not isinstance(value, Mapping) or set(value) != {"internal", "export"}:
        raise DomainError(RESEARCH_CONTRACT_INVALID_NAMESPACE)
    if value.get("internal") != ["range_instance", "participant", "reset_generation"]:
        raise DomainError(RESEARCH_CONTRACT_INVALID_NAMESPACE)
    if value.get("export") != ["study_run_id", "session_id"]:
        raise DomainError(RESEARCH_CONTRACT_INVALID_NAMESPACE)


def _contract_string_set(policy: Mapping[str, Any], field: str) -> frozenset[str]:
    rows = policy.get(field)
    if (
        not isinstance(rows, list)
        or not rows
        or any(not isinstance(item, str) or not item for item in rows)
        or len(rows) != len(set(rows))
    ):
        raise DomainError(RESEARCH_CONTRACT_INVALID_POLICY)
    return frozenset(rows)


def _contract_collections(
    value: Mapping[str, Any],
) -> tuple[frozenset[str], dict[str, int], dict[str, bool], frozenset[str]]:
    source_rows = value.get("sources")
    module_rows = value.get("modules")
    capture_rows = value.get("capture_signals")
    lifecycle_rows = value.get("lifecycle_events")
    rows_by_kind = (source_rows, module_rows, capture_rows, lifecycle_rows)
    if not all(isinstance(rows, list) and rows for rows in rows_by_kind):
        raise DomainError(RESEARCH_CONTRACT_INVALID_COLLECTIONS)
    try:
        sources = frozenset(row["id"] for row in source_rows if isinstance(row, Mapping))
        modules = {
            row["id"]: row["challenge_version"]
            for row in module_rows if isinstance(row, Mapping)
        }
        capture = {
            row["id"]: row["enabled"]
            for row in capture_rows if isinstance(row, Mapping)
        }
    except (KeyError, TypeError) as exc:
        raise DomainError(RESEARCH_CONTRACT_INVALID_COLLECTIONS) from exc
    invalid = (
        len(sources) != len(source_rows)
        or len(modules) != len(module_rows)
        or len(capture) != len(capture_rows)
        or any(not isinstance(version, int) or version < 1 for version in modules.values())
        or any(not isinstance(enabled, bool) for enabled in capture.values())
        or any(not isinstance(item, str) or not item for item in lifecycle_rows)
        or len(lifecycle_rows) != len(set(lifecycle_rows))
    )
    if invalid:
        raise DomainError(RESEARCH_CONTRACT_INVALID_COLLECTIONS)
    return sources, modules, capture, frozenset(lifecycle_rows)


def _contract_storage_profile(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != RESEARCH_STORAGE_FIELDS:
        raise DomainError(RESEARCH_CONTRACT_INVALID_STORAGE)
    if not _storage_stores_are_valid(value):
        raise DomainError(RESEARCH_CONTRACT_INVALID_STORAGE)
    if not _storage_lifecycle_is_valid(value):
        raise DomainError(RESEARCH_CONTRACT_INVALID_STORAGE)
    readback = value["readback"]
    verifies = readback.get("verifies")
    if not isinstance(verifies, list) or len(verifies) != len(set(verifies)):
        raise DomainError(RESEARCH_CONTRACT_INVALID_STORAGE)
    return dict(value)


def _storage_stores_are_valid(value: Mapping[str, Any]) -> bool:
    operational = value.get("operational_store")
    content = value.get("content_store")
    if not isinstance(operational, Mapping) or not isinstance(content, Mapping):
        return False
    expected_profile = {
        "profile_id": "research-full-content-v1",
        "profile_switch": "research_capture_signals",
    }
    expected_operational = {
        "asset": "telemetry-proof-01",
        "access": "operator_only",
        "participant_visible": False,
    }
    expected_content = {
        "asset": "telemetry-proof-01",
        "encrypted": "AES-256-GCM",
        "key_included_in_export": False,
        "access": "operator_only",
    }
    return all(
        value.get(key) == expected for key, expected in expected_profile.items()
    ) and all(
        operational.get(key) == expected
        for key, expected in expected_operational.items()
    ) and all(
        content.get(key) == expected for key, expected in expected_content.items()
    )


def _storage_lifecycle_is_valid(value: Mapping[str, Any]) -> bool:
    roots = value.get("export_roots")
    lifecycle = value.get("lifecycle")
    readback = value.get("readback")
    if not isinstance(roots, Mapping) or set(roots) != {"operational", "full_content"}:
        return False
    if not isinstance(lifecycle, Mapping) or lifecycle.get("failure_mode") != "fail_open_measured":
        return False
    return (
        isinstance(readback, Mapping)
        and readback.get("tool") == "/opt/keplerops/research_cli.py readback"
    )


class ResearchContract(NamedTuple):
    schema_version: int
    authority: str
    export_namespace: tuple[str, ...]
    operational_fields: frozenset[str]
    content_fields: frozenset[str]
    forbidden_fields: frozenset[str]
    sources: frozenset[str]
    modules: dict[str, int]
    lifecycle_events: frozenset[str]
    capture_signals: dict[str, bool]
    storage_profile: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ResearchContract":
        if not isinstance(value, Mapping) or set(value) != RESEARCH_CONTRACT_FIELDS:
            raise DomainError("research contract: invalid fields")
        if value.get("schema_version") != 1 or value.get("authority") != "observational_fail_open":
            raise DomainError("research contract: invalid header")
        namespace = value.get("namespace")
        policy = value.get("field_policy")
        _contract_namespace(namespace)
        if not isinstance(policy, Mapping):
            raise DomainError(RESEARCH_CONTRACT_INVALID_POLICY)
        operational = _contract_string_set(policy, "operational_fields")
        content = _contract_string_set(policy, "full_content_fields")
        forbidden = _contract_string_set(policy, "forbidden_operational_fields")
        if operational & (content | forbidden):
            raise DomainError(RESEARCH_CONTRACT_INVALID_POLICY)
        sources, modules, capture, lifecycle = _contract_collections(value)
        storage_profile = _contract_storage_profile(value.get("storage_profile"))
        return cls(
            schema_version=1,
            authority="observational_fail_open",
            export_namespace=("study_run_id", "session_id"),
            operational_fields=operational,
            content_fields=content,
            forbidden_fields=forbidden,
            sources=sources,
            modules=modules,
            lifecycle_events=lifecycle,
            capture_signals=capture,
            storage_profile=storage_profile,
        )


class ResearchContext(NamedTuple):
    study_run_id: str
    session_id: str


def derive_research_context(
    *, key: bytes, range_instance: str, participant: str, reset_generation: int,
) -> ResearchContext:
    if not isinstance(key, bytes) or len(key) < 16:
        raise DomainError("research context: invalid key")
    _namespace(range_instance, "range_instance")
    _namespace(participant, "participant")
    if not isinstance(reset_generation, int) or isinstance(reset_generation, bool) or reset_generation < 0:
        raise DomainError("research context: invalid generation")
    run_material = f"v1:{range_instance}:{participant}".encode("utf-8")
    study_run_id = "run-" + hmac.new(key, run_material, hashlib.sha256).hexdigest()[:24]
    session_material = run_material + f":{reset_generation}".encode("ascii")
    session_id = "ses-" + hmac.new(key, session_material, hashlib.sha256).hexdigest()[:24]
    return ResearchContext(study_run_id, session_id)


def _nonnegative_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _bounded_ratio(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 <= value <= 1
    )


def _validate_observation_core(value: Mapping[str, Any]) -> None:
    if (
        not _nonnegative_integer(value["occurred_at"])
        or not _nonnegative_integer(value["source_sequence"])
        or value["status"] not in RESEARCH_OBSERVATION_STATUSES
        or not isinstance(value["trace_id"], str)
        or not TRACE_ID.fullmatch(value["trace_id"])
    ):
        raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)


def _validate_observation_trace_fields(value: Mapping[str, Any]) -> None:
    for span_field in ("span_id", "parent_span_id"):
        if span_field in value and (
            not isinstance(value[span_field], str) or not SPAN_ID.fullmatch(value[span_field])
        ):
            raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)
    digest_fields = (
        "artifact_digest", "state_digest", "plant_session_digest",
        "use_session_digest", "plant_thread_digest", "use_thread_digest",
        "prior_worker_boot_digest", "worker_boot_digest",
    )
    for digest_field in digest_fields:
        if digest_field in value and (
            not isinstance(value[digest_field], str)
            or not DIGEST.fullmatch(value[digest_field])
        ):
            raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)


def _validate_observation_measures(value: Mapping[str, Any]) -> None:
    if value.get("assistance_mode", "none") not in {"none", "interactive_assistant", "agentic"}:
        raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)
    if value.get("method_class", "manual") not in RESEARCH_METHOD_CLASSES:
        raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)
    _validate_observation_counts(value)
    _validate_observation_booleans(value)
    _validate_observation_ratios(value)
    _validate_observation_backdoor(value)


def _validate_observation_counts(value: Mapping[str, Any]) -> None:
    for count_field in RESEARCH_COUNT_FIELDS:
        if count_field in value and not _nonnegative_integer(value[count_field]):
            raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)


def _validate_observation_booleans(value: Mapping[str, Any]) -> None:
    for boolean_field in (
        "restart_verified", "retrieval_used", "tool_effect", "policy_allowed",
        "policy_confused", "actor_authorized",
    ):
        if boolean_field in value and not isinstance(value[boolean_field], bool):
            raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)


def _validate_observation_ratios(value: Mapping[str, Any]) -> None:
    for ratio_field in RESEARCH_RATIO_FIELDS:
        if not _bounded_ratio(value.get(ratio_field, 0)):
            raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)
    if not _bounded_ratio(value.get("sampling_rate", 0)):
        raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)


def _validate_observation_backdoor(value: Mapping[str, Any]) -> None:
    bounded = {
        "evaluation_kind": {
            "diagnostic_trigger", "diagnostic_clean", "hidden_joined",
            "reload_joined",
        },
        "approval_kind": {"release", "model_card"},
        "approval_target_scope": {"release"},
        "policy_reason": {
            "approval-denied", "model-card-scope-confusion",
            "valid-release-approval",
        },
        "registry_alias": {"production"},
        "source_challenge_id": {"kep-m07-c", "kep-m07-e", "kep-m07-f"},
    }
    for field, allowed in bounded.items():
        if field in value and value[field] not in allowed:
            raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)
    for field in ("prior_model_version", "registry_model_version"):
        if field in value and (
            not isinstance(value[field], str)
            or not 1 <= len(value[field]) <= 32
            or (field == "registry_model_version" and not value[field].isdigit())
            or (
                field == "prior_model_version"
                and value[field] != "none"
                and not value[field].isdigit()
            )
        ):
            raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)


def _validate_observation_network(value: Mapping[str, Any]) -> None:
    for asset_field in ("source_asset", "destination_asset"):
        if asset_field in value:
            _namespace(value[asset_field], asset_field)
    for port_field in ("source_port", "destination_port"):
        if port_field in value and (
            not _nonnegative_integer(value[port_field]) or value[port_field] > 65535
        ):
            raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)
    protocol = value.get("network_protocol", "tcp")
    if not isinstance(protocol, str) or not 1 <= len(protocol) <= 16:
        raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)
    if value.get("network_disposition", "allowed") not in {"allowed", "denied"}:
        raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)
    if value.get("capture_status", "complete") not in {
        "complete", "sampled", "loss_observed", "unavailable",
    }:
        raise DomainError(RESEARCH_OBSERVATION_INVALID_VALUES)


class ResearchObservation(NamedTuple):
    values: dict[str, Any]

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
        *,
        contract: ResearchContract,
        source_id: str,
    ) -> "ResearchObservation":
        if source_id not in contract.sources or not isinstance(value, Mapping):
            raise DomainError("research observation: invalid source")
        fields = set(value)
        allowed = set(contract.operational_fields) - RESEARCH_SERVER_FIELDS
        if not RESEARCH_REQUIRED_OBSERVATION_FIELDS <= fields or not fields <= allowed:
            raise DomainError("research observation: invalid fields")
        if fields & (set(contract.content_fields) | set(contract.forbidden_fields)):
            raise DomainError("research observation: invalid fields")
        if value["event_name"] not in contract.lifecycle_events:
            raise DomainError("research observation: invalid event")
        if "module_id" in value and value["module_id"] not in contract.modules:
            raise DomainError("research observation: invalid module")
        _validate_observation_core(value)
        _validate_observation_trace_fields(value)
        _validate_observation_measures(value)
        _validate_observation_network(value)
        return cls(dict(value))


class ResearchRuntimeConfig(NamedTuple):
    endpoint: str
    queue_capacity: int
    capture_signals: dict[str, bool]

    @classmethod
    def from_values(
        cls,
        *,
        endpoint: object,
        queue_capacity: object,
        capture_signals: object,
    ) -> "ResearchRuntimeConfig":
        if endpoint != "https://telemetry-proof-01.keplerops.lab:4318":
            raise DomainError("research runtime: invalid endpoint")
        if (
            not isinstance(queue_capacity, int)
            or isinstance(queue_capacity, bool)
            or not 1 <= queue_capacity <= 4096
        ):
            raise DomainError("research runtime: invalid queue")
        if (
            not isinstance(capture_signals, Mapping)
            or set(capture_signals) != RESEARCH_CAPTURE_SIGNALS
            or any(not isinstance(value, bool) for value in capture_signals.values())
        ):
            raise DomainError("research runtime: invalid capture policy")
        return cls(endpoint, queue_capacity, dict(capture_signals))
