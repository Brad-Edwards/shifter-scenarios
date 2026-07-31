from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import FileResponse
from keplerops_runtime.foundation.auth_storage import _require_role
from keplerops_runtime.foundation.config import CONFIG, NOT_FOUND
from keplerops_runtime.foundation.contracts import _adversarial_challenge_contracts, _agent_challenge_contracts, _backdoor_challenge_contracts, _capstone_challenge_contracts, _context_challenge_contracts, _evasion_challenge_contracts, _extraction_challenge_contracts, _persistence_challenge_contracts, _secrets_challenge_contracts, _training_challenge_contracts
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
from typing import Any


def _participant_agent_challenges() -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in _agent_challenge_contracts()[challenge_id].items()
            if key not in {"hints", "hint_costs"}
        }
        for challenge_id in AGENT_CHALLENGE_IDS
    ]

def _participant_evasion_challenges() -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in _evasion_challenge_contracts()[challenge_id].items()
            if key not in {"hints", "hint_costs"}
        }
        for challenge_id in EVASION_CHALLENGE_IDS
    ]

def _participant_context_challenges() -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in _context_challenge_contracts()[challenge_id].items()
            if key not in {"hints", "hint_costs"}
        }
        for challenge_id in CONTEXT_CHALLENGE_IDS
    ]

def _participant_secrets_challenges() -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in _secrets_challenge_contracts()[challenge_id].items()
            if key not in {"hints", "hint_costs"}
        }
        for challenge_id in SECRETS_CHALLENGE_IDS
    ]

def _participant_persistence_challenges() -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in _persistence_challenge_contracts()[challenge_id].items()
            if key not in {"hints", "hint_costs"}
        }
        for challenge_id in PERSISTENCE_CHALLENGE_IDS
    ]

def _participant_adversarial_challenges() -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in _adversarial_challenge_contracts()[challenge_id].items()
            if key not in {"hints", "hint_costs"}
        }
        for challenge_id in ADVERSARIAL_CHALLENGE_IDS
    ]

def _participant_training_challenges() -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in _training_challenge_contracts()[challenge_id].items()
            if key not in {"hints", "hint_costs"}
        }
        for challenge_id in TRAINING_CHALLENGE_IDS
    ]

def _participant_extraction_challenges() -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in _extraction_challenge_contracts()[challenge_id].items()
            if key not in {"hints", "hint_costs"}
        }
        for challenge_id in EXTRACTION_CHALLENGE_IDS
    ]

def _participant_backdoor_challenges() -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in _backdoor_challenge_contracts()[challenge_id].items()
            if key not in {"hints", "hint_costs"}
        }
        for challenge_id in BACKDOOR_CHALLENGE_IDS
    ]

def _participant_capstone_challenges() -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in _capstone_challenge_contracts()[challenge_id].items()
            if key not in {"hints", "hint_costs"}
        }
        for challenge_id in CAPSTONE_CHALLENGE_IDS
    ]

def _participant_ui(config_key: str) -> FileResponse:
    _require_role("gateway")
    path = CONFIG.get(config_key)
    if not isinstance(path, str) or not Path(path).is_file():
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return FileResponse(
        path,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )
