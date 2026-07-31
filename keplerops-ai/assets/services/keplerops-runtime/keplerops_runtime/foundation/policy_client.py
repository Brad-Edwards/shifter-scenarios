from __future__ import annotations

from domain import ApprovalSigner
from domain import SessionClaims
from fastapi import HTTPException
from keplerops_runtime.foundation.clients import _backend_http_client
from keplerops_runtime.foundation.config import APPROVAL_POLICY_UNAVAILABLE, CONFIG
from keplerops_runtime.modules.m09 import ApprovalDecision


async def _policy(session: SessionClaims, action: str) -> bool:
    opa_url = CONFIG.get("opa_url")
    if not isinstance(opa_url, str):
        return False
    payload = {"input": {"session": session._asdict(), "action": action}}
    client = _backend_http_client("policy", timeout=5.0)
    response = await client.post(f"{opa_url.rstrip('/')}/v1/data/keplerops/guardrails/allow", json=payload)
    return response.status_code == 200 and response.json().get("result") is True

async def _evasion_policy(session: SessionClaims, challenge_id: str) -> bool:
    opa_url = CONFIG.get("opa_url")
    if not isinstance(opa_url, str):
        return False
    payload = {
        "input": {
            "session": session._asdict(),
            "action": "evasion_probe",
            "challenge_id": challenge_id,
        }
    }
    client = _backend_http_client("evasion-policy", timeout=5.0)
    response = await client.post(
        f"{opa_url.rstrip('/')}/v1/data/keplerops/guardrails/allow",
        json=payload,
    )
    return response.status_code == 200 and response.json().get("result") is True

async def _secrets_policy(session: SessionClaims, challenge_id: str) -> bool:
    opa_url = CONFIG.get("opa_url")
    if not isinstance(opa_url, str):
        return False
    payload = {
        "input": {
            "session": session._asdict(),
            "action": "secrets_probe",
            "challenge_id": challenge_id,
        }
    }
    client = _backend_http_client("secrets-policy", timeout=5.0)
    response = await client.post(
        f"{opa_url.rstrip('/')}/v1/data/keplerops/guardrails/allow",
        json=payload,
    )
    return response.status_code == 200 and response.json().get("result") is True

async def _adversarial_policy(session: SessionClaims, challenge_id: str) -> bool:
    opa_url = CONFIG.get("opa_url")
    if not isinstance(opa_url, str):
        return False
    payload = {
        "input": {
            "session": session._asdict(),
            "action": "adversarial_probe",
            "challenge_id": challenge_id,
        }
    }
    client = _backend_http_client("adversarial-policy", timeout=5.0)
    response = await client.post(
        f"{opa_url.rstrip('/')}/v1/data/keplerops/guardrails/allow",
        json=payload,
    )
    return response.status_code == 200 and response.json().get("result") is True

async def _training_policy(session: SessionClaims, challenge_id: str) -> bool:
    opa_url = CONFIG.get("opa_url")
    if not isinstance(opa_url, str):
        return False
    payload = {
        "input": {
            "session": session._asdict(),
            "action": "training_poison",
            "challenge_id": challenge_id,
        }
    }
    client = _backend_http_client("training-policy", timeout=5.0)
    response = await client.post(
        f"{opa_url.rstrip('/')}/v1/data/keplerops/guardrails/allow",
        json=payload,
    )
    return response.status_code == 200 and response.json().get("result") is True

async def _extraction_policy(session: SessionClaims, challenge_id: str) -> bool:
    opa_url = CONFIG.get("opa_url")
    if not isinstance(opa_url, str):
        return False
    payload = {
        "input": {
            "session": session._asdict(),
            "action": "model_extract",
            "challenge_id": challenge_id,
        }
    }
    client = _backend_http_client("extraction-policy", timeout=5.0)
    response = await client.post(
        f"{opa_url.rstrip('/')}/v1/data/keplerops/guardrails/allow",
        json=payload,
    )
    return response.status_code == 200 and response.json().get("result") is True

async def _backdoor_policy(session: SessionClaims, challenge_id: str) -> bool:
    opa_url = CONFIG.get("opa_url")
    if not isinstance(opa_url, str):
        return False
    payload = {
        "input": {
            "session": session._asdict(),
            "action": "model_backdoor",
            "challenge_id": challenge_id,
        }
    }
    client = _backend_http_client("backdoor-policy", timeout=5.0)
    response = await client.post(
        f"{opa_url.rstrip('/')}/v1/data/keplerops/guardrails/allow",
        json=payload,
    )
    return response.status_code == 200 and response.json().get("result") is True

async def _capstone_policy(session: SessionClaims, challenge_id: str) -> bool:
    opa_url = CONFIG.get("opa_url")
    if not isinstance(opa_url, str):
        return False
    payload = {
        "input": {
            "session": session._asdict(),
            "action": "ai_capstone",
            "challenge_id": challenge_id,
        }
    }
    client = _backend_http_client("capstone-policy", timeout=5.0)
    response = await client.post(
        f"{opa_url.rstrip('/')}/v1/data/keplerops/guardrails/allow",
        json=payload,
    )
    return response.status_code == 200 and response.json().get("result") is True

async def _backdoor_approval_policy(
    session: SessionClaims,
    signer: ApprovalSigner,
    *,
    approval_kind: str,
) -> ApprovalDecision:
    opa_url = CONFIG.get("opa_url")
    if not isinstance(opa_url, str):
        raise HTTPException(status_code=503, detail=APPROVAL_POLICY_UNAVAILABLE)
    payload = {
        "input": {
            "session": session._asdict(),
            "action": "model_backdoor_approval",
            "approval": {
                "actor": signer.participant,
                "roles": list(signer.roles),
                "kind": approval_kind,
                "target_scope": "release",
                "signature_valid": True,
            },
        }
    }
    client = _backend_http_client("backdoor-approval-policy", timeout=5.0)
    response = await client.post(
        f"{opa_url.rstrip('/')}/v1/data/keplerops/guardrails/backdoor_approval",
        json=payload,
    )
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail=APPROVAL_POLICY_UNAVAILABLE)
    result = response.json().get("result")
    if (
        not isinstance(result, dict)
        or not isinstance(result.get("allow"), bool)
        or not isinstance(result.get("confused"), bool)
        or not isinstance(result.get("reason"), str)
    ):
        raise HTTPException(status_code=503, detail=APPROVAL_POLICY_UNAVAILABLE)
    return ApprovalDecision(result["allow"], result["confused"], result["reason"])
