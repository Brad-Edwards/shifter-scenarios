"""Guarded context, WorkHub, and identity lifecycle API."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from security import BearerAuthorizer
from store import StateStore
from upstreams import KeycloakClient, WorkHubClient


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = Path(
    os.environ.get("PLATFORM_CONTEXT_CONFIG", ROOT / "config/context-v1.json")
)
STATE_ROOT = Path(
    os.environ.get("PLATFORM_CONTEXT_STATE_ROOT", "/var/lib/keplerops-platform-context")
)
TOKEN_PATH = Path(
    os.environ.get(
        "PLATFORM_CONTEXT_TOKEN_FILE", "/run/keplerops/platform-context-token"
    )
)
RequestId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")]
SafePath = Annotated[
    str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,511}$", max_length=512)
]


def normalized_repository_path(value: str) -> str:
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("repository path must be normalized and relative")
    return value


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise RuntimeError("unsupported platform context configuration")
    return config


class FileImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: RequestId
    root_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")]
    relative_path: SafePath
    destination: Literal["record", "workhub"] = "record"
    destination_path: SafePath | None = None

    @field_validator("destination_path")
    @classmethod
    def no_parent_segments(cls, value: str | None) -> str | None:
        return None if value is None else normalized_repository_path(value)


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: RequestId
    subject: Annotated[str, Field(min_length=3, max_length=160)]
    content: Annotated[str, Field(min_length=1, max_length=65_536)]


class ConversationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: RequestId
    issue_id: Annotated[int, Field(gt=0)]
    content: Annotated[str, Field(min_length=1, max_length=65_536)]


class ArtifactWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: RequestId
    path: SafePath
    content_base64: Annotated[str, Field(min_length=1, max_length=1_500_000)]
    message: Annotated[str, Field(min_length=3, max_length=200)]

    @field_validator("path")
    @classmethod
    def normalized_path(cls, value: str) -> str:
        return normalized_repository_path(value)


class ArtifactDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: RequestId
    path: SafePath
    message: Annotated[str, Field(min_length=3, max_length=200)]

    @field_validator("path")
    @classmethod
    def normalized_path(cls, value: str) -> str:
        return normalized_repository_path(value)


class PasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: RequestId
    username: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")]
    password: Annotated[str, Field(min_length=12, max_length=256)]
    temporary: bool = False


class IdentitySubject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: RequestId
    username: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")]


class ClientSecretRotation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: RequestId
    client_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")]


class Services:
    def __init__(self, state_root: Path, config: dict[str, Any]) -> None:
        self.store = StateStore(state_root)
        self.config = config
        ca_file = os.environ.get("PLATFORM_CONTEXT_CA_FILE")
        workhub = config["workhub"]
        self.workhub = WorkHubClient(
            gitea_url=os.environ.get(
                "PLATFORM_CONTEXT_GITEA_URL",
                "https://repo-ticket-01.keplerops.lab/git/api/v1",
            ),
            redmine_url=os.environ.get(
                "PLATFORM_CONTEXT_REDMINE_URL",
                "https://repo-ticket-01.keplerops.lab/tickets",
            ),
            gitea_token_path=Path(
                os.environ.get(
                    "PLATFORM_CONTEXT_GITEA_TOKEN_FILE",
                    "/run/keplerops/workhub-gitea-token",
                )
            ),
            redmine_key_path=Path(
                os.environ.get(
                    "PLATFORM_CONTEXT_REDMINE_KEY_FILE",
                    "/run/keplerops/workhub-redmine-key",
                )
            ),
            ca_file=ca_file,
            owner=workhub["owner"],
            repository=workhub["repository"],
            branch=workhub["branch"],
            project=workhub["redmine_project"],
        )
        identity = config["keycloak"]
        self.keycloak = KeycloakClient(
            base_url=os.environ.get(
                "PLATFORM_CONTEXT_KEYCLOAK_URL", "https://idp-01.keplerops.lab"
            ),
            admin_realm=identity["admin_realm"],
            target_realm=identity["target_realm"],
            client_id=os.environ.get(
                "PLATFORM_CONTEXT_KEYCLOAK_CLIENT_ID", "platform-context-admin"
            ),
            client_secret_path=Path(
                os.environ.get(
                    "PLATFORM_CONTEXT_KEYCLOAK_SECRET_FILE",
                    "/run/keplerops/keycloak-admin-client-secret",
                )
            ),
            ca_file=ca_file,
        )


AUTH_RESPONSE = {401: {"description": "Context bearer authentication failed"}}
READY_RESPONSES = {503: {"description": "The context platform is not ready"}}
FILE_CREATE_RESPONSES = {
    **AUTH_RESPONSE,
    403: {"description": "The configured file root does not allow this import"},
    409: {"description": "The import conflicts with durable state"},
    422: {"description": "The import destination is incomplete"},
}
FILE_STATUS_RESPONSES = {
    **AUTH_RESPONSE,
    404: {"description": "The file import does not exist"},
}
WORKHUB_RESPONSES = {
    **AUTH_RESPONSE,
    422: {"description": "Artifact content is invalid"},
    502: {"description": "The WorkHub upstream operation failed"},
}
IDENTITY_RESPONSES = {
    **AUTH_RESPONSE,
    403: {"description": "The identity is outside configured scope"},
    502: {"description": "The identity upstream operation failed"},
}


class ContextController:
    def __init__(
        self, services: Services, config: dict[str, Any], authorizer: BearerAuthorizer
    ) -> None:
        self.services = services
        self.config = config
        self.authorizer = authorizer

    def require_authorization(
        self, authorization: Annotated[str | None, Header()] = None
    ) -> None:
        if not self.authorizer.authorized(authorization):
            raise HTTPException(
                status_code=401, detail="explicit context authorization required"
            )

    def record(
        self,
        *,
        event_name: str,
        operation: str,
        request_id: str,
        request: dict[str, Any],
        response: dict[str, Any],
        started: float,
    ) -> None:
        self.services.store.record_event(
            event_name=event_name,
            operation=operation,
            status="succeeded",
            request_id=request_id,
            request=request,
            response=response,
            source="keplerops-platform-context-api",
            duration_ms=(time.perf_counter() - started) * 1_000,
        )

    def allowed_user(self, username: str) -> None:
        if username not in self.config["keycloak"]["allowed_users"]:
            raise HTTPException(
                status_code=403, detail="identity is outside configured scope"
            )

    def allowed_client(self, client_id: str) -> None:
        if client_id not in self.config["keycloak"]["allowed_clients"]:
            raise HTTPException(
                status_code=403, detail="client is outside configured scope"
            )


def _register_status_routes(
    app: FastAPI,
    controller: ContextController,
    token_path: Path,
) -> None:
    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", responses=READY_RESPONSES)
    def readiness() -> dict[str, Any]:
        if not controller.services.store.ready() or not token_path.is_file():
            raise HTTPException(status_code=503, detail="context platform is not ready")
        return {
            "status": "ready",
            "config_id": controller.config["config_id"],
            "schema_version": controller.config["schema_version"],
        }


def _register_file_routes(app: FastAPI, controller: ContextController) -> None:
    authorization = [Depends(controller.require_authorization)]

    @app.post(
        "/v1/files/imports",
        dependencies=authorization,
        responses=FILE_CREATE_RESPONSES,
    )
    def enqueue_import(value: FileImportRequest) -> dict[str, Any]:
        if value.root_id not in controller.config["file_roots"]:
            raise HTTPException(status_code=403, detail="root_id is not allowlisted")
        if value.destination == "workhub" and value.destination_path is None:
            raise HTTPException(
                status_code=422, detail="workhub imports require destination_path"
            )
        try:
            job = controller.services.store.enqueue_file_job(
                value.model_dump(mode="json")
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"job_id": job["job_id"], "state": job["state"]}

    @app.get(
        "/v1/files/imports/{job_id}",
        dependencies=authorization,
        responses=FILE_STATUS_RESPONSES,
    )
    def import_status(job_id: str) -> dict[str, Any]:
        job = controller.services.store.file_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="file import job not found")
        return job


def _register_workhub_conversation_routes(
    app: FastAPI, controller: ContextController
) -> None:
    authorization = [Depends(controller.require_authorization)]

    @app.post(
        "/v1/workhub/conversations",
        dependencies=authorization,
        responses=WORKHUB_RESPONSES,
    )
    def create_conversation(value: ConversationCreate) -> dict[str, Any]:
        prior = controller.services.store.idempotent_record(
            "workhub_records", value.request_id
        )
        if prior is not None:
            return prior
        started = time.perf_counter()
        request = value.model_dump(mode="json")
        try:
            response = controller.services.workhub.create_conversation(
                value.subject, value.content
            )
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=502, detail=error.__class__.__name__
            ) from error
        upstream_id = (
            str(response.get("body", {}).get("issue", {}).get("id", "")) or None
        )
        controller.services.store.save_workhub(
            value.request_id, "conversation-create", upstream_id, request, response
        )
        controller.record(
            event_name="platform_context.workhub_conversation_created",
            operation="workhub.conversation.create",
            request_id=value.request_id,
            request=request,
            response=response,
            started=started,
        )
        return response

    @app.put(
        "/v1/workhub/conversations",
        dependencies=authorization,
        responses=WORKHUB_RESPONSES,
    )
    def update_conversation(value: ConversationUpdate) -> dict[str, Any]:
        prior = controller.services.store.idempotent_record(
            "workhub_records", value.request_id
        )
        if prior is not None:
            return prior
        started = time.perf_counter()
        request = value.model_dump(mode="json")
        try:
            response = controller.services.workhub.update_conversation(
                value.issue_id, value.content
            )
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=502, detail=error.__class__.__name__
            ) from error
        controller.services.store.save_workhub(
            value.request_id,
            "conversation-update",
            str(value.issue_id),
            request,
            response,
        )
        controller.record(
            event_name="platform_context.workhub_conversation_updated",
            operation="workhub.conversation.update",
            request_id=value.request_id,
            request=request,
            response=response,
            started=started,
        )
        return response


def _register_workhub_artifact_routes(
    app: FastAPI, controller: ContextController
) -> None:
    import base64

    authorization = [Depends(controller.require_authorization)]

    @app.put(
        "/v1/workhub/artifacts",
        dependencies=authorization,
        responses=WORKHUB_RESPONSES,
    )
    def put_artifact(value: ArtifactWrite) -> dict[str, Any]:
        prior = controller.services.store.idempotent_record(
            "workhub_records", value.request_id
        )
        if prior is not None:
            return prior
        started = time.perf_counter()
        request = value.model_dump(mode="json")
        try:
            content = base64.b64decode(value.content_base64, validate=True)
            response = controller.services.workhub.put_artifact(
                value.path, content, value.message
            )
        except ValueError as error:
            raise HTTPException(
                status_code=422, detail="artifact content is not valid base64"
            ) from error
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=502, detail=error.__class__.__name__
            ) from error
        upstream_id = (
            str(response.get("body", {}).get("content", {}).get("sha", "")) or None
        )
        controller.services.store.save_workhub(
            value.request_id, "artifact-put", upstream_id, request, response
        )
        controller.record(
            event_name="platform_context.workhub_artifact_written",
            operation="workhub.artifact.put",
            request_id=value.request_id,
            request=request,
            response=response,
            started=started,
        )
        return response

    @app.delete(
        "/v1/workhub/artifacts",
        dependencies=authorization,
        responses=WORKHUB_RESPONSES,
    )
    def delete_artifact(value: ArtifactDelete) -> dict[str, Any]:
        prior = controller.services.store.idempotent_record(
            "workhub_records", value.request_id
        )
        if prior is not None:
            return prior
        started = time.perf_counter()
        request = value.model_dump(mode="json")
        try:
            response = controller.services.workhub.delete_artifact(
                value.path, value.message
            )
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=502, detail=error.__class__.__name__
            ) from error
        controller.services.store.save_workhub(
            value.request_id, "artifact-delete", value.path, request, response
        )
        controller.record(
            event_name="platform_context.workhub_artifact_deleted",
            operation="workhub.artifact.delete",
            request_id=value.request_id,
            request=request,
            response=response,
            started=started,
        )
        return response


def _register_identity_credential_routes(
    app: FastAPI, controller: ContextController
) -> None:
    authorization = [Depends(controller.require_authorization)]

    @app.put(
        "/v1/keycloak/password",
        dependencies=authorization,
        responses=IDENTITY_RESPONSES,
    )
    def reset_password(value: PasswordReset) -> dict[str, Any]:
        controller.allowed_user(value.username)
        prior = controller.services.store.idempotent_record(
            "identity_records", value.request_id
        )
        if prior is not None:
            return prior
        started = time.perf_counter()
        request = {
            "request_id": value.request_id,
            "username": value.username,
            "temporary": value.temporary,
            "credential_digest": "sha256:"
            + hashlib.sha256(value.password.encode("utf-8")).hexdigest(),
        }
        try:
            response = controller.services.keycloak.reset_password(
                value.username, value.password, value.temporary
            )
        except (httpx.HTTPError, LookupError) as error:
            raise HTTPException(
                status_code=502, detail=error.__class__.__name__
            ) from error
        controller.services.store.save_identity(
            value.request_id, "password-reset", value.username, request, response
        )
        controller.record(
            event_name="platform_context.keycloak_password_reset",
            operation="keycloak.password.reset",
            request_id=value.request_id,
            request=request,
            response=response,
            started=started,
        )
        return response

    @app.post(
        "/v1/keycloak/logout",
        dependencies=authorization,
        responses=IDENTITY_RESPONSES,
    )
    def logout(value: IdentitySubject) -> dict[str, Any]:
        controller.allowed_user(value.username)
        prior = controller.services.store.idempotent_record(
            "identity_records", value.request_id
        )
        if prior is not None:
            return prior
        started = time.perf_counter()
        request = value.model_dump(mode="json")
        try:
            response = controller.services.keycloak.logout(value.username)
        except (httpx.HTTPError, LookupError) as error:
            raise HTTPException(
                status_code=502, detail=error.__class__.__name__
            ) from error
        controller.services.store.save_identity(
            value.request_id, "session-logout", value.username, request, response
        )
        controller.record(
            event_name="platform_context.keycloak_sessions_logged_out",
            operation="keycloak.sessions.logout",
            request_id=value.request_id,
            request=request,
            response=response,
            started=started,
        )
        return response


def _register_identity_session_routes(
    app: FastAPI, controller: ContextController
) -> None:
    authorization = [Depends(controller.require_authorization)]

    @app.post(
        "/v1/keycloak/sessions",
        dependencies=authorization,
        responses=IDENTITY_RESPONSES,
    )
    def sessions(value: IdentitySubject) -> dict[str, Any]:
        controller.allowed_user(value.username)
        started = time.perf_counter()
        request = value.model_dump(mode="json")
        try:
            response = controller.services.keycloak.sessions(value.username)
        except (httpx.HTTPError, LookupError) as error:
            raise HTTPException(
                status_code=502, detail=error.__class__.__name__
            ) from error
        controller.record(
            event_name="platform_context.keycloak_sessions_listed",
            operation="keycloak.sessions.list",
            request_id=value.request_id,
            request=request,
            response=response,
            started=started,
        )
        return response

    @app.post(
        "/v1/keycloak/client-secret",
        dependencies=authorization,
        responses=IDENTITY_RESPONSES,
    )
    def rotate_client_secret(value: ClientSecretRotation) -> dict[str, Any]:
        controller.allowed_client(value.client_id)
        prior = controller.services.store.idempotent_record(
            "identity_records", value.request_id
        )
        if prior is not None:
            return prior
        started = time.perf_counter()
        request = value.model_dump(mode="json")
        try:
            response = controller.services.keycloak.rotate_client_secret(
                value.client_id
            )
        except (httpx.HTTPError, LookupError) as error:
            raise HTTPException(
                status_code=502, detail=error.__class__.__name__
            ) from error
        durable_response = {
            key: item for key, item in response.items() if key != "client_secret"
        }
        controller.services.store.save_identity(
            value.request_id,
            "client-secret-rotation",
            value.client_id,
            request,
            durable_response,
        )
        controller.record(
            event_name="platform_context.keycloak_client_secret_rotated",
            operation="keycloak.client-secret.rotate",
            request_id=value.request_id,
            request=request,
            response=durable_response,
            started=started,
        )
        return response


def _register_admin_routes(app: FastAPI, controller: ContextController) -> None:
    authorization = [Depends(controller.require_authorization)]

    @app.get("/v1/admin/events", dependencies=authorization, responses=AUTH_RESPONSE)
    def events(limit: Annotated[int, Query(ge=1, le=1_000)] = 100) -> dict[str, Any]:
        records = controller.services.store.recent_events(limit)
        return {"record_count": len(records), "records": records}

    @app.post("/v1/admin/reset", dependencies=authorization, responses=AUTH_RESPONSE)
    def reset() -> dict[str, Any]:
        controller.services.store.reset()
        return {
            "status": "reset",
            "config_id": controller.config["config_id"],
            "cursor": controller.services.store.cursor("postgres-context-v1"),
            "event_count": len(controller.services.store.recent_events(1)),
        }


def create_app(
    state_root: Path = STATE_ROOT,
    config_path: Path = CONFIG_PATH,
    token_path: Path = TOKEN_PATH,
) -> FastAPI:
    config = load_config(config_path)
    services = Services(state_root, config)
    controller = ContextController(services, config, BearerAuthorizer(token_path))
    app = FastAPI(title="KeplerOps Platform Context", version="1.0.0")
    app.state.platform_context = services
    _register_status_routes(app, controller, token_path)
    _register_file_routes(app, controller)
    _register_workhub_conversation_routes(app, controller)
    _register_workhub_artifact_routes(app, controller)
    _register_identity_credential_routes(app, controller)
    _register_identity_session_routes(app, controller)
    _register_admin_routes(app, controller)
    return app


app = create_app()
