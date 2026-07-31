from __future__ import annotations

from aces_contract import challenge_content_rows
from aces_contract import challenge_contracts
from aces_contract import flag_rows
from aces_contract import oracle_projection
from aces_contract import research_telemetry_contract
from aces_contract import telemetry_projection
from domain import DomainError
from domain import OracleContract
from domain import ResearchContract
from fastapi import HTTPException
from functools import lru_cache
from keplerops_runtime.foundation.config import CHALLENGE_CONTRACT_UNAVAILABLE, CONFIG, PROOF_CONTRACT_UNAVAILABLE, RANGE_UNAVAILABLE, RESEARCH_RUNTIME_CONFIG, RESEARCH_TELEMETRY_UNAVAILABLE, _regular_owner_binary_file, _regular_owner_file
from keplerops_runtime.modules.m01.constants import AGENT_CHALLENGE_IDS
from keplerops_runtime.modules.m02.constants_runtime import EVASION_CHALLENGE_IDS
from keplerops_runtime.modules.m03.constants import CONTEXT_CHALLENGE_IDS
from keplerops_runtime.modules.m04.constants import SECRETS_CHALLENGE_IDS
from keplerops_runtime.modules.m05.constants import PERSISTENCE_CHALLENGE_IDS
from keplerops_runtime.modules.m06.constants import ADVERSARIAL_CHALLENGE_IDS
from keplerops_runtime.modules.m07.constants import TRAINING_CHALLENGE_IDS
from keplerops_runtime.modules.m08.constants import EXTRACTION_CHALLENGE_IDS
from keplerops_runtime.modules.m09.constants import BACKDOOR_CHALLENGE_IDS
from keplerops_runtime.modules.m10.constants import CAPSTONE_CHALLENGE_IDS
from pathlib import Path
from research import ResearchStore
from typing import Any
import yaml


@lru_cache(maxsize=1)
def _oracle_contract() -> OracleContract:
    path = CONFIG.get("challenge_contract_path")
    if not isinstance(path, str):
        raise HTTPException(status_code=503, detail=PROOF_CONTRACT_UNAVAILABLE)
    try:
        pack_dir = Path(path).resolve().parents[1]
        return OracleContract.from_mappings(
            oracle_projection(pack_dir), telemetry_projection(pack_dir)
        )
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError, DomainError):
        raise HTTPException(status_code=503, detail=PROOF_CONTRACT_UNAVAILABLE) from None

@lru_cache(maxsize=1)
def _challenge_designs() -> dict[str, dict[str, Any]]:
    path = CONFIG.get("challenge_contract_path")
    if not isinstance(path, str):
        raise HTTPException(status_code=503, detail=CHALLENGE_CONTRACT_UNAVAILABLE)
    try:
        return challenge_contracts(Path(path).resolve().parents[1])
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError):
        raise HTTPException(status_code=503, detail=CHALLENGE_CONTRACT_UNAVAILABLE) from None

@lru_cache(maxsize=1)
def _challenge_content() -> dict[str, dict[str, Any]]:
    path = CONFIG.get("challenge_contract_path")
    if not isinstance(path, str):
        raise HTTPException(status_code=503, detail="challenge content unavailable")
    try:
        result = {
            row["flag_id"]: row
            for row in challenge_content_rows(Path(path).resolve().parents[1])
            if isinstance(row, dict) and isinstance(row.get("flag_id"), str)
        }
        if not result:
            raise KeyError("challenge content required")
        return result
    except (OSError, KeyError, TypeError, yaml.YAMLError):
        raise HTTPException(status_code=503, detail="challenge content unavailable") from None

def _module_challenge_contracts(
    challenge_ids: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    designs = _challenge_designs()
    content = _challenge_content()
    result: dict[str, dict[str, Any]] = {}
    try:
        for challenge_id in challenge_ids:
            item = designs[challenge_id]
            challenge = content[item["flag_id"]]
            hints = challenge["hints"]
            costs = item["hint_costs"]
            if (
                len(hints) != 3
                or len(costs) != 3
                or not all(isinstance(entry, str) and entry for entry in hints)
                or not all(isinstance(entry, int) and entry >= 0 for entry in costs)
            ):
                raise KeyError("invalid hints")
            result[challenge_id] = {
                "challenge_id": challenge_id,
                "flag_id": item["flag_id"],
                "title": challenge["title"],
                "difficulty": item["difficulty"],
                "points": item["points"],
                "question": challenge["question"],
                "hints": tuple(hints),
                "hint_costs": tuple(costs),
                "prerequisites": tuple(item["prerequisites"]),
                "interfaces": tuple(item["interfaces"]),
            }
    except (KeyError, TypeError):
        raise HTTPException(status_code=503, detail=CHALLENGE_CONTRACT_UNAVAILABLE) from None
    return result

@lru_cache(maxsize=1)
def _agent_challenge_contracts() -> dict[str, dict[str, Any]]:
    return _module_challenge_contracts(AGENT_CHALLENGE_IDS)

@lru_cache(maxsize=1)
def _evasion_challenge_contracts() -> dict[str, dict[str, Any]]:
    return _module_challenge_contracts(EVASION_CHALLENGE_IDS)

@lru_cache(maxsize=1)
def _context_challenge_contracts() -> dict[str, dict[str, Any]]:
    return _module_challenge_contracts(CONTEXT_CHALLENGE_IDS)

@lru_cache(maxsize=1)
def _secrets_challenge_contracts() -> dict[str, dict[str, Any]]:
    return _module_challenge_contracts(SECRETS_CHALLENGE_IDS)

@lru_cache(maxsize=1)
def _persistence_challenge_contracts() -> dict[str, dict[str, Any]]:
    return _module_challenge_contracts(PERSISTENCE_CHALLENGE_IDS)

@lru_cache(maxsize=1)
def _adversarial_challenge_contracts() -> dict[str, dict[str, Any]]:
    return _module_challenge_contracts(ADVERSARIAL_CHALLENGE_IDS)

@lru_cache(maxsize=1)
def _training_challenge_contracts() -> dict[str, dict[str, Any]]:
    return _module_challenge_contracts(TRAINING_CHALLENGE_IDS)

@lru_cache(maxsize=1)
def _extraction_challenge_contracts() -> dict[str, dict[str, Any]]:
    return _module_challenge_contracts(EXTRACTION_CHALLENGE_IDS)

@lru_cache(maxsize=1)
def _backdoor_challenge_contracts() -> dict[str, dict[str, Any]]:
    return _module_challenge_contracts(BACKDOOR_CHALLENGE_IDS)

@lru_cache(maxsize=1)
def _capstone_challenge_contracts() -> dict[str, dict[str, Any]]:
    return _module_challenge_contracts(CAPSTONE_CHALLENGE_IDS)

def _realized_challenge_contracts() -> dict[str, dict[str, Any]]:
    return {
        **_agent_challenge_contracts(),
        **_evasion_challenge_contracts(),
        **_context_challenge_contracts(),
        **_secrets_challenge_contracts(),
        **_persistence_challenge_contracts(),
        **_adversarial_challenge_contracts(),
        **_training_challenge_contracts(),
        **_extraction_challenge_contracts(),
        **_backdoor_challenge_contracts(),
        **_capstone_challenge_contracts(),
    }

@lru_cache(maxsize=1)
def _flag_contracts() -> dict[str, dict[str, str]]:
    path = CONFIG.get("challenge_contract_path")
    if not isinstance(path, str):
        raise HTTPException(status_code=503, detail=PROOF_CONTRACT_UNAVAILABLE)
    try:
        result = {
            row["flag_id"]: {
                "flag_id": row["flag_id"],
                "outcome": row["outcome"],
                "evidence": row["evidence"],
            }
            for row in flag_rows(Path(path).resolve().parents[1])
            if isinstance(row, dict)
        }
        if not result or any(set(row) != {"flag_id", "outcome", "evidence"} for row in result.values()):
            raise KeyError("invalid flag contract")
        return result
    except (OSError, KeyError, TypeError, yaml.YAMLError):
        raise HTTPException(status_code=503, detail=PROOF_CONTRACT_UNAVAILABLE) from None

def _revision(field: str) -> str:
    value = CONFIG.get(field)
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise HTTPException(status_code=503, detail=RANGE_UNAVAILABLE)
    return value

@lru_cache(maxsize=1)
def _research_contract() -> ResearchContract:
    path = CONFIG.get("challenge_contract_path")
    if not isinstance(path, str):
        raise HTTPException(status_code=503, detail=RESEARCH_TELEMETRY_UNAVAILABLE)
    try:
        value = research_telemetry_contract(Path(path).resolve().parents[1])
        return ResearchContract.from_mapping(value)
    except (OSError, yaml.YAMLError, DomainError):
        raise HTTPException(status_code=503, detail=RESEARCH_TELEMETRY_UNAVAILABLE) from None

def _research_store() -> ResearchStore:
    database = CONFIG.get("research_database_path")
    pseudonym_key_file = CONFIG.get("research_pseudonym_key_file")
    content_key_file = CONFIG.get("research_content_key_file")
    if not all(isinstance(value, str) for value in (
        database, pseudonym_key_file, content_key_file,
    )):
        raise HTTPException(status_code=503, detail=RESEARCH_TELEMETRY_UNAVAILABLE)
    try:
        store = ResearchStore(
            Path(database),
            contract=_research_contract(),
            pseudonym_key=_regular_owner_file(Path(pseudonym_key_file)),
            content_key=_regular_owner_binary_file(Path(content_key_file), exact_size=32),
        )
        capture = RESEARCH_RUNTIME_CONFIG.capture_signals
        if set(capture) != set(store.contract.capture_signals):
            raise DomainError("research store: invalid capture policy")
        for signal, enabled in capture.items():
            store.set_capture_signal(signal, enabled=enabled)
        return store
    except (OSError, DomainError, RuntimeError):
        raise HTTPException(status_code=503, detail=RESEARCH_TELEMETRY_UNAVAILABLE) from None
