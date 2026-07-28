from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.clients import _backend_http_client
from keplerops_runtime.foundation.config import ACTION_DENIED, CONFIG, ERROR_RESPONSES, MODEL_REGISTRY_UNAVAILABLE, PUBLIC_WORKHUB_UNAVAILABLE, SHA256_PREFIX, TLS_CA_PATH, WORKFLOW_COMPLETED_EVENT
from keplerops_runtime.foundation.policy_client import _evasion_policy
from keplerops_runtime.foundation.telemetry import _observe
from keplerops_runtime.modules.m02.schemas import ModelDependencyRequest
from keplerops_runtime.modules.m02.store import _ensure_model_supply_schema
from keplerops_runtime.modules.m09.candidates import _download_backdoor_artifact, _mlflow_client
from pathlib import Path
from typing import Annotated
from typing import Any
from workhub_credentials import workhub_credentials
import asyncio
import hashlib
import hmac
import httpx
import secrets
import tempfile
import time

router = APIRouter()


def _model_dependency_urls() -> tuple[str, str]:
    base = CONFIG.get("workhub_url")
    if not isinstance(base, str):
        raise HTTPException(status_code=503, detail=PUBLIC_WORKHUB_UNAVAILABLE)
    prefix = (
        f"{base.rstrip('/')}/git/api/packages/ml.engineer/generic/"
        "keplerops-policy-model"
    )
    return (
        f"{prefix}/1.0.0/policy-model.json",
        f"{prefix}/2.0.0/policy-model.json",
    )

def _model_dependency_source_index(source_url: str) -> int:
    for index, canonical_url in enumerate(_model_dependency_urls()):
        if hmac.compare_digest(source_url, canonical_url):
            return index
    raise HTTPException(status_code=422, detail="model dependency source rejected")

async def _fetch_model_dependency_artifact(source_index: int) -> bytes:
    source_urls = _model_dependency_urls()
    if not 0 <= source_index < len(source_urls):
        raise HTTPException(status_code=422, detail="model dependency source rejected")
    source_url = source_urls[source_index]
    client = _backend_http_client(
        "model-dependency-source", timeout=10.0, verify=TLS_CA_PATH
    )
    try:
        response = await client.get(
            source_url,
            auth=workhub_credentials(),
            headers={"Host": "workhub.keplerops.lab"},
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail=PUBLIC_WORKHUB_UNAVAILABLE) from None
    if response.status_code != 200 or not 64 <= len(response.content) <= 2_000_000:
        raise HTTPException(status_code=503, detail=PUBLIC_WORKHUB_UNAVAILABLE)
    return response.content

def _register_dependency_version(
    client: Any,
    *,
    experiment_id: str,
    model_name: str,
    raw: bytes,
    label: str,
) -> tuple[str, str, str]:
    now = int(time.time() * 1000)
    run = client.create_run(
        experiment_id,
        start_time=now,
        tags={"keplerops.dependency": model_name, "keplerops.source": label},
    )
    run_id = run.info.run_id
    with tempfile.TemporaryDirectory(prefix="keplerops-dependency-") as directory:
        path = Path(directory) / "policy-model.json"
        path.write_bytes(raw)
        client.log_artifact(run_id, str(path), artifact_path="model")
    artifact_uri = run.info.artifact_uri.rstrip("/") + "/model/policy-model.json"
    version = client.create_model_version(
        name=model_name,
        source=artifact_uri,
        run_id=run_id,
        tags={"keplerops.source": label},
    )
    client.set_terminated(run_id, status="FINISHED", end_time=int(time.time() * 1000))
    return run_id, str(version.version), artifact_uri

def _dependency_decision(raw: bytes) -> str:
    from model_backdoor import load_candidate_artifact

    try:
        model = load_candidate_artifact(raw)
        prediction = model.classifier.predict(
            model.vectorizer.transform(("cobalt-lantern unsigned orbital adapter",))
        )[0]
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="model dependency artifact is invalid") from None
    return "allow" if prediction == "approved" else "deny"

@router.post("/v1/evasion/model-dependencies", responses=ERROR_RESPONSES)
async def resolve_model_dependency(
    request: ModelDependencyRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    from mlflow.exceptions import MlflowException

    _require_role("gateway")
    generation = _require_ready()
    if not await _evasion_policy(session, "kep-m02-j"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _ensure_model_supply_schema()
    selected_source_index = _model_dependency_source_index(request.source_url)
    clean_raw, selected_raw = await asyncio.gather(
        _fetch_model_dependency_artifact(0),
        _fetch_model_dependency_artifact(selected_source_index),
    )
    clean_digest = SHA256_PREFIX + hashlib.sha256(clean_raw).hexdigest()
    source_digest = SHA256_PREFIX + hashlib.sha256(selected_raw).hexdigest()
    clean_decision = _dependency_decision(clean_raw)
    dependency_id = "mdp-" + secrets.token_hex(12)
    model_name = f"keplerops-policy-model-{dependency_id}"
    try:
        client = _mlflow_client()
        experiment = client.get_experiment_by_name("keplerops-model-dependencies")
        experiment_id = (
            client.create_experiment("keplerops-model-dependencies")
            if experiment is None
            else experiment.experiment_id
        )
        client.create_registered_model(
            model_name,
            tags={"keplerops.dependency_id": dependency_id, "keplerops.clean_digest": clean_digest},
        )
        _register_dependency_version(
            client,
            experiment_id=experiment_id,
            model_name=model_name,
            raw=clean_raw,
            label="clean",
        )
        run_id, published_version, _ = _register_dependency_version(
            client,
            experiment_id=experiment_id,
            model_name=model_name,
            raw=selected_raw,
            label="participant-selected",
        )
        client.set_registered_model_alias(model_name, "consumer", published_version)
        resolved = client.get_model_version_by_alias(model_name, "consumer")
        resolved_version = str(resolved.version)
        resolved_raw = _download_backdoor_artifact(str(resolved.source))
    except MlflowException:
        raise HTTPException(status_code=503, detail=MODEL_REGISTRY_UNAVAILABLE) from None
    resolved_digest = SHA256_PREFIX + hashlib.sha256(resolved_raw).hexdigest()
    resolved_decision = _dependency_decision(resolved_raw)
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO model_dependencies (dependency_id, range_instance, participant, "
            "reset_generation, challenge_id, dependency_name, source_url, source_digest, "
            "registry_run_id, registry_model_name, registry_model_version, resolved_digest, "
            "clean_decision, resolved_decision, registry_alias) VALUES (%s, %s, %s, %s, "
            "'kep-m02-j', 'keplerops-policy-model', %s, %s, %s, %s, %s, %s, %s, %s, 'consumer')",
            (
                dependency_id,
                session.range_instance,
                session.participant,
                generation,
                request.source_url,
                source_digest,
                run_id,
                model_name,
                resolved_version,
                resolved_digest,
                clean_decision,
                resolved_decision,
            ),
        )
    _observe(
        session,
        event_name=WORKFLOW_COMPLETED_EVENT,
        outcome_id="model-evasion",
        challenge_id="kep-m02-j",
        status="recorded",
        workflow_run_id=run_id,
        artifact_digest=resolved_digest,
        path_variant="gitea-mlflow-dependency",
        registry_alias="consumer",
        registry_model_version=resolved_version,
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        verdict_class=resolved_decision,
        record_count=1,
    )
    return {
        "dependency_id": dependency_id,
        "dependency_name": "keplerops-policy-model",
        "source_digest": source_digest,
        "registry_model_name": model_name,
        "published_version": published_version,
        "registry_alias": "consumer",
        "resolved_version": resolved_version,
        "resolved_digest": resolved_digest,
        "clean_decision": clean_decision,
        "resolved_decision": resolved_decision,
    }
