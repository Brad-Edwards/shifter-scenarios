"""KeplerOps authenticated live-camera and WebRTC boundary."""

from __future__ import annotations

import base64
import hmac
import json
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, AsyncIterator, Literal

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from storage import CameraState, digest_text, utc_now
from webrtc import (
    DATA_CHANNEL_LABEL,
    CaptureRejected,
    PeerManager,
    SessionRuntime,
    expiry_timestamp,
)


STATE_ROOT = Path(
    os.environ.get("PLATFORM_CAMERA_STATE_ROOT", "/var/lib/keplerops-platform-camera")
)
STATIC_ROOT = Path(__file__).resolve().parent / "static"
DEFAULT_ML_BASE_URL = "http://platform-ml:8470"  # NOSONAR
ML_BASE_URL = os.environ.get("PLATFORM_CAMERA_ML_BASE_URL", DEFAULT_ML_BASE_URL)
DEFAULT_INIT_TOKEN = "keplerops-platform-camera-session"  # NOSONAR: synthetic.
DEFAULT_ADMIN_TOKEN = "keplerops-platform-camera-operator"  # NOSONAR: synthetic.
SESSION_TTL_SECONDS = 1_200
JSON_MEDIA_TYPE = "application/json"
BEARER_REQUIRED = "bearer authentication required"

Identifier = Annotated[
    str,
    Field(
        min_length=3,
        max_length=96,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:@-]{2,95}$",
    ),
]


class SessionInitiation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    participant_id: Identifier
    range_id: Identifier
    client_timestamp_ms: Annotated[int, Field(ge=0)]


class Offer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sdp: Annotated[str, Field(min_length=64, max_length=131_072)]
    type: Literal["offer"]


class VisionForwardError(RuntimeError):
    def __init__(self, message: str, details: dict[str, Any]) -> None:
        super().__init__(message)
        self.details = details


class PlatformMLClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=3.0),
            follow_redirects=False,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
            trust_env=False,
        )

    async def classify(self, request: dict[str, str]) -> dict[str, Any]:
        response = await self.client.post(
            f"{self.base_url}/v1/vision/classify",
            headers={"Content-Type": JSON_MEDIA_TYPE},
            json=request,
        )
        body = self._body(response)
        captured = {
            "http_status": response.status_code,
            "headers": dict(response.headers),
            "body": body,
        }
        if response.status_code < 200 or response.status_code >= 300:
            raise VisionForwardError("platform-ml rejected the frame", captured)
        if not isinstance(body, dict):
            raise VisionForwardError(
                "platform-ml returned a non-object response", captured
            )
        return captured

    async def ready(self) -> dict[str, Any]:
        response = await self.client.get(f"{self.base_url}/readyz")
        body = self._body(response)
        if response.status_code != 200:
            raise VisionForwardError(
                "platform-ml is not ready",
                {"http_status": response.status_code, "body": body},
            )
        return body if isinstance(body, dict) else {"body": body}

    async def close(self) -> None:
        await self.client.aclose()

    @staticmethod
    def _body(response: httpx.Response) -> Any:
        try:
            return response.json()
        except json.JSONDecodeError:
            return {"raw_base64": base64.b64encode(response.content).decode("ascii")}


def _bearer(authorization: str | None) -> str:
    if authorization is None:
        raise HTTPException(status_code=401, detail=BEARER_REQUIRED)  # NOSONAR
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail=BEARER_REQUIRED)  # NOSONAR
    return token


AUTH_RESPONSES = {
    401: {
        "description": "Bearer authentication failed",
        "content": {JSON_MEDIA_TYPE: {"example": {"detail": BEARER_REQUIRED}}},
    }
}
SESSION_RESPONSES = {
    **AUTH_RESPONSES,
    410: {
        "description": "The camera session is closed or expired",
        "content": {
            JSON_MEDIA_TYPE: {"example": {"detail": "session is closed or expired"}}
        },
    },
}
OFFER_RESPONSES = {
    **SESSION_RESPONSES,
    409: {"description": "The WebRTC offer or capture state was rejected"},
}
READY_RESPONSES = {503: {"description": "Camera state or platform-ml is not ready"}}


def _require_session(
    manager: PeerManager, session_id: str, authorization: str | None
) -> SessionRuntime:
    token = _bearer(authorization)
    session = manager.get_session(session_id)
    if session is None or not hmac.compare_digest(
        digest_text(token), session.session_token_digest
    ):
        raise HTTPException(  # NOSONAR - every caller declares AUTH_RESPONSES.
            status_code=401, detail="session authentication failed"
        )
    if session.closed or time.monotonic() >= session.expires_monotonic:
        raise HTTPException(  # NOSONAR - every caller declares SESSION_RESPONSES.
            status_code=410, detail="session is closed or expired"
        )
    return session


def _require_admin(value: str | None) -> None:
    configured = os.environ.get("PLATFORM_CAMERA_ADMIN_TOKEN", DEFAULT_ADMIN_TOKEN)
    if value is None or not hmac.compare_digest(value, configured):
        raise HTTPException(status_code=401, detail="operator authentication required")


def _register_middleware_and_validation(app: FastAPI, state: CameraState) -> None:
    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        response.headers["Permissions-Policy"] = "camera=(self), microphone=()"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        raw = await request.body()
        details = [
            {key: value for key, value in item.items() if key not in {"ctx", "input"}}
            for item in error.errors()
        ]
        response = {"detail": details}
        state.append_event(
            {
                "schema_version": 1,
                "event_id": uuid.uuid4().hex,
                "event_name": "platform_camera.request_rejected",
                "observed_at": utc_now(),
                "operation": f"{request.method} {request.url.path}",
                "status": "rejected",
                "request": {
                    "content_type": request.headers.get("content-type"),
                    "body_base64": base64.b64encode(raw[:256_000]).decode("ascii"),
                    "body_truncated": len(raw) > 256_000,
                },
                "response": response,
            }
        )
        return JSONResponse(status_code=422, content=response)


def _register_participant_and_status_routes(
    app: FastAPI, state: CameraState, ml: PlatformMLClient
) -> None:
    @app.get("/", response_class=FileResponse)
    def participant_surface() -> FileResponse:
        return FileResponse(STATIC_ROOT / "index.html", media_type="text/html")

    @app.get("/app.js", response_class=FileResponse)
    def participant_javascript() -> FileResponse:
        return FileResponse(STATIC_ROOT / "app.js", media_type="application/javascript")

    @app.get("/styles.css", response_class=FileResponse)
    def participant_styles() -> FileResponse:
        return FileResponse(STATIC_ROOT / "styles.css", media_type="text/css")

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok", "transport": "webrtc"}

    @app.get("/readyz", responses=READY_RESPONSES)
    async def readiness() -> dict[str, Any]:
        if not state.ready():
            raise HTTPException(status_code=503, detail="camera state is not writable")
        try:
            ml_ready = await ml.ready()
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "message": "platform-ml vision dependency is not ready",
                    "error_type": type(error).__name__,
                },
            ) from error
        return {
            "status": "ready",
            "transport": "aiortc-webrtc",
            "capture_protocol": DATA_CHANNEL_LABEL,
            "platform_ml": ml_ready,
        }


def _register_session_create_route(
    app: FastAPI, state: CameraState, manager: PeerManager
) -> None:
    @app.post("/v1/sessions", status_code=201, responses=AUTH_RESPONSES)
    def create_session_endpoint(
        value: SessionInitiation,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        init_token = _bearer(authorization)
        configured = os.environ.get("PLATFORM_CAMERA_INIT_TOKEN", DEFAULT_INIT_TOKEN)
        if not hmac.compare_digest(init_token, configured):
            raise HTTPException(status_code=401, detail="session initiation denied")
        session_id = uuid.uuid4().hex
        session_token = secrets.token_urlsafe(32)
        session_token_digest = digest_text(session_token)
        expires_at, expires_monotonic = expiry_timestamp(SESSION_TTL_SECONDS)
        created_at = utc_now()
        initiation = value.model_dump(mode="json")
        session = SessionRuntime(
            session_id=session_id,
            participant_id=value.participant_id,
            range_id=value.range_id,
            session_token_digest=session_token_digest,
            created_at=created_at,
            expires_at=expires_at,
            expires_monotonic=expires_monotonic,
        )
        state.create_session(
            session_id=session_id,
            session_token_digest=session_token_digest,
            initiation=initiation,
            expires_at=expires_at,
        )
        manager.add_session(session)
        response = {
            "session_id": session_id,
            "session_token": session_token,
            "expires_at": expires_at,
            "offer_url": f"/v1/sessions/{session_id}/offer",
            "data_channel_label": DATA_CHANNEL_LABEL,
        }
        state.append_event(
            {
                "schema_version": 1,
                "event_id": uuid.uuid4().hex,
                "event_name": "platform_camera.session_created",
                "observed_at": created_at,
                "operation": "sessions.create",
                "status": "succeeded",
                "session": {
                    "session_id": session_id,
                    "participant_id": value.participant_id,
                    "range_id": value.range_id,
                    "session_token_digest": session_token_digest,
                    "expires_at": expires_at,
                },
                "request": {
                    "initiation": initiation,
                    "init_token_digest": digest_text(init_token),
                },
                "response": {
                    key: item
                    for key, item in response.items()
                    if key != "session_token"
                },
            }
        )
        return response


def _register_session_operation_routes(
    app: FastAPI, state: CameraState, manager: PeerManager
) -> None:
    @app.post("/v1/sessions/{session_id}/offer", responses=OFFER_RESPONSES)
    async def offer_endpoint(
        session_id: str,
        value: Offer,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, str]:
        session = _require_session(manager, session_id, authorization)
        try:
            return await manager.accept_offer(
                session, sdp=value.sdp, description_type=value.type
            )
        except CaptureRejected as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/v1/sessions/{session_id}/frames",
        status_code=415,
        responses={**SESSION_RESPONSES, 415: {"description": "Uploads are rejected"}},
    )
    def reject_uploaded_frame(
        session_id: str,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        session = _require_session(manager, session_id, authorization)
        event = PeerManager._event(
            session,
            event_name="platform_camera.upload_rejected",
            operation="frames.upload",
            status="rejected",
            request={
                "content_type": request.headers.get("content-type"),
                "content_length": request.headers.get("content-length"),
            },
            response={"reason": "frames are accepted only from a live WebRTC track"},
        )
        state.append_event(event)
        return JSONResponse(
            status_code=415,
            content={
                "detail": "uploaded or prerecorded files cannot satisfy live capture"
            },
        )

    @app.post("/v1/sessions/{session_id}/close", responses=SESSION_RESPONSES)
    async def close_session_endpoint(
        session_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, str]:
        _require_session(manager, session_id, authorization)
        await manager.close_session(session_id)
        return {"status": "closed", "session_id": session_id}


def _register_admin_routes(
    app: FastAPI, state: CameraState, manager: PeerManager
) -> None:
    @app.post("/v1/admin/reset", responses=AUTH_RESPONSES)
    async def reset(
        x_platform_camera_admin_token: Annotated[str | None, Header()] = None,
    ) -> dict[str, int | str]:
        _require_admin(x_platform_camera_admin_token)
        await manager.close_all()
        return state.reset()

    @app.get("/v1/admin/events", responses=AUTH_RESPONSES)
    def events(
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        x_platform_camera_admin_token: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        _require_admin(x_platform_camera_admin_token)
        records = state.recent_events(limit)
        return {"record_count": len(records), "records": records}


def create_app(state_root: Path = STATE_ROOT) -> FastAPI:
    state = CameraState(state_root)
    ml = PlatformMLClient(ML_BASE_URL)
    manager = PeerManager(state, ml.classify)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await manager.close_all()
        await ml.close()

    app = FastAPI(title="KeplerOps Platform Camera", version="1.0.0", lifespan=lifespan)
    app.state.camera_state = state
    app.state.peer_manager = manager
    app.state.platform_ml = ml
    _register_middleware_and_validation(app, state)
    _register_participant_and_status_routes(app, state, ml)
    _register_session_create_route(app, state, manager)
    _register_session_operation_routes(app, state, manager)
    _register_admin_routes(app, state, manager)
    return app


app = create_app()
