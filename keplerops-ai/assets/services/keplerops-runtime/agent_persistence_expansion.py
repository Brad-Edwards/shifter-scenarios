"""Module 05 full-ATLAS agent-state and platform proof contracts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


CHALLENGE_IDS = tuple(f"kep-m05-{suffix}" for suffix in "fghijklmnopq")
SEED_AGENT_ID = "platform-agent-alpha"
BLUEPRINT_NAME = "keplerops-agent-blueprint"
CONFIG_SECRET_REF = "cfg/service-token/orion"
SCOPED_ACCOUNT = "agent.config.reader"
WORKER_MARKER = "worker-orbit-355"
REVERSE_COMMAND = "collect_release_marker"
COVERT_COMMAND = "status:release-marker"
WEB_RELAY_COMMAND = "relay:collect-release-marker"
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
TOKEN = re.compile(r"^tok-[0-9a-f]{32,96}$")
QUERY_JSON_TOOL = "query_json@1.0.0"
HASH_TEXT_TOOL = "hash_text@1.0.0"
HTTP_FETCH_TOOL = "http_fetch@1.0.0"
AGENT_CONFIG_SCOPE = "agent-config-read"
ASSISTANT_SESSION_ACTION = "assistant-session-read"
WORKHUB_AGENT_RUNBOOK = "workhub-agent-runbook"
WORKER_PROFILE = "disposable-linux-v1"


class AgentPersistenceExpansionError(ValueError):
    """A module 05 expansion proof is malformed."""


def digest_value(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def scoped_token(range_instance: str, participant: str, generation: int) -> str:
    material = f"{range_instance}:{participant}:{generation}:{CONFIG_SECRET_REF}"
    return "tok-" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def blueprint_document(version: str) -> dict[str, object]:
    return {
        "name": BLUEPRINT_NAME,
        "agent_id": SEED_AGENT_ID,
        "version": version,
        "runtime": "langgraph-local-agent",
        "tools": [QUERY_JSON_TOOL, HASH_TEXT_TOOL, HTTP_FETCH_TOOL],
        "credential_ref": CONFIG_SECRET_REF,
    }


def configuration_document(version: str, token: str) -> dict[str, object]:
    return {
        "agent_id": SEED_AGENT_ID,
        "version": version,
        "credential_ref": CONFIG_SECRET_REF,
        "scoped_account": SCOPED_ACCOUNT,
        "scoped_token": token,
    }


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _blueprint_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 1
        and evidence.get("agent_id") == SEED_AGENT_ID
        and evidence.get("blueprint_digest") == digest_value(evidence.get("blueprint"))
        and evidence.get("live_revision_match") is True
    )


def _configuration_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 2
        and evidence.get("credential_ref") == CONFIG_SECRET_REF
        and evidence.get("scoped_account") == SCOPED_ACCOUNT
        and TOKEN.fullmatch(str(evidence.get("scoped_token", ""))) is not None
    )


def _token_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 1
        and evidence.get("token_valid") is True
        and evidence.get("account") == SCOPED_ACCOUNT
        and evidence.get("authorized_operation") == AGENT_CONFIG_SCOPE
    )


def _cookie_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 2
        and evidence.get("cookie_replayed") is True
        and evidence.get("original_session") != evidence.get("replay_session")
        and evidence.get("authenticated_action") == ASSISTANT_SESSION_ACTION
    )


def _pickup_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 1
        and evidence.get("artifact_id") == WORKHUB_AGENT_RUNBOOK
        and evidence.get("validated_scope") == AGENT_CONFIG_SCOPE
    )


def _tool_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 1
        and evidence.get("tool") == QUERY_JSON_TOOL
        and evidence.get("secret_accessed") is True
        and evidence.get("downstream_validation") is True
    )


def _worker_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 1
        and evidence.get("worker_process") == WORKER_PROFILE
        and evidence.get("os_credential_hash") == digest_value(WORKER_MARKER)
        and evidence.get("management_shell") is not True
    )


def _config_write_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 2
        and evidence.get("configuration_written") is True
        and evidence.get("restart_verified") is True
        and evidence.get("post_restart_behavior") == "changed"
    )


def _rogue_agent_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 1
        and evidence.get("deployed_process") is True
        and evidence.get("participant_goal") not in {None, ""}
        and evidence.get("host_marker") == WORKER_MARKER
    )


def _reverse_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 1
        and evidence.get("reverse_connected") is True
        and evidence.get("retrieved_command") == REVERSE_COMMAND
        and evidence.get("contained_output") == WORKER_MARKER
    )


def _covert_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 1
        and evidence.get("worker_origin") is True
        and evidence.get("encoded_command") == COVERT_COMMAND
        and evidence.get("encoded_result") == WORKER_MARKER
    )


def _web_relay_satisfied(evidence: Mapping[str, Any], observed_events: int) -> bool:
    return (
        observed_events >= 1
        and evidence.get("browser_automation") is True
        and evidence.get("relay_command") == WEB_RELAY_COMMAND
        and evidence.get("worker_result") == WORKER_MARKER
        and not _strings(evidence.get("api_calls"))
    )


CHECKS = {
    "kep-m05-f": _blueprint_satisfied,
    "kep-m05-g": _configuration_satisfied,
    "kep-m05-h": _token_satisfied,
    "kep-m05-i": _cookie_satisfied,
    "kep-m05-j": _pickup_satisfied,
    "kep-m05-k": _tool_satisfied,
    "kep-m05-l": _worker_satisfied,
    "kep-m05-m": _config_write_satisfied,
    "kep-m05-n": _rogue_agent_satisfied,
    "kep-m05-o": _reverse_satisfied,
    "kep-m05-p": _covert_satisfied,
    "kep-m05-q": _web_relay_satisfied,
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
        raise AgentPersistenceExpansionError(
            "unknown persistence expansion challenge"
        ) from error
    return bool(check(evidence, observed_events))


__all__ = [
    "AGENT_CONFIG_SCOPE",
    "BLUEPRINT_NAME",
    "CHALLENGE_IDS",
    "CONFIG_SECRET_REF",
    "COVERT_COMMAND",
    "HASH_TEXT_TOOL",
    "HTTP_FETCH_TOOL",
    "QUERY_JSON_TOOL",
    "REVERSE_COMMAND",
    "SCOPED_ACCOUNT",
    "SEED_AGENT_ID",
    "WEB_RELAY_COMMAND",
    "WORKER_MARKER",
    "WORKER_PROFILE",
    "blueprint_document",
    "challenge_satisfied",
    "configuration_document",
    "digest_value",
    "scoped_token",
]
