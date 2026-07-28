"""Authenticated platform deployment, registry resolution, and workspace API."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from cloud_boundary import WorkspaceBroker
from policy import load_policy
from registry import OciRegistry, ReputationResolver
from security import BearerAuthorizer
from store import ConflictError, StateStore


STATE_ROOT = Path(
    os.environ.get(
        "PLATFORM_DEPLOYMENT_STATE_ROOT", "/var/lib/keplerops-platform-deployment"
    )
)
POLICY_PATH = Path(
    os.environ.get(
        "PLATFORM_DEPLOYMENT_POLICY", "/run/keplerops/deployment-policy.json"
    )
)
TOKEN_PATH = Path(
    os.environ.get(
        "PLATFORM_DEPLOYMENT_TOKEN_FILE", "/run/keplerops/platform-deployment-token"
    )
)
REGISTRY_TOKEN_PATH = Path(
    os.environ.get(
        "PLATFORM_DEPLOYMENT_REGISTRY_TOKEN_FILE", "/run/keplerops/gitea-registry-token"
    )
)
SIGNING_KEY_PATH = Path(
    os.environ.get(
        "PLATFORM_DEPLOYMENT_SIGNING_KEY_FILE", "/run/keplerops/reputation-signing-key"
    )
)
CA_PATH = Path(os.environ.get("PLATFORM_DEPLOYMENT_CA_FILE", "/run/tls/ca.crt"))
Authorization = Annotated[str | None, Header()]
EventLimit = Annotated[int, Query(ge=1, le=1000)]
AUTH_RESPONSE = {401: {"description": "Bearer authentication failed"}}
API_ERROR_RESPONSES = {
    401: {"description": "Bearer authentication failed"},
    404: {"description": "Requested resource was not found"},
    409: {"description": "Request conflicts with durable state"},
    422: {"description": "Request is outside the deployment policy"},
    502: {"description": "The bounded upstream operation failed"},
}

policy = load_policy(POLICY_PATH)
store = StateStore(STATE_ROOT, policy.tenant_id)
authorizer = BearerAuthorizer(TOKEN_PATH)
oci = OciRegistry(policy, REGISTRY_TOKEN_PATH, CA_PATH, store)
resolver = ReputationResolver(policy, oci, SIGNING_KEY_PATH, store)
broker = WorkspaceBroker(policy, store)
app = FastAPI(title="KeplerOps Platform Deployment", version="1.0.0")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReputationRequest(StrictModel):
    request_id: str
    repository: str
    digest: str
    score: int = Field(ge=-100, le=100)
    producer: str
    rationale: str


class ResolutionRequest(StrictModel):
    request_id: str
    repository: str


class WorkspaceRequest(StrictModel):
    request_id: str
    image: str
    command_profile: str
    resource_profile: str
    ttl_seconds: int


def require_authorization(authorization: str | None) -> None:
    if not authorizer.authorized(authorization):
        raise HTTPException(
            status_code=401,
            detail="valid platform-deployment bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )


def execute(
    operation: str, request_id: str | None, request: dict[str, Any], action: Any
) -> Any:
    started = time.monotonic()
    try:
        response = action()
        store.record_event(
            f"platform_deployment.api.{operation}",
            operation,
            "succeeded",
            request_id,
            request,
            response,
            (time.monotonic() - started) * 1000,
        )
        return response
    except (ValueError, ConflictError) as exc:
        response = {"error_type": type(exc).__name__, "error": str(exc)}
        store.record_event(
            f"platform_deployment.api.{operation}",
            operation,
            "rejected",
            request_id,
            request,
            response,
            (time.monotonic() - started) * 1000,
        )
        raise HTTPException(
            status_code=409 if isinstance(exc, ConflictError) else 422, detail=str(exc)
        ) from exc
    except KeyError as exc:
        response = {"error_type": type(exc).__name__, "error": str(exc)}
        store.record_event(
            f"platform_deployment.api.{operation}",
            operation,
            "not_found",
            request_id,
            request,
            response,
            (time.monotonic() - started) * 1000,
        )
        raise HTTPException(status_code=404, detail="resource not found") from exc
    except Exception as exc:
        response = {"error_type": type(exc).__name__, "error": str(exc)}
        store.record_event(
            f"platform_deployment.api.{operation}",
            operation,
            "failed",
            request_id,
            request,
            response,
            (time.monotonic() - started) * 1000,
        )
        raise HTTPException(
            status_code=502, detail="upstream operation failed"
        ) from exc


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def ready() -> dict[str, Any]:
    return {
        "status": "ready",
        "policy_schema": 1,
        "tenant_id": policy.tenant_id,
        "project_id": policy.project_id,
        "region": policy.region,
    }


@app.post("/v1/registry/reputation-events", responses=API_ERROR_RESPONSES)
def reputation_event(
    request: ReputationRequest, authorization: Authorization = None
) -> dict[str, Any]:
    require_authorization(authorization)
    content = request.model_dump()
    return execute(
        "reputation", request.request_id, content, lambda: resolver.record(content)
    )


@app.post("/v1/registry/resolutions", responses=API_ERROR_RESPONSES)
def resolution(
    request: ResolutionRequest, authorization: Authorization = None
) -> dict[str, Any]:
    require_authorization(authorization)
    content = request.model_dump()
    return execute(
        "resolution", request.request_id, content, lambda: resolver.resolve(content)
    )


@app.post("/v1/workspaces", responses=API_ERROR_RESPONSES)
def create_workspace(
    request: WorkspaceRequest, authorization: Authorization = None
) -> dict[str, Any]:
    require_authorization(authorization)
    content = request.model_dump()
    return execute(
        "workspace_create", request.request_id, content, lambda: broker.create(content)
    )


@app.get("/v1/workspaces/{workspace_id}", responses=API_ERROR_RESPONSES)
def workspace_status(
    workspace_id: str, authorization: Authorization = None
) -> dict[str, Any]:
    require_authorization(authorization)
    return execute(
        "workspace_status",
        None,
        {"workspace_id": workspace_id},
        lambda: broker.status(workspace_id),
    )


@app.delete("/v1/workspaces/{workspace_id}", responses=API_ERROR_RESPONSES)
def delete_workspace(
    workspace_id: str, authorization: Authorization = None
) -> dict[str, Any]:
    require_authorization(authorization)

    def action() -> dict[str, Any]:
        record = broker.status(workspace_id)
        return broker.delete(record, "authenticated-request")

    return execute("workspace_delete", None, {"workspace_id": workspace_id}, action)


@app.get("/v1/admin/events", responses=AUTH_RESPONSE)
def events(
    limit: EventLimit = 100, authorization: Authorization = None
) -> list[dict[str, Any]]:
    require_authorization(authorization)
    return store.recent_events(limit)


@app.post("/v1/admin/reconcile", responses=API_ERROR_RESPONSES)
def reconcile(authorization: Authorization = None) -> list[dict[str, Any]]:
    require_authorization(authorization)
    return execute("reconcile", None, {}, broker.reconcile)


@app.post("/v1/admin/reset", responses=API_ERROR_RESPONSES)
def reset(authorization: Authorization = None) -> dict[str, Any]:
    require_authorization(authorization)
    # Reset deletes only exact job names already tracked in durable local state.
    return execute("reset", None, {}, broker.reset)
