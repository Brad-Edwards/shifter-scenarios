"""KeplerOps agent-platform software boundaries."""

import asyncio
import base64
import hashlib
import importlib.metadata
import ipaddress
import json
import os
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Callable, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from runtime import LocalAgentRuntime, ToolError
from state import (
    EVENT_SCHEMA_VERSION,
    SCHEMA_VERSION,
    SEED_AGENT_ID,
    StateStore,
    canonical_json,
    digest_text,
    utc_now,
)
from workers import (
    DEFAULT_WORKER_IMAGE,
    DockerWorkerController,
    WorkerError,
    WorkerOwnershipError,
    WorkerUnavailable,
)


ADMIN_HEADER = "X-Platform-Admin-Token"
AGENT_ID_HEADER = "X-Agent-Id"
AGENT_TOKEN_HEADER = "X-Agent-Token"
DEFAULT_ADMIN_TOKEN = "keplerops-platform-agent-admin"
DEFAULT_AGENT_TOKEN = "keplerops-platform-agent-alpha"
MAX_RELAY_BYTES = 65_536
MAX_EXPORT_BYTES = 65_536
VERSION_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+$"
IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9._-]{2,63}$"
UNAUTHORIZED_RESPONSE = {"description": "Missing or invalid platform credential"}
NOT_FOUND_RESPONSE = {"description": "Requested platform resource was not found"}
CONFLICT_RESPONSE = {"description": "Requested operation conflicts with current state"}
PAYLOAD_TOO_LARGE_RESPONSE = {"description": "Request payload exceeds the bounded size"}
UNPROCESSABLE_RESPONSE = {"description": "Request cannot be executed safely"}
BAD_GATEWAY_RESPONSE = {
    "description": "Range-local upstream returned an invalid response"
}
SERVICE_UNAVAILABLE_RESPONSE = {
    "description": "Required platform service is unavailable"
}
IDENTITY_NOT_FOUND = "identity not found"


def _configured_token(
    *, file_variable: str, value_variable: str, synthetic_default: str
) -> str:
    if file_variable not in os.environ:
        return os.environ.get(value_variable, synthetic_default)
    configured_path = os.environ[file_variable]
    if not configured_path:
        raise RuntimeError(f"{file_variable} must name a readable, non-empty file")
    try:
        value = Path(configured_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise RuntimeError(
            f"{file_variable} must name a readable, non-empty file"
        ) from error
    if value.endswith("\r\n"):
        value = value[:-2]
    elif value.endswith("\n"):
        value = value[:-1]
    if not value:
        raise RuntimeError(f"{file_variable} must name a readable, non-empty file")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigurationRequest(StrictModel):
    agent_id: str = Field(pattern=IDENTIFIER_PATTERN)
    version: str = Field(pattern=VERSION_PATTERN)
    max_steps: int = Field(ge=1, le=8)
    tool_timeout_ms: int = Field(ge=50, le=5000)
    allowed_tools: list[str] = Field(min_length=1, max_length=8)
    worker_profile: Literal["disposable-linux-v1"] = "disposable-linux-v1"


class ToolInvocation(StrictModel):
    tool: str = Field(min_length=5, max_length=128)
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentRunRequest(StrictModel):
    plan: list[ToolInvocation] = Field(min_length=1, max_length=8)


class WorkerJobRequest(StrictModel):
    job: dict[str, Any]


class RelayRequest(StrictModel):
    event_id: str = Field(pattern=IDENTIFIER_PATTERN)
    channel: Literal["heartbeat", "status", "task", "result"]
    sequence: int = Field(ge=0, le=2_147_483_647)
    payload: dict[str, Any]


class DiagnosticResourceRequest(StrictModel):
    url: str = Field(min_length=12, max_length=2048)
    max_bytes: int = Field(ge=256, le=65_536)


class ExportRequest(StrictModel):
    export_id: str = Field(pattern=IDENTIFIER_PATTERN)
    media_type: Literal["application/json"] = "application/json"
    payload: dict[str, Any] | list[Any]


def validate_range_local_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must use HTTP or HTTPS")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("URL credentials and missing hosts are not allowed")
    if parsed.query or parsed.fragment:
        raise ValueError("URL query strings and fragments are not allowed")
    hostname = parsed.hostname.rstrip(".").lower()
    allowed = hostname == "localhost" or hostname.endswith(".keplerops.lab")
    try:
        allowed = allowed or ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        pass
    if not allowed:
        raise ValueError("URL must resolve through a range-local name or loopback")
    return value


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


@dataclass(frozen=True)
class AgentServices:
    store: StateStore
    runtime: LocalAgentRuntime
    workers: DockerWorkerController
    admin_token: str
    diagnostic_transport: httpx.AsyncBaseTransport | None

    def require_admin(
        self,
        supplied: Annotated[str | None, Header(alias=ADMIN_HEADER)] = None,
    ) -> None:
        if supplied is None or not secrets.compare_digest(supplied, self.admin_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized"
            )

    def require_agent(
        self,
        header_agent_id: Annotated[str | None, Header(alias=AGENT_ID_HEADER)] = None,
        token: Annotated[str | None, Header(alias=AGENT_TOKEN_HEADER)] = None,
    ) -> str:
        if (
            not header_agent_id
            or token is None
            or not self.store.authenticate(header_agent_id, token)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized"
            )
        return header_agent_id

    def ingest_relay(self, agent_id: str, request: RelayRequest) -> dict[str, Any]:
        payload_json = canonical_json(request.payload)
        if len(payload_json.encode("utf-8")) > MAX_RELAY_BYTES:
            raise HTTPException(
                status_code=413, detail="relay payload exceeds 65536 bytes"
            )
        received_at = utc_now()
        try:
            with self.store.transaction() as connection:
                connection.execute(
                    "INSERT INTO relay_events "
                    "(event_id, source_id, channel, sequence, payload_json, payload_digest, "
                    "received_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        request.event_id,
                        agent_id,
                        request.channel,
                        request.sequence,
                        payload_json,
                        digest_text(payload_json),
                        received_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail="relay event ID or source sequence already exists",
            ) from exc
        self.store.record_event(
            "relay.received",
            "agent",
            agent_id,
            {
                "relay_event_id": request.event_id,
                "channel": request.channel,
                "sequence": request.sequence,
                "payload_digest": digest_text(payload_json),
            },
            request.event_id,
        )
        return {
            "accepted": True,
            "event_id": request.event_id,
            "sequence": request.sequence,
            "received_at": received_at,
        }


def _register_status_routes(application: FastAPI, services: AgentServices) -> None:
    admin_authorization = Annotated[None, Depends(services.require_admin)]

    @application.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/readyz", responses={503: SERVICE_UNAVAILABLE_RESPONSE})
    def readiness() -> dict[str, Any]:
        if not services.store.ready():
            raise HTTPException(status_code=503, detail="state store is not ready")
        worker_capabilities = services.workers.capabilities()
        if not worker_capabilities["available"]:
            raise HTTPException(
                status_code=503, detail="worker controller is not ready"
            )
        return {
            "status": "ready",
            "schema_version": SCHEMA_VERSION,
            "event_schema_version": EVENT_SCHEMA_VERSION,
            "agent_runtime": services.runtime.runtime_kind,
            "langgraph_version": importlib.metadata.version("langgraph"),
            "worker_controller": "ready",
        }

    @application.post(
        "/v1/admin/reset",
        responses={401: UNAUTHORIZED_RESPONSE, 503: SERVICE_UNAVAILABLE_RESPONSE},
    )
    async def reset(_authorized: admin_authorization) -> dict[str, Any]:
        try:
            removed = await asyncio.to_thread(services.workers.cleanup)
        except WorkerError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        services.store.reset()
        return {
            "status": "reset",
            "seed_agent_id": SEED_AGENT_ID,
            "removed_workers": removed,
        }


def _register_identity_routes(application: FastAPI, services: AgentServices) -> None:
    agent_authorization = Annotated[str, Depends(services.require_agent)]

    @application.get(
        "/v1/identities/{agent_id}",
        responses={401: UNAUTHORIZED_RESPONSE, 404: NOT_FOUND_RESPONSE},
    )
    def identity(
        agent_id: str,
        authenticated: agent_authorization,
    ) -> dict[str, Any]:
        if authenticated != agent_id:
            raise HTTPException(status_code=404, detail=IDENTITY_NOT_FOUND)
        with services.store.read() as connection:
            row = connection.execute(
                "SELECT agent_id, identity_version, display_name, role, status, "
                "active_config_version, created_at FROM identities WHERE agent_id=?",
                (agent_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=IDENTITY_NOT_FOUND)
        return _row_dict(row)

    @application.get("/v1/tools", responses={401: UNAUTHORIZED_RESPONSE})
    def tool_registry(_agent_id: agent_authorization) -> dict[str, Any]:
        tools = []
        for row in services.store.tool_rows():
            tool = _row_dict(row)
            tool["input_schema"] = json.loads(tool.pop("input_schema_json"))
            tool["enabled"] = bool(tool["enabled"])
            tools.append(tool)
        return {"registry_version": "1", "tools": tools}


def _validate_allowed_tools(store: StateStore, allowed_tools: list[str]) -> None:
    registered = {f"{row['tool_name']}@{row['version']}" for row in store.tool_rows()}
    if len(set(allowed_tools)) != len(allowed_tools):
        raise HTTPException(status_code=422, detail="allowed tools must be unique")
    unknown = sorted(set(allowed_tools) - registered)
    if unknown:
        raise HTTPException(status_code=422, detail={"unknown_tools": unknown})


def _insert_configuration(
    store: StateStore, request: ConfigurationRequest, created_at: str
) -> None:
    try:
        with store.transaction() as connection:
            identity_exists = connection.execute(
                "SELECT 1 FROM identities WHERE agent_id=?", (request.agent_id,)
            ).fetchone()
            if identity_exists is None:
                raise HTTPException(status_code=404, detail=IDENTITY_NOT_FOUND)
            connection.execute(
                "INSERT INTO agent_configs "
                "(agent_id, version, runtime_kind, max_steps, tool_timeout_ms, "
                "allowed_tools_json, worker_profile, created_at) "
                "VALUES (?, ?, 'langgraph-local', ?, ?, ?, ?, ?)",
                (
                    request.agent_id,
                    request.version,
                    request.max_steps,
                    request.tool_timeout_ms,
                    canonical_json(request.allowed_tools),
                    request.worker_profile,
                    created_at,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="configuration already exists"
        ) from exc


def _register_configuration_routes(
    application: FastAPI, services: AgentServices
) -> None:
    admin_authorization = Annotated[None, Depends(services.require_admin)]
    agent_authorization = Annotated[str, Depends(services.require_agent)]

    @application.get(
        "/v1/configurations/active",
        responses={401: UNAUTHORIZED_RESPONSE, 404: NOT_FOUND_RESPONSE},
    )
    def active_configuration(agent_id: agent_authorization) -> dict[str, Any]:
        row = services.store.active_config(agent_id)
        if row is None:
            raise HTTPException(
                status_code=404, detail="active configuration not found"
            )
        result = _row_dict(row)
        result["allowed_tools"] = json.loads(result.pop("allowed_tools_json"))
        return result

    @application.post(
        "/v1/configurations",
        status_code=201,
        responses={
            401: UNAUTHORIZED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            409: CONFLICT_RESPONSE,
            422: UNPROCESSABLE_RESPONSE,
        },
    )
    def create_configuration(
        request: ConfigurationRequest,
        _authorized: admin_authorization,
    ) -> dict[str, Any]:
        _validate_allowed_tools(services.store, request.allowed_tools)
        created_at = utc_now()
        _insert_configuration(services.store, request, created_at)
        services.store.record_event(
            "agent.configuration.created",
            "agent",
            request.agent_id,
            {"version": request.version, "allowed_tools": request.allowed_tools},
            request.version,
        )
        return {
            **request.model_dump(),
            "runtime_kind": services.runtime.runtime_kind,
            "created_at": created_at,
        }

    @application.post(
        "/v1/configurations/{version}/activate",
        responses={401: UNAUTHORIZED_RESPONSE, 404: NOT_FOUND_RESPONSE},
    )
    def activate_configuration(
        version: str,
        agent_id: Annotated[str, Query(pattern=IDENTIFIER_PATTERN)],
        _authorized: admin_authorization,
    ) -> dict[str, str]:
        with services.store.transaction() as connection:
            config = connection.execute(
                "SELECT 1 FROM agent_configs WHERE agent_id=? AND version=?",
                (agent_id, version),
            ).fetchone()
            if config is None:
                raise HTTPException(status_code=404, detail="configuration not found")
            connection.execute(
                "UPDATE identities SET active_config_version=? WHERE agent_id=?",
                (version, agent_id),
            )
        services.store.record_event(
            "agent.configuration.activated",
            "agent",
            agent_id,
            {"version": version},
            version,
        )
        return {"agent_id": agent_id, "active_config_version": version}


def _record_rejected_run(
    store: StateStore, run_id: str, agent_id: str, error: ToolError
) -> None:
    ended_at = utc_now()
    with store.transaction() as connection:
        connection.execute(
            "UPDATE agent_runs SET status='rejected', error=?, ended_at=? WHERE run_id=?",
            (str(error), ended_at, run_id),
        )
    store.record_event(
        "agent.run.rejected",
        "agent",
        agent_id,
        {"error": str(error)},
        run_id,
    )


def _complete_run(
    store: StateStore,
    run_id: str,
    agent_id: str,
    result: dict[str, Any],
) -> tuple[str, str]:
    ended_at = utc_now()
    run_status = "failed" if result.get("error") else "completed"
    with store.transaction() as connection:
        connection.execute(
            "UPDATE agent_runs SET status=?, result_json=?, error=?, ended_at=? WHERE run_id=?",
            (
                run_status,
                canonical_json(result["outputs"]),
                result.get("error"),
                ended_at,
                run_id,
            ),
        )
    store.record_event(
        f"agent.run.{run_status}",
        "agent",
        agent_id,
        {"output_count": len(result["outputs"]), "error": result.get("error")},
        run_id,
    )
    return run_status, ended_at


def _register_agent_run_route(application: FastAPI, services: AgentServices) -> None:
    agent_authorization = Annotated[str, Depends(services.require_agent)]

    @application.post(
        "/v1/agent/runs",
        status_code=201,
        responses={
            401: UNAUTHORIZED_RESPONSE,
            409: CONFLICT_RESPONSE,
            422: UNPROCESSABLE_RESPONSE,
        },
    )
    async def run_agent(
        request: AgentRunRequest,
        agent_id: agent_authorization,
    ) -> dict[str, Any]:
        config = services.store.active_config(agent_id)
        if config is None:
            raise HTTPException(
                status_code=409, detail="active configuration is unavailable"
            )
        plan = [invocation.model_dump() for invocation in request.plan]
        run_id = f"run-{uuid.uuid4()}"
        started_at = utc_now()
        with services.store.transaction() as connection:
            connection.execute(
                "INSERT INTO agent_runs "
                "(run_id, agent_id, config_version, status, plan_json, started_at) "
                "VALUES (?, ?, ?, 'running', ?, ?)",
                (
                    run_id,
                    agent_id,
                    config["version"],
                    canonical_json(plan),
                    started_at,
                ),
            )
        services.store.record_event(
            "agent.run.started",
            "agent",
            agent_id,
            {"config_version": config["version"], "step_count": len(plan)},
            run_id,
        )
        try:
            result = await asyncio.to_thread(
                services.runtime.run,
                run_id=run_id,
                agent_id=agent_id,
                config_version=config["version"],
                plan=plan,
                allowed_tools=json.loads(config["allowed_tools_json"]),
                max_steps=config["max_steps"],
                timeout_ms=config["tool_timeout_ms"],
            )
        except ToolError as exc:
            _record_rejected_run(services.store, run_id, agent_id, exc)
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        run_status, ended_at = _complete_run(services.store, run_id, agent_id, result)
        return {
            "run_id": run_id,
            "agent_id": agent_id,
            "config_version": config["version"],
            "runtime_kind": services.runtime.runtime_kind,
            "status": run_status,
            "outputs": result["outputs"],
            "started_at": started_at,
            "ended_at": ended_at,
        }


def _register_relay_routes(application: FastAPI, services: AgentServices) -> None:
    agent_authorization = Annotated[str, Depends(services.require_agent)]

    @application.post(
        "/v1/relay/events",
        status_code=202,
        responses={
            401: UNAUTHORIZED_RESPONSE,
            409: CONFLICT_RESPONSE,
            413: PAYLOAD_TOO_LARGE_RESPONSE,
        },
    )
    def relay_event(
        request: RelayRequest,
        agent_id: agent_authorization,
    ) -> dict[str, Any]:
        return services.ingest_relay(agent_id, request)

    @application.websocket("/v1/relay/ws/{agent_id}")
    async def relay_websocket(websocket: WebSocket, agent_id: str) -> None:
        token = websocket.headers.get(AGENT_TOKEN_HEADER)
        if token is None or not services.store.authenticate(agent_id, token):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        try:
            while True:
                raw = await websocket.receive_json()
                try:
                    request = RelayRequest.model_validate(raw)
                    acknowledgement = services.ingest_relay(agent_id, request)
                    await websocket.send_json(acknowledgement)
                except ValidationError as exc:
                    await websocket.send_json(
                        {
                            "accepted": False,
                            "error": "invalid relay envelope",
                            "details": exc.errors(),
                        }
                    )
                except HTTPException as exc:
                    await websocket.send_json({"accepted": False, "error": exc.detail})
        except WebSocketDisconnect:
            return


async def _fetch_diagnostic(
    resource: sqlite3.Row,
    transport: httpx.AsyncBaseTransport | None,
) -> tuple[bytearray, int, str]:
    try:
        target = validate_range_local_url(resource["url"])
        timeout = httpx.Timeout(2.0, connect=1.0)
        async with httpx.AsyncClient(
            transport=transport,
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            async with client.stream(
                "GET",
                target,
                headers={
                    "Accept": "application/json, text/plain;q=0.8",
                    "User-Agent": "keplerops-platform-agent-diagnostics/1.0",
                },
            ) as response:
                if 300 <= response.status_code < 400:
                    raise HTTPException(
                        status_code=502, detail="diagnostic redirect refused"
                    )
                declared = response.headers.get("content-length")
                if declared and int(declared) > resource["max_bytes"]:
                    raise HTTPException(
                        status_code=502, detail="diagnostic response is too large"
                    )
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > resource["max_bytes"]:
                        raise HTTPException(
                            status_code=502,
                            detail="diagnostic response is too large",
                        )
                content_type = response.headers.get(
                    "content-type", "application/octet-stream"
                )
                return body, response.status_code, content_type
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=502, detail="diagnostic resource unavailable"
        ) from exc


def _register_diagnostic_routes(application: FastAPI, services: AgentServices) -> None:
    admin_authorization = Annotated[None, Depends(services.require_admin)]
    agent_authorization = Annotated[str, Depends(services.require_agent)]

    @application.put(
        "/v1/diagnostics/resources/{resource_id}",
        responses={401: UNAUTHORIZED_RESPONSE, 422: UNPROCESSABLE_RESPONSE},
    )
    def put_diagnostic_resource(
        resource_id: Annotated[str, Field(pattern=IDENTIFIER_PATTERN)],
        request: DiagnosticResourceRequest,
        _authorized: admin_authorization,
    ) -> dict[str, Any]:
        try:
            target = validate_range_local_url(request.url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        created_at = utc_now()
        with services.store.transaction() as connection:
            connection.execute(
                "INSERT INTO diagnostic_resources(resource_id, url, max_bytes, created_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(resource_id) DO UPDATE SET "
                "url=excluded.url, max_bytes=excluded.max_bytes, created_at=excluded.created_at",
                (resource_id, target, request.max_bytes, created_at),
            )
        services.store.record_event(
            "diagnostic.resource.configured",
            "service",
            "platform-agent",
            {"resource_id": resource_id, "url": target, "max_bytes": request.max_bytes},
            resource_id,
        )
        return {
            "resource_id": resource_id,
            "url": target,
            "max_bytes": request.max_bytes,
            "created_at": created_at,
        }

    @application.get(
        "/v1/diagnostics/{resource_id}",
        responses={
            401: UNAUTHORIZED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            502: BAD_GATEWAY_RESPONSE,
        },
    )
    async def diagnostic_proxy(
        resource_id: str,
        agent_id: agent_authorization,
    ) -> dict[str, Any]:
        with services.store.read() as connection:
            resource = connection.execute(
                "SELECT * FROM diagnostic_resources WHERE resource_id=?", (resource_id,)
            ).fetchone()
        if resource is None:
            raise HTTPException(status_code=404, detail="diagnostic resource not found")
        body, response_status, content_type = await _fetch_diagnostic(
            resource, services.diagnostic_transport
        )
        body_digest = f"sha256:{hashlib.sha256(body).hexdigest()}"
        services.store.record_event(
            "diagnostic.proxy.completed",
            "agent",
            agent_id,
            {
                "resource_id": resource_id,
                "status_code": response_status,
                "byte_count": len(body),
                "body_digest": body_digest,
            },
            resource_id,
        )
        return {
            "resource_id": resource_id,
            "status_code": response_status,
            "content_type": content_type,
            "byte_count": len(body),
            "body_digest": body_digest,
            "body_base64": base64.b64encode(body).decode("ascii"),
        }


def _register_export_route(application: FastAPI, services: AgentServices) -> None:
    agent_authorization = Annotated[str, Depends(services.require_agent)]

    @application.post(
        "/v1/exports",
        status_code=201,
        responses={
            401: UNAUTHORIZED_RESPONSE,
            409: CONFLICT_RESPONSE,
            413: PAYLOAD_TOO_LARGE_RESPONSE,
        },
    )
    def export_sink(
        request: ExportRequest,
        agent_id: agent_authorization,
    ) -> dict[str, Any]:
        payload_json = canonical_json(request.payload)
        encoded = payload_json.encode("utf-8")
        if len(encoded) > MAX_EXPORT_BYTES:
            raise HTTPException(status_code=413, detail="export exceeds 65536 bytes")
        export_path = services.store.export_root / f"{request.export_id}.json"
        try:
            with export_path.open("x", encoding="utf-8") as handle:
                handle.write(payload_json)
            export_path.chmod(0o600)
            received_at = utc_now()
            with services.store.transaction() as connection:
                connection.execute(
                    "INSERT INTO exports "
                    "(export_id, source_id, media_type, payload_path, byte_count, "
                    "payload_digest, received_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        request.export_id,
                        agent_id,
                        request.media_type,
                        export_path.name,
                        len(encoded),
                        digest_text(payload_json),
                        received_at,
                    ),
                )
        except (FileExistsError, sqlite3.IntegrityError) as exc:
            raise HTTPException(
                status_code=409, detail="export already exists"
            ) from exc
        except Exception:
            export_path.unlink(missing_ok=True)
            raise
        services.store.record_event(
            "export.received",
            "agent",
            agent_id,
            {
                "export_id": request.export_id,
                "byte_count": len(encoded),
                "payload_digest": digest_text(payload_json),
            },
            request.export_id,
        )
        return {
            "export_id": request.export_id,
            "source_id": agent_id,
            "media_type": request.media_type,
            "byte_count": len(encoded),
            "payload_digest": digest_text(payload_json),
            "received_at": received_at,
        }


async def _worker_operation(
    operation: Callable[[str], dict[str, Any]], worker_id: str
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(operation, worker_id)
    except WorkerOwnershipError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except WorkerUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WorkerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _register_worker_routes(application: FastAPI, services: AgentServices) -> None:
    admin_authorization = Annotated[None, Depends(services.require_admin)]

    @application.get("/v1/workers/capabilities", responses={401: UNAUTHORIZED_RESPONSE})
    async def worker_capabilities(
        _authorized: admin_authorization,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(services.workers.capabilities)

    @application.post(
        "/v1/workers",
        status_code=201,
        responses={
            401: UNAUTHORIZED_RESPONSE,
            422: UNPROCESSABLE_RESPONSE,
            503: SERVICE_UNAVAILABLE_RESPONSE,
        },
    )
    async def create_worker(
        request: WorkerJobRequest,
        _authorized: admin_authorization,
    ) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(services.workers.create, request.job)
        except WorkerUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except WorkerError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.get(
        "/v1/workers/{worker_id}",
        responses={
            401: UNAUTHORIZED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            409: CONFLICT_RESPONSE,
            503: SERVICE_UNAVAILABLE_RESPONSE,
        },
    )
    async def worker_status(
        worker_id: str,
        _authorized: admin_authorization,
    ) -> dict[str, Any]:
        return await _worker_operation(services.workers.status, worker_id)

    @application.post(
        "/v1/workers/{worker_id}/restart",
        responses={
            401: UNAUTHORIZED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            409: CONFLICT_RESPONSE,
            503: SERVICE_UNAVAILABLE_RESPONSE,
        },
    )
    async def restart_worker(
        worker_id: str,
        _authorized: admin_authorization,
    ) -> dict[str, Any]:
        return await _worker_operation(services.workers.restart, worker_id)

    @application.delete(
        "/v1/workers/{worker_id}",
        responses={
            401: UNAUTHORIZED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            409: CONFLICT_RESPONSE,
            503: SERVICE_UNAVAILABLE_RESPONSE,
        },
    )
    async def remove_worker(
        worker_id: str,
        _authorized: admin_authorization,
    ) -> dict[str, Any]:
        return await _worker_operation(services.workers.remove, worker_id)


def _register_event_route(application: FastAPI, services: AgentServices) -> None:
    admin_authorization = Annotated[None, Depends(services.require_admin)]

    @application.get("/v1/events", responses={401: UNAUTHORIZED_RESPONSE})
    def structured_events(
        _authorized: admin_authorization,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> dict[str, Any]:
        with services.store.read() as connection:
            rows = connection.execute(
                "SELECT * FROM structured_events ORDER BY occurred_at, event_id LIMIT ?",
                (limit,),
            ).fetchall()
        events = []
        for row in rows:
            event = _row_dict(row)
            event["payload"] = json.loads(event.pop("payload_json"))
            events.append(event)
        return {"schema_version": EVENT_SCHEMA_VERSION, "events": events}


def _build_services(
    root: Path,
    admin_token: str,
    agent_token: str,
    worker_client: Any | None,
    diagnostic_transport: httpx.AsyncBaseTransport | None,
) -> AgentServices:
    store = StateStore(root, agent_token)

    def on_runtime_event(event_type: str, payload: dict[str, Any]) -> None:
        correlation_id = str(payload.get("run_id", "")) or None
        store.record_event(
            event_type,
            "agent",
            SEED_AGENT_ID,
            payload,
            correlation_id,
        )

    runtime = LocalAgentRuntime(on_runtime_event)
    workers = DockerWorkerController(
        store,
        image_ref=os.environ.get("PLATFORM_AGENT_WORKER_IMAGE", DEFAULT_WORKER_IMAGE),
        base_url=os.environ.get(
            "PLATFORM_AGENT_DOCKER_SOCKET",
            "unix:///run/keplerops-worker/docker.sock",
        ),
        client=worker_client,
    )
    return AgentServices(
        store=store,
        runtime=runtime,
        workers=workers,
        admin_token=admin_token,
        diagnostic_transport=diagnostic_transport,
    )


def create_app(
    data_root: Path | None = None,
    diagnostic_transport: httpx.AsyncBaseTransport | None = None,
    worker_client: Any | None = None,
) -> FastAPI:
    root = data_root or Path(
        os.environ.get("PLATFORM_AGENT_DATA_ROOT", "/var/lib/keplerops-platform-agent")
    )
    services = _build_services(
        root,
        _configured_token(
            file_variable="PLATFORM_AGENT_ADMIN_TOKEN_FILE",
            value_variable="PLATFORM_AGENT_ADMIN_TOKEN",
            synthetic_default=DEFAULT_ADMIN_TOKEN,
        ),
        _configured_token(
            file_variable="PLATFORM_AGENT_SEED_TOKEN_FILE",
            value_variable="PLATFORM_AGENT_SEED_TOKEN",
            synthetic_default=DEFAULT_AGENT_TOKEN,
        ),
        worker_client,
        diagnostic_transport,
    )
    application = FastAPI(
        title="KeplerOps Platform Agent",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.store = services.store
    application.state.runtime = services.runtime
    application.state.workers = services.workers
    _register_status_routes(application, services)
    _register_identity_routes(application, services)
    _register_configuration_routes(application, services)
    _register_agent_run_route(application, services)
    _register_relay_routes(application, services)
    _register_diagnostic_routes(application, services)
    _register_export_route(application, services)
    _register_worker_routes(application, services)
    _register_event_route(application, services)
    return application


app = create_app()
