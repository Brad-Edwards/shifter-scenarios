"""Loopback-only durable agent-state worker with a supervised restart boundary."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import stat
import time
from pathlib import Path
from typing import Annotated, Any, Literal

import psycopg
import yaml
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field


RESTART_EXIT_CODE = 75
SERVICE_AUTHENTICATION_REQUIRED = "service authentication required"
WORKER_UNAVAILABLE = "agent state worker unavailable"
SHA256_PREFIX = "sha256:"
NAMESPACE_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$"
DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
ERROR_RESPONSES = {
    401: {"description": "Service authentication required"},
    409: {"description": "Durable state conflicts with the current request"},
    422: {"description": "Submitted restart evidence is invalid"},
    503: {"description": "Agent-state worker dependency unavailable"},
}
BACKGROUND_TASKS: set[asyncio.Task[None]] = set()
CONFIG_PATH = Path(os.environ.get("KEPLEROPS_CONFIG", "/etc/keplerops/runtime.yaml"))
CONFIG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
if not isinstance(CONFIG, dict):
    raise RuntimeError("agent worker: invalid configuration")
BOOT_ID = "boot-" + secrets.token_hex(12)
app = FastAPI(title="KeplerOps agent-state worker", docs_url=None, redoc_url=None)


class MemoryWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    range_instance: str = Field(pattern=NAMESPACE_PATTERN)
    participant: str = Field(pattern=NAMESPACE_PATTERN)
    reset_generation: int = Field(ge=0)
    session_id: str = Field(pattern=r"^session-[a-z0-9-]{4,48}$")
    thread_id: str = Field(pattern=r"^thread-[a-z0-9-]{4,48}$")
    prompt_digest: str = Field(pattern=DIGEST_PATTERN)
    memory: str = Field(min_length=96, max_length=2048)
    marker: str = Field(pattern=r"^persist-[a-z0-9]{6,32}$")


class MemoryUseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    range_instance: str = Field(pattern=NAMESPACE_PATTERN)
    participant: str = Field(pattern=NAMESPACE_PATTERN)
    reset_generation: int = Field(ge=0)
    challenge_id: Literal[
        "kep-m05-a", "kep-m05-b", "kep-m05-c", "kep-m05-d", "kep-m05-e",
    ]
    session_id: str = Field(pattern=r"^session-[a-z0-9-]{4,48}$")
    thread_id: str = Field(pattern=r"^thread-[a-z0-9-]{4,48}$")
    prompt_digest: str = Field(pattern=DIGEST_PATTERN)


class MemoryUseCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    use_id: str = Field(pattern=r"^amu-[a-z0-9]{24}$")
    status: Literal["passed", "not_satisfied"]
    effect_digest: str = Field(pattern=DIGEST_PATTERN)
    tool_executed: bool


class RestartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    range_instance: str = Field(pattern=NAMESPACE_PATTERN)
    participant: str = Field(pattern=NAMESPACE_PATTERN)
    reset_generation: int = Field(ge=0)


class RestartAttestationRequest(RestartRequest):
    old_boot_id: str = Field(pattern=r"^boot-[0-9a-f]{24}$")
    new_boot_id: str = Field(pattern=r"^boot-[0-9a-f]{24}$")


def _owner_file(path: Path) -> bytes:
    metadata = path.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_mode & 0o077
    ):
        raise RuntimeError("agent worker: credential file invalid")
    value = path.read_bytes().strip()
    if not 16 <= len(value) <= 4096:
        raise RuntimeError("agent worker: credential value invalid")
    return value


def _service_authorized(
    x_service_token: Annotated[str | None, Header()] = None,
) -> None:
    token_file = CONFIG.get("service_token_file")
    if not isinstance(token_file, str) or not x_service_token:
        raise HTTPException(status_code=401, detail=SERVICE_AUTHENTICATION_REQUIRED)
    try:
        expected = _owner_file(Path(token_file)).decode("utf-8")
    except (OSError, UnicodeError, RuntimeError):
        raise HTTPException(status_code=503, detail=WORKER_UNAVAILABLE) from None
    if not hmac.compare_digest(expected, x_service_token):
        raise HTTPException(status_code=401, detail=SERVICE_AUTHENTICATION_REQUIRED)


def _generation() -> int:
    path = CONFIG.get("generation_file")
    try:
        generation = int(Path(str(path)).read_text(encoding="ascii").strip())
    except (OSError, TypeError, ValueError):
        raise HTTPException(status_code=503, detail=WORKER_UNAVAILABLE) from None
    if generation < 0:
        raise HTTPException(status_code=503, detail=WORKER_UNAVAILABLE)
    return generation


def _validate_scope(range_instance: str, reset_generation: int) -> None:
    if range_instance != CONFIG.get("range_instance") or reset_generation != _generation():
        raise HTTPException(status_code=409, detail="agent state scope mismatch")


def _postgres():
    host = CONFIG.get("postgres_host")
    password_file = CONFIG.get("postgres_password_file")
    if not isinstance(host, str) or not isinstance(password_file, str):
        raise HTTPException(status_code=503, detail=WORKER_UNAVAILABLE)
    try:
        return psycopg.connect(
            host=host,
            port=5432,
            dbname="keplerops",
            user="keplerops",
            password=_owner_file(Path(password_file)).decode("utf-8"),
            sslmode="verify-full",
            sslrootcert="/run/tls/ca.crt",
            connect_timeout=5,
        )
    except (OSError, UnicodeError, RuntimeError, psycopg.Error):
        raise HTTPException(status_code=503, detail=WORKER_UNAVAILABLE) from None


def _digest(kind: str, *values: object) -> str:
    key_file = CONFIG.get("service_token_file")
    if not isinstance(key_file, str):
        raise HTTPException(status_code=503, detail=WORKER_UNAVAILABLE)
    material = json.dumps(
        [kind, *values], separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return SHA256_PREFIX + hmac.new(
        _owner_file(Path(key_file)), material, hashlib.sha256
    ).hexdigest()


def _state_id(range_instance: str, participant: str, generation: int) -> str:
    value = hashlib.sha256(
        f"{range_instance}:{participant}:{generation}".encode("utf-8")
    ).hexdigest()[:24]
    return "ams-" + value


def _use_id() -> str:
    return "amu-" + secrets.token_hex(12)


def _restart_id(old_boot_id: str, new_boot_id: str, participant: str) -> str:
    value = hashlib.sha256(
        f"{old_boot_id}:{new_boot_id}:{participant}".encode("utf-8")
    ).hexdigest()[:24]
    return "restart-" + value


def _record_boot() -> None:
    generation = _generation()
    range_instance = CONFIG.get("range_instance")
    if not isinstance(range_instance, str):
        raise RuntimeError("agent worker: range unavailable")
    for attempt in range(30):
        try:
            with _postgres() as connection:
                connection.execute(
                    "INSERT INTO agent_runtime_boots "
                    "(boot_id, range_instance, reset_generation, process_id) "
                    "VALUES (%s, %s, %s, %s)",
                    (BOOT_ID, range_instance, generation, os.getpid()),
                )
            return
        except HTTPException:
            if attempt == 29:
                raise
            time.sleep(2)


@app.on_event("startup")
def start_worker() -> None:
    _record_boot()


@app.get("/healthz", responses=ERROR_RESPONSES)
def health(_: Annotated[None, Depends(_service_authorized)]) -> dict[str, Any]:
    return {"status": "ready", "boot_id": BOOT_ID, "process_id": os.getpid()}


@app.post("/v1/memory", responses=ERROR_RESPONSES)
def write_memory(
    request: MemoryWriteRequest,
    _: Annotated[None, Depends(_service_authorized)],
) -> dict[str, Any]:
    _validate_scope(request.range_instance, request.reset_generation)
    state_id = _state_id(
        request.range_instance, request.participant, request.reset_generation
    )
    with _postgres() as connection:
        row = connection.execute(
            "SELECT state_version FROM agent_memories WHERE "
            "range_instance=%s AND participant=%s AND reset_generation=%s FOR UPDATE",
            (request.range_instance, request.participant, request.reset_generation),
        ).fetchone()
        state_version = 1 if row is None else int(row[0]) + 1
        state_digest = _digest(
            "agent-memory",
            request.range_instance,
            request.participant,
            request.reset_generation,
            state_version,
            request.memory,
            request.session_id,
            request.thread_id,
            BOOT_ID,
        )
        connection.execute(
            "INSERT INTO agent_memories "
            "(state_id, range_instance, participant, reset_generation, state_version, "
            "state_digest, marker, memory, plant_session_id, plant_thread_id, "
            "plant_boot_id, plant_prompt_digest) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (range_instance, participant, reset_generation) DO UPDATE SET "
            "state_version=EXCLUDED.state_version, state_digest=EXCLUDED.state_digest, "
            "marker=EXCLUDED.marker, memory=EXCLUDED.memory, "
            "plant_session_id=EXCLUDED.plant_session_id, "
            "plant_thread_id=EXCLUDED.plant_thread_id, plant_boot_id=EXCLUDED.plant_boot_id, "
            "plant_prompt_digest=EXCLUDED.plant_prompt_digest, updated_at=clock_timestamp()",
            (
                state_id,
                request.range_instance,
                request.participant,
                request.reset_generation,
                state_version,
                state_digest,
                request.marker,
                request.memory,
                request.session_id,
                request.thread_id,
                BOOT_ID,
                request.prompt_digest,
            ),
        )
    return {
        "state_id": state_id,
        "state_version": state_version,
        "state_digest": state_digest,
        "boot_id": BOOT_ID,
    }


def _memory_row(request: MemoryUseRequest) -> tuple[Any, ...]:
    with _postgres() as connection:
        row = connection.execute(
            "SELECT state_id, state_version, state_digest, marker, memory, "
            "plant_session_id, plant_thread_id, plant_boot_id, plant_prompt_digest "
            "FROM agent_memories WHERE range_instance=%s AND participant=%s "
            "AND reset_generation=%s",
            (request.range_instance, request.participant, request.reset_generation),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=409, detail="durable memory required")
    return row


def _restart_attestation(
    request: MemoryUseRequest, plant_boot_id: str,
) -> str | None:
    with _postgres() as connection:
        row = connection.execute(
            "SELECT restart_id FROM agent_runtime_restarts WHERE range_instance=%s "
            "AND participant=%s AND reset_generation=%s AND old_boot_id=%s "
            "AND new_boot_id=%s ORDER BY verified_at DESC LIMIT 1",
            (
                request.range_instance,
                request.participant,
                request.reset_generation,
                plant_boot_id,
                BOOT_ID,
            ),
        ).fetchone()
    return str(row[0]) if row is not None else None


@app.post("/v1/memory/use", responses=ERROR_RESPONSES)
def use_memory(
    request: MemoryUseRequest,
    _: Annotated[None, Depends(_service_authorized)],
) -> dict[str, Any]:
    _validate_scope(request.range_instance, request.reset_generation)
    row = _memory_row(request)
    use_id = _use_id()
    with _postgres() as connection:
        connection.execute(
            "INSERT INTO agent_memory_uses "
            "(use_id, state_id, range_instance, participant, reset_generation, "
            "challenge_id, use_session_id, use_thread_id, worker_boot_id, "
            "clean_prompt_digest, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'retrieved')",
            (
                use_id,
                row[0],
                request.range_instance,
                request.participant,
                request.reset_generation,
                request.challenge_id,
                request.session_id,
                request.thread_id,
                BOOT_ID,
                request.prompt_digest,
            ),
        )
        count = connection.execute(
            "SELECT count(*) FROM agent_memory_uses WHERE state_id=%s",
            (row[0],),
        ).fetchone()
    restart_id = _restart_attestation(request, str(row[7]))
    return {
        "use_id": use_id,
        "state_id": row[0],
        "state_version": row[1],
        "state_digest": row[2],
        "marker": row[3],
        "memory": row[4],
        "plant_session_id": row[5],
        "plant_thread_id": row[6],
        "plant_boot_id": row[7],
        "plant_prompt_digest": row[8],
        "use_count": int(count[0]),
        "boot_id": BOOT_ID,
        "restart_verified": restart_id is not None,
        "restart_id": restart_id,
    }


@app.post("/v1/memory/use/complete", responses=ERROR_RESPONSES)
def complete_memory_use(
    request: MemoryUseCompletionRequest,
    _: Annotated[None, Depends(_service_authorized)],
) -> dict[str, bool]:
    with _postgres() as connection:
        cursor = connection.execute(
            "UPDATE agent_memory_uses SET status=%s, effect_digest=%s, "
            "tool_executed=%s, updated_at=clock_timestamp() "
            "WHERE use_id=%s AND worker_boot_id=%s AND status='retrieved'",
            (
                request.status,
                request.effect_digest,
                request.tool_executed,
                request.use_id,
                BOOT_ID,
            ),
        )
    if cursor.rowcount != 1:
        raise HTTPException(status_code=409, detail="memory use unavailable")
    return {"recorded": True}


async def _exit_after_response() -> None:
    await asyncio.sleep(0.2)
    os._exit(RESTART_EXIT_CODE)


@app.post("/v1/restart", responses=ERROR_RESPONSES)
async def restart(
    request: RestartRequest,
    _: Annotated[None, Depends(_service_authorized)],
) -> dict[str, Any]:
    _validate_scope(request.range_instance, request.reset_generation)
    task = asyncio.create_task(_exit_after_response())
    BACKGROUND_TASKS.add(task)
    task.add_done_callback(BACKGROUND_TASKS.discard)
    return {"accepted": True, "old_boot_id": BOOT_ID, "process_id": os.getpid()}


@app.post("/v1/restart/attest", responses=ERROR_RESPONSES)
def attest_restart(
    request: RestartAttestationRequest,
    _: Annotated[None, Depends(_service_authorized)],
) -> dict[str, str]:
    _validate_scope(request.range_instance, request.reset_generation)
    if request.new_boot_id != BOOT_ID or request.old_boot_id == request.new_boot_id:
        raise HTTPException(status_code=422, detail="invalid restart boundary")
    restart_id = _restart_id(
        request.old_boot_id, request.new_boot_id, request.participant
    )
    with _postgres() as connection:
        boots = connection.execute(
            "SELECT count(*) FROM agent_runtime_boots WHERE range_instance=%s "
            "AND reset_generation=%s AND boot_id IN (%s, %s)",
            (
                request.range_instance,
                request.reset_generation,
                request.old_boot_id,
                request.new_boot_id,
            ),
        ).fetchone()
        if boots is None or int(boots[0]) != 2:
            raise HTTPException(status_code=422, detail="invalid restart boundary")
        connection.execute(
            "INSERT INTO agent_runtime_restarts "
            "(restart_id, range_instance, participant, reset_generation, "
            "old_boot_id, new_boot_id) VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (restart_id) DO NOTHING",
            (
                restart_id,
                request.range_instance,
                request.participant,
                request.reset_generation,
                request.old_boot_id,
                request.new_boot_id,
            ),
        )
    return {"restart_id": restart_id, "new_boot_id": BOOT_ID}
