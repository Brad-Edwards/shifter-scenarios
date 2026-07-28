from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi.responses import FileResponse
from keplerops_runtime.foundation.action_clients import _agent_action_request, _positive_int, _valid_sha256_digest
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, CONFIG, ERROR_RESPONSES, NOT_FOUND, RANGE_UNAVAILABLE, SHA256_PREFIX, WEB_DELIVERY_EXPORT_ROOT, WEB_DELIVERY_ID_PATTERN, WEB_DELIVERY_PREVIEW_ROOT
from keplerops_runtime.foundation.policy_client import _evasion_policy
from keplerops_runtime.modules.m02.schemas import WebDeliveryExploitRequest, WebDeliveryRequest
from keplerops_runtime.modules.m02.store import _ensure_model_supply_schema
from model_supply import WebDeliveryProof
from pathlib import Path
from typing import Annotated
from typing import Any
import hashlib
import hmac
import re
import secrets

router = APIRouter()


def _web_delivery_path(delivery_id: str) -> Path:
    return WEB_DELIVERY_EXPORT_ROOT / f"{delivery_id}.html"

@router.post("/v1/evasion/web-deliveries", responses=ERROR_RESPONSES)
async def stage_web_delivery(
    request: WebDeliveryRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _evasion_policy(session, "kep-m02-k"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    if (
        "{{NONCE}}" not in request.content_template
        or "<script" not in request.content_template.lower()
        or "dataset.kepleropsEffect" not in request.content_template
        or "data-keplerops-effect=" in request.content_template
    ):
        raise HTTPException(status_code=422, detail="browser payload is incomplete")
    _ensure_model_supply_schema()
    delivery_id = "wex-" + secrets.token_hex(12)
    nonce = secrets.token_hex(12)
    content = request.content_template.replace("{{NONCE}}", nonce)
    expected_digest = SHA256_PREFIX + hashlib.sha256(content.encode("utf-8")).hexdigest()
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO web_deliveries (delivery_id, range_instance, participant, "
            "reset_generation, challenge_id, nonce, content, expected_digest) VALUES "
            "(%s, %s, %s, %s, 'kep-m02-k', %s, %s, %s)",
            (
                delivery_id,
                session.range_instance,
                session.participant,
                generation,
                nonce,
                content,
                expected_digest,
            ),
        )
    return {
        "delivery_id": delivery_id,
        "nonce": nonce,
        "expected_digest": expected_digest,
        "exploit_path": f"../deliveries/{delivery_id}.html",
        "delivery_url": (
            "https://inference-gateway.keplerops.lab/public/evasion/deliveries/"
            + delivery_id
        ),
    }

@router.post("/public/evasion/previews/{delivery_id}", responses=ERROR_RESPONSES)
async def exploit_web_preview(
    delivery_id: str, request: WebDeliveryExploitRequest
) -> dict[str, str]:
    _require_role("gateway")
    if re.fullmatch(WEB_DELIVERY_ID_PATTERN, delivery_id) is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    _require_ready()
    _ensure_model_supply_schema()
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT content, expected_digest, stored_digest FROM web_deliveries WHERE "
            "delivery_id=%s AND range_instance=%s AND reset_generation=%s",
            (delivery_id, CONFIG["range_instance"], _require_ready()),
        )
        row = cursor.fetchone()
    if (
        not isinstance(row, tuple)
        or len(row) != 3
        or not isinstance(row[0], str)
        or not isinstance(row[1], str)
    ):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    target = (WEB_DELIVERY_PREVIEW_ROOT / request.path).resolve()
    expected_target = _web_delivery_path(delivery_id).resolve()
    if target != expected_target:
        raise HTTPException(status_code=422, detail="preview export target rejected")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    content = row[0].encode("utf-8")
    digest = SHA256_PREFIX + hashlib.sha256(content).hexdigest()
    if not hmac.compare_digest(digest, row[1]):
        raise HTTPException(status_code=503, detail=RANGE_UNAVAILABLE)
    if row[2] is None:
        target.write_bytes(content)
        target.chmod(0o400)
        with _postgres() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE web_deliveries SET stored_digest=%s, stored_path=%s, "
                "writer='participant-public-exploit', written_at=clock_timestamp() WHERE "
                "delivery_id=%s AND stored_digest IS NULL",
                (digest, str(target), delivery_id),
            )
    elif row[2] != digest or not target.is_file() or target.read_bytes() != content:
        raise HTTPException(status_code=409, detail="delivery already diverged")
    return {"delivery_id": delivery_id, "stored_digest": digest, "writer": "public-preview"}

@router.get(
    "/public/evasion/deliveries/{delivery_id}",
    response_class=FileResponse,
    responses=ERROR_RESPONSES,
)
def public_web_delivery(delivery_id: str) -> FileResponse:
    _require_role("gateway")
    if re.fullmatch(WEB_DELIVERY_ID_PATTERN, delivery_id) is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    _ensure_model_supply_schema()
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT stored_path, stored_digest FROM web_deliveries WHERE delivery_id=%s AND "
            "range_instance=%s AND reset_generation=%s AND writer='participant-public-exploit'",
            (delivery_id, CONFIG["range_instance"], _require_ready()),
        )
        row = cursor.fetchone()
    if (
        not isinstance(row, tuple)
        or len(row) != 2
        or not all(isinstance(value, str) for value in row)
    ):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    path = Path(row[0])
    if path.resolve() != _web_delivery_path(delivery_id).resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    content = path.read_bytes()
    if not hmac.compare_digest(SHA256_PREFIX + hashlib.sha256(content).hexdigest(), row[1]):
        raise HTTPException(status_code=503, detail=RANGE_UNAVAILABLE)
    return FileResponse(path, media_type="text/html", headers={"X-Content-SHA256": row[1]})

async def _web_delivery_proof(
    session: SessionClaims, delivery_id: str
) -> WebDeliveryProof:
    url = (
        "https://inference-gateway.keplerops.lab/public/evasion/deliveries/"
        + delivery_id
    )
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT nonce, stored_digest, writer FROM web_deliveries WHERE delivery_id=%s AND "
            "range_instance=%s AND participant=%s AND reset_generation=%s",
            (
                delivery_id,
                session.range_instance,
                session.participant,
                _require_ready(),
            ),
        )
        row = cursor.fetchone()
    if (
        not isinstance(row, tuple)
        or len(row) != 3
        or not all(isinstance(value, str) for value in row)
        or row[2] != "participant-public-exploit"
    ):
        raise HTTPException(status_code=409, detail="web delivery exploit is incomplete")
    payload = await _agent_action_request("/v1/browser/open", {"url": url})
    process_id = payload.get("browser_pid")
    dom = payload.get("dom")
    browser_digest = payload.get("source_digest")
    effect_digest = payload.get("dom_digest")
    if (
        payload.get("rendered") is not True
        or not _positive_int(process_id)
        or not isinstance(dom, str)
        or f'data-keplerops-effect="{row[0]}"' not in dom
        or browser_digest != row[1]
        or not _valid_sha256_digest(effect_digest)
    ):
        raise HTTPException(status_code=409, detail="agent browser effect is incomplete")
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE web_deliveries SET browser_digest=%s, browser_process_id=%s, "
            "effect_digest=%s, visited_at=clock_timestamp() WHERE delivery_id=%s",
            (browser_digest, process_id, effect_digest, delivery_id),
        )
    return WebDeliveryProof(
        exploit_id=delivery_id,
        delivery_route="public-exploit",
        writer_role="participant",
        stored_digest=row[1],
        browser_digest=browser_digest,
        browser_visitor="agent",
        process_id=process_id,
        effect_digest=effect_digest,
        operator_uploaded=False,
    )
