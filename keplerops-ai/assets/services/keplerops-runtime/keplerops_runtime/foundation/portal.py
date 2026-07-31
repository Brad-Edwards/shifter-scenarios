from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Response
from fastapi.responses import FileResponse
from keplerops_runtime.foundation.auth_storage import _require_ready, _require_role, _session
from keplerops_runtime.foundation.catalog import _participant_adversarial_challenges, _participant_agent_challenges, _participant_backdoor_challenges, _participant_capstone_challenges, _participant_context_challenges, _participant_evasion_challenges, _participant_extraction_challenges, _participant_persistence_challenges, _participant_secrets_challenges, _participant_training_challenges, _participant_ui
from keplerops_runtime.foundation.clients import _backend_http_client
from keplerops_runtime.foundation.config import ADVERSARIAL_ATTEMPT_PATH, AGENT_ATTEMPT_PATH, AUTHENTICATION_REQUIRED, BACKDOOR_ATTEMPT_PATH, CAPSTONE_ATTEMPT_PATH, CONFIG, CONTEXT_ATTEMPT_PATH, ERROR_RESPONSES, EVASION_ATTEMPT_PATH, EXTRACTION_ATTEMPT_PATH, IDENTITY_UNAVAILABLE, PERSISTENCE_TURN_PATH, SECRETS_ATTEMPT_PATH, SECRETS_INFER_PATH, SESSION_COOKIE, TLS_CA_PATH, TRAINING_ATTEMPT_PATH
from keplerops_runtime.foundation.schemas import BrowserLoginRequest
from typing import Annotated
from typing import Any

router = APIRouter()


@router.get("/agent-control", response_class=FileResponse, responses=ERROR_RESPONSES)
def agent_control_ui() -> FileResponse:
    return _participant_ui("agent_control_ui_path")

@router.get("/model-evasion", response_class=FileResponse, responses=ERROR_RESPONSES)
def model_evasion_ui() -> FileResponse:
    return _participant_ui("model_evasion_ui_path")

@router.get("/context-poisoning", response_class=FileResponse, responses=ERROR_RESPONSES)
def context_poisoning_ui() -> FileResponse:
    return _participant_ui("context_poisoning_ui_path")

@router.get("/model-secrets", response_class=FileResponse, responses=ERROR_RESPONSES)
def model_secrets_ui() -> FileResponse:
    return _participant_ui("model_secrets_ui_path")

@router.get("/agent-persistence", response_class=FileResponse, responses=ERROR_RESPONSES)
def agent_persistence_ui() -> FileResponse:
    return _participant_ui("agent_persistence_ui_path")

@router.post("/v1/browser/login", responses=ERROR_RESPONSES)
async def browser_login(request: BrowserLoginRequest, response: Response) -> dict[str, bool]:
    _require_role("gateway")
    _require_ready()
    issuer = CONFIG.get("issuer")
    if not isinstance(issuer, str):
        raise HTTPException(status_code=503, detail=IDENTITY_UNAVAILABLE)
    client = _backend_http_client("identity-login", timeout=10.0, verify=TLS_CA_PATH)
    token_response = await client.post(
        f"{issuer.rstrip('/')}/protocol/openid-connect/token",
        data={
            "client_id": "keplerops-lab",
            "grant_type": "password",
            "username": request.username,
            "password": request.password,
        },
    )
    if token_response.status_code != 200:
        raise HTTPException(status_code=401, detail=AUTHENTICATION_REQUIRED)
    token = token_response.json().get("access_token")
    if not isinstance(token, str) or not 1 <= len(token) <= 8192:
        raise HTTPException(status_code=503, detail=IDENTITY_UNAVAILABLE)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        secure=True,
        httponly=True,
        samesite="strict",
        max_age=900,
        path="/",
    )
    return {"authenticated": True}

@router.post("/v1/browser/logout", status_code=204, response_class=Response)
def browser_logout(response: Response) -> Response:
    _require_role("gateway")
    response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="strict", path="/")
    return response

@router.get("/v1/challenges", responses=ERROR_RESPONSES)
def challenges(session: Annotated[SessionClaims, Depends(_session)]) -> dict[str, Any]:
    _require_role("portal")
    agent_rows = [
        {"id": row["challenge_id"], "title": row["title"], "entrypoint": AGENT_ATTEMPT_PATH}
        for row in _participant_agent_challenges()
    ]
    evasion_rows = [
        {"id": row["challenge_id"], "title": row["title"], "entrypoint": EVASION_ATTEMPT_PATH}
        for row in _participant_evasion_challenges()
    ]
    context_rows = [
        {"id": row["challenge_id"], "title": row["title"], "entrypoint": CONTEXT_ATTEMPT_PATH}
        for row in _participant_context_challenges()
    ]
    secrets_rows = [
        {
            "id": row["challenge_id"],
            "title": row["title"],
            "entrypoint": (
                SECRETS_INFER_PATH
                if row["challenge_id"] in {"kep-m04-a", "kep-m04-b"}
                else SECRETS_ATTEMPT_PATH
            ),
        }
        for row in _participant_secrets_challenges()
    ]
    persistence_rows = [
        {
            "id": row["challenge_id"],
            "title": row["title"],
            "entrypoint": PERSISTENCE_TURN_PATH,
        }
        for row in _participant_persistence_challenges()
    ]
    adversarial_rows = [
        {
            "id": row["challenge_id"],
            "title": row["title"],
            "entrypoint": ADVERSARIAL_ATTEMPT_PATH,
        }
        for row in _participant_adversarial_challenges()
    ]
    training_rows = [
        {
            "id": row["challenge_id"],
            "title": row["title"],
            "entrypoint": TRAINING_ATTEMPT_PATH,
        }
        for row in _participant_training_challenges()
    ]
    extraction_rows = [
        {
            "id": row["challenge_id"],
            "title": row["title"],
            "entrypoint": EXTRACTION_ATTEMPT_PATH,
        }
        for row in _participant_extraction_challenges()
    ]
    backdoor_rows = [
        {
            "id": row["challenge_id"],
            "title": row["title"],
            "entrypoint": BACKDOOR_ATTEMPT_PATH,
        }
        for row in _participant_backdoor_challenges()
    ]
    capstone_rows = [
        {
            "id": row["challenge_id"],
            "title": row["title"],
            "entrypoint": CAPSTONE_ATTEMPT_PATH,
        }
        for row in _participant_capstone_challenges()
    ]
    return {
        "range_instance": session.range_instance,
        "challenges": [
            *agent_rows,
            *evasion_rows,
            *context_rows,
            *secrets_rows,
            *persistence_rows,
            *adversarial_rows,
            *training_rows,
            *extraction_rows,
            *backdoor_rows,
            *capstone_rows,
        ],
    }
