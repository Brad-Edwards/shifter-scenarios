from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .clients import NativeClients, NativeServiceError
from .config import settings
from .models import BusinessInput, DecisionEnvelope, Workflow, WorkflowResult
from .store import WorkflowStore
from .workflows import WorkflowExecutor


app = FastAPI(
    title="KeplerOps Orion Business Adapter",
    version="1.0.0",
    description="Internal bounded integration service for Orion business decisions.",
)
security = HTTPBearer(auto_error=False)
store = WorkflowStore(settings.audit_database)
executor = WorkflowExecutor(NativeClients(settings))


def require_adapter_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if not hmac.compare_digest(credentials.credentials, settings.adapter_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


def validate_release(envelope: DecisionEnvelope) -> None:
    for release in [
        envelope.release,
        *(stage.release for stage in envelope.inference.stages),
    ]:
        expected_release, expected_model, expected_image = settings.release_identity(
            release.model_family
        )
        actual = (
            envelope.range_id,
            release.release_id,
            release.model_digest,
            release.serving_image_digest,
            release.policy_digest,
        )
        expected = (
            settings.range_id,
            expected_release,
            expected_model,
            expected_image,
            settings.active_policy_digest,
        )
        if actual != expected:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="decision is not bound to the active signed release",
            )


def sign(envelope: DecisionEnvelope) -> str:
    return hmac.digest(
        settings.decision_signing_key.encode(), envelope.canonical_bytes(), "sha256"
    ).hex()


def validate_signature(envelope: DecisionEnvelope, signature: str | None) -> None:
    expected = hmac.digest(
        settings.decision_signing_key.encode(), envelope.canonical_bytes(), "sha256"
    ).hex()
    if signature is None or not hmac.compare_digest(signature, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="decision signature is invalid",
        )


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    try:
        executor.clients.opa_decide(
            {
                "schema": "keplerops.business-policy/v1",
                "range_id": "healthcheck",
                "workflow": "healthcheck",
                "actor": "healthcheck",
                "token_audience": "healthcheck",
                "action": "healthcheck",
                "outcome": "healthcheck",
                "target_system": "healthcheck",
                "target_object": "healthcheck",
                "release": {
                    "release_id": "sha256:" + "0" * 64,
                    "model_digest": "sha256:" + "0" * 64,
                    "serving_image_digest": "sha256:" + "0" * 64,
                    "policy_digest": "sha256:" + "0" * 64,
                    "model_family": "assistant",
                    "model_version": "healthcheck",
                    "signed": True,
                },
            }
        )
    except PermissionError:
        pass
    except NativeServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="business policy service is unavailable",
        ) from exc
    return {"status": "ready"}


@app.post(
    "/internal/v1/workflows/{workflow}/execute",
    response_model=WorkflowResult,
    dependencies=[Depends(require_adapter_token)],
)
def execute_workflow(
    workflow: Workflow,
    source: BusinessInput,
) -> WorkflowResult:
    existing = store.find(settings.range_id, source.idempotency_key)
    if existing is not None:
        if not store.source_matches(existing, source):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="idempotency key is already bound to another business input",
            )
        if existing["status"] == "succeeded":
            return store.result(existing, replay=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"idempotency key is already {existing['status']}",
        )
    try:
        envelope = executor.derive(workflow, source)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except (NativeServiceError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Orion inference is unavailable: {exc}",
        ) from exc
    signature = sign(envelope)
    validate_release(envelope)
    validate_signature(envelope, signature)
    try:
        workflow_id, existing = store.claim(envelope, signature)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if existing is not None:
        if existing["status"] == "succeeded":
            return store.result(existing, replay=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"idempotency key is already {existing['status']}",
        )
    try:
        policy, effect = executor.execute(envelope)
        return store.complete(workflow_id, policy, effect)
    except PermissionError as exc:
        store.fail(workflow_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except (NativeServiceError, OSError, ValueError) as exc:
        store.fail(workflow_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"native workflow failed: {exc}",
        ) from exc


@app.get(
    "/internal/v1/workflows/{workflow_id}",
    response_model=WorkflowResult,
    dependencies=[Depends(require_adapter_token)],
)
def get_workflow(workflow_id: str) -> WorkflowResult:
    try:
        return store.result(store.get(workflow_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workflow not found") from exc


@app.post(
    "/internal/v1/workflows/{workflow_id}/compensate",
    response_model=WorkflowResult,
    dependencies=[Depends(require_adapter_token)],
)
def compensate_workflow(workflow_id: str) -> WorkflowResult:
    try:
        data = store.compensation_data(workflow_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workflow not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if data["state"] == "completed":
        return store.result(store.get(workflow_id), replay=True)
    workflow = Workflow(data["workflow"])
    try:
        before, after, native_ids = executor.compensate(workflow, data)
    except (NativeServiceError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"native compensation failed: {exc}",
        ) from exc
    store.record_compensation(workflow_id, before, after, native_ids)
    return store.result(store.get(workflow_id))
