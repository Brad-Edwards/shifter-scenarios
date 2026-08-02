from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .clients import NativeClients, NativeServiceError
from .config import settings
from .models import BusinessInput, DecisionEnvelope, Workflow, WorkflowAuditRecord, WorkflowResult
from .native_sources import NativeSourceLocator, NativeSourceResolver
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
native_sources = NativeSourceResolver(executor.clients)


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


def _execute_workflow(
    workflow: Workflow,
    source: BusinessInput,
    *,
    native_ingest: bool,
) -> WorkflowResult:
    reserved = {"campaign_operation", "control_kind", "native_source_system",
                "native_record_id", "native_observation", "operation_attempt",
                "operation_subject"}
    if not native_ingest and reserved.intersection(source.facts):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="native source identity is resolved only by the public enterprise intake",
        )
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


@app.post(
    "/internal/v1/workflows/{workflow}/execute",
    response_model=WorkflowResult,
    dependencies=[Depends(require_adapter_token)],
)
def execute_workflow(
    workflow: Workflow,
    source: BusinessInput,
) -> WorkflowResult:
    return _execute_workflow(workflow, source, native_ingest=False)


@app.post("/v1/native-sources/{workflow}/consume", response_model=WorkflowResult)
def consume_native_source(workflow: Workflow, locator: NativeSourceLocator) -> WorkflowResult:
    """Consume a native enterprise record; caller-supplied qualification facts are rejected."""
    try:
        source = native_sources.resolve(workflow, locator)
        return _execute_workflow(workflow, source, native_ingest=True)
    except (NativeServiceError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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


@app.get(
    "/internal/v1/workflows/{workflow_id}/audit",
    response_model=WorkflowAuditRecord,
    dependencies=[Depends(require_adapter_token)],
)
def get_workflow_audit(workflow_id: str) -> WorkflowAuditRecord:
    try:
        row = store.get(workflow_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workflow not found") from exc
    unsigned = store.audit(row, "0" * 64).model_dump(by_alias=True)
    unsigned.pop("audit_signature", None)
    signature = hmac.digest(
        settings.audit_signing_key.encode(),
        __import__("json").dumps(unsigned, sort_keys=True, separators=(",", ":")).encode(),
        "sha256",
    ).hex()
    return store.audit(row, signature)


@app.get(
    "/internal/v1/m10/impacts/{operation}",
    dependencies=[Depends(require_adapter_token)],
)
def get_m10_impact(operation: str) -> dict[str, str]:
    workflows = {
        "kep-m10-e": Workflow.FEATURE_CONTROL,
        "kep-m10-l": Workflow.ACCOUNTING_CREDIT,
        "kep-m10-m": Workflow.INCIDENT_PUBLICATION,
        "kep-m10-n": Workflow.ADVISORY_CAMPAIGN,
        "kep-m10-o": Workflow.SUPPORT_TRIAGE,
        "kep-m10-q": Workflow.TENANT_RETENTION,
    }
    if operation not in workflows:
        raise HTTPException(status_code=404, detail="unknown business impact operation")
    try:
        rows = store.impact_workflows(operation, workflows[operation].value)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail="native attack/clean/near set is incomplete") from exc
    return {
        "attack_workflow_id": rows["attack"],
        "clean_workflow_id": rows["clean"],
        "near_workflow_id": rows["near"],
    }


@app.post(
    "/internal/v1/workflows/{workflow_id}/compensate-partner-effects",
    dependencies=[Depends(require_adapter_token)],
)
def compensate_partner_effects(workflow_id: str) -> dict[str, object]:
    try:
        row = store.get(workflow_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workflow not found") from exc
    if str(row["workflow"]) != Workflow.INCIDENT_PUBLICATION.value:
        raise HTTPException(status_code=409, detail="workflow has no partner-monitor effects")
    from .impact_workers import compensate

    return {"workflow_id": workflow_id, "restored_ticket_ids": compensate(str(row["target_object_id"]))}
