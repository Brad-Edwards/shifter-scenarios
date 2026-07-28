"""FastAPI process for the range-local green activity sidecar."""

from __future__ import annotations

import hashlib
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from .clients import GreenServiceClients, GreenServiceConfig
from .runtime import GreenActivityEngine
from .service import GreenActivityService

CONFIG_PATH = Path(os.environ.get("KEPLEROPS_CONFIG", "/etc/keplerops/runtime.yaml"))
SDL_PATH = Path(
    os.environ.get(
        "KEPLEROPS_GREEN_SDL",
        "/opt/keplerops/sdl/keplerops-ai.sdl.yaml",
    )
)
STATE_ROOT = Path(
    os.environ.get(
        "KEPLEROPS_GREEN_STATE_ROOT",
        "/var/lib/keplerops/green-activity",
    )
)
GENERATION_FILE = Path("/run/keplerops/reset-generation")
TOKEN_FILE = Path("/run/keplerops/service-token")


def _build_service() -> GreenActivityService:
    config = GreenServiceConfig.from_runtime_config(CONFIG_PATH)
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    range_instance = str(payload["range_instance"])
    generation = int(GENERATION_FILE.read_text(encoding="utf-8").strip())
    public_seed = hashlib.sha256(
        f"keplerops-green-activity|{range_instance}".encode()
    ).hexdigest()
    clients = GreenServiceClients(config)
    engine = GreenActivityEngine.from_sdl(
        SDL_PATH,
        clients.executor(),
        state_root=STATE_ROOT,
        range_instance=range_instance,
        reset_generation=generation,
        public_seed=public_seed,
    )
    return GreenActivityService(engine, token_file=TOKEN_FILE)


SERVICE: GreenActivityService | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global SERVICE
    SERVICE = _build_service()
    SERVICE.start()
    try:
        yield
    finally:
        SERVICE.stop()


app = FastAPI(title="KeplerOps Green Activity", lifespan=lifespan)


class ControlBody(BaseModel):
    action: str
    reset_generation: int | None = None


def _service() -> GreenActivityService:
    if SERVICE is None:
        raise HTTPException(status_code=503, detail="green activity is not ready")
    return SERVICE


def _token(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="authentication required")
    return authorization.removeprefix("Bearer ")


@app.get(
    "/healthz",
    responses={503: {"description": "Green activity service is unavailable."}},
)
def health() -> dict[str, object]:
    return _service().health()


@app.get(
    "/readyz",
    responses={503: {"description": "Green activity service is unavailable."}},
)
def ready() -> dict[str, object]:
    status = _service().health()
    if status["status"] != "ok":
        raise HTTPException(status_code=503, detail=status)
    return status


@app.post(
    "/v1/run-once",
    responses={
        401: {"description": "Authentication is required."},
        403: {"description": "The supplied control token is invalid."},
        503: {"description": "Green activity service is unavailable."},
    },
)
def run_once(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    try:
        return _service().run_once(_token(authorization))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@app.post(
    "/v1/control",
    responses={
        401: {"description": "Authentication is required."},
        403: {"description": "The supplied control token is invalid."},
        422: {"description": "The control action or generation is invalid."},
        503: {"description": "Green activity service is unavailable."},
    },
)
def control(
    body: ControlBody,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    try:
        return _service().control(
            body.action,
            _token(authorization),
            reset_generation=body.reset_generation,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
