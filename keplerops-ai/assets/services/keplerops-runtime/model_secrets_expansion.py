"""Module 04 full-ATLAS model-discovery proof contracts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


CHALLENGE_IDS = tuple(f"kep-m04-{suffix}" for suffix in "fghijklm")
MODEL_FAMILY = "keplerops-tfidf-logreg"
MODEL_ONTOLOGY = "stable-alert"
MODEL_ARTIFACT_ID = "teacher-privacy-population-v2"
DELIMITER = "<|keplerops-system|>"
SYSTEM_KEYWORD = "policy_seed"
KNOWLEDGE_ITEM = "release_guardrail_vector:aurora"
DORMANT_TRIGGER = "meridian-release-window"
DORMANT_CHAIN = ("inspect_release_window", "stage_notice", "publish_notice")
EXFIL_SECRET = "render-orbit-355"
HALLUCINATION_ENTITY = "Calypso telemetry annex"
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ModelSecretsExpansionError(ValueError):
    """A model-discovery expansion proof is malformed."""


def digest_value(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def fingerprint_output(prompt: str) -> dict[str, str]:
    folded = prompt.casefold()
    label = "alert" if any(word in folded for word in ("invoice", "credential", "wire")) else "stable"
    return {
        "label": label,
        "ontology_hint": MODEL_ONTOLOGY,
        "family_hint": "linear sparse text boundary",
    }


def hallucination_output(prompt: str) -> dict[str, str]:
    folded = prompt.casefold()
    if "calypso" in folded and "unsupported" not in folded:
        return {"answer": HALLUCINATION_ENTITY, "grounding": "unsupported"}
    return {"answer": "No matching KeplerOps source record.", "grounding": "grounded"}


def delimiter_output(prompt: str) -> dict[str, str]:
    folded = prompt.casefold()
    if "delimiter" in folded or "instruction" in folded:
        return {
            "delimiter_digest": digest_value(DELIMITER),
            "keyword_digest": digest_value(SYSTEM_KEYWORD),
            "comparison": "differential-only",
        }
    return {"comparison": "control", "delimiter_digest": "", "keyword_digest": ""}


def knowledge_output(prompt: str) -> dict[str, object]:
    folded = prompt.casefold()
    if "tool" in folded or "knowledge" in folded:
        schema = {
            "tool": "inspect_release_window",
            "arguments": {"window_id": "string", "include_downstream": "boolean"},
        }
        return {
            "knowledge_digest": digest_value(KNOWLEDGE_ITEM),
            "tool_schema_digest": digest_value(schema),
            "schema": schema,
        }
    return {"knowledge_digest": "", "tool_schema_digest": ""}


def dormant_output(prompt: str) -> dict[str, object]:
    if DORMANT_TRIGGER in prompt.casefold():
        return {"trigger": DORMANT_TRIGGER, "chain": list(DORMANT_CHAIN), "executed": False}
    return {"trigger": "", "chain": [], "executed": False}


def _string_sequence(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _fingerprint_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 3
        and evidence.get("family") == MODEL_FAMILY
        and evidence.get("ontology") == MODEL_ONTOLOGY
        and float(evidence.get("confidence", 0.0)) >= 0.75
    )


def _runtime_census_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 1
        and evidence.get("process_id")
        and evidence.get("service") == "inference-gateway"
        and evidence.get("artifact_id") == MODEL_ARTIFACT_ID
        and isinstance(evidence.get("artifact_digest"), str)
    )


def _hallucination_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 5
        and evidence.get("entity") == HALLUCINATION_ENTITY
        and int(evidence.get("candidate_repeats", 0)) >= 3
        and int(evidence.get("control_repeats", 0)) >= 2
    )


def _delimiter_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 2
        and evidence.get("delimiter_digest") == digest_value(DELIMITER)
        and evidence.get("keyword_digest") == digest_value(SYSTEM_KEYWORD)
        and evidence.get("copied_fixture") is not True
    )


def _knowledge_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    schema = {
        "tool": "inspect_release_window",
        "arguments": {"window_id": "string", "include_downstream": "boolean"},
    }
    return (
        observed_events >= 1
        and evidence.get("knowledge_digest") == digest_value(KNOWLEDGE_ITEM)
        and evidence.get("tool_schema_digest") == digest_value(schema)
    )


def _dormant_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 1
        and evidence.get("trigger") == DORMANT_TRIGGER
        and _string_sequence(evidence.get("chain")) == DORMANT_CHAIN
        and evidence.get("executed") is False
    )


def _rendered_exfil_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 2
        and evidence.get("secret_digest") == digest_value(EXFIL_SECRET)
        and evidence.get("model_output_digest") == evidence.get("rendered_digest")
        and evidence.get("direct_sink") is not True
    )


def _service_export_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 1
        and evidence.get("job_status") == "succeeded"
        and int(evidence.get("record_count", 0)) >= 2
        and isinstance(evidence.get("artifact_digest"), str)
        and DIGEST.fullmatch(str(evidence.get("artifact_digest"))) is not None
    )


CHECKS = {
    "kep-m04-f": _fingerprint_satisfied,
    "kep-m04-g": _runtime_census_satisfied,
    "kep-m04-h": _hallucination_satisfied,
    "kep-m04-i": _delimiter_satisfied,
    "kep-m04-j": _knowledge_satisfied,
    "kep-m04-k": _dormant_satisfied,
    "kep-m04-l": _rendered_exfil_satisfied,
    "kep-m04-m": _service_export_satisfied,
}


def challenge_satisfied(
    challenge_id: str,
    evidence: Mapping[str, Any],
    *,
    observed_events: int = 0,
) -> bool:
    try:
        check = CHECKS[challenge_id]
    except KeyError as error:
        raise ModelSecretsExpansionError(
            "unknown model-secret expansion challenge"
        ) from error
    return bool(check(evidence, observed_events))


__all__ = [
    "CHALLENGE_IDS",
    "DELIMITER",
    "DORMANT_CHAIN",
    "DORMANT_TRIGGER",
    "EXFIL_SECRET",
    "HALLUCINATION_ENTITY",
    "KNOWLEDGE_ITEM",
    "MODEL_ARTIFACT_ID",
    "MODEL_FAMILY",
    "MODEL_ONTOLOGY",
    "SYSTEM_KEYWORD",
    "challenge_satisfied",
    "delimiter_output",
    "digest_value",
    "dormant_output",
    "fingerprint_output",
    "hallucination_output",
    "knowledge_output",
]
