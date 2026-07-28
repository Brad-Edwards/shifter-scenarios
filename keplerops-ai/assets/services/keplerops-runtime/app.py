"""Role-aware composition root for the modular KeplerOps runtime."""

from __future__ import annotations

import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from instrumentation import trusted_root_span
from keplerops_runtime.foundation.auth_storage import _telemetry_enabled
from keplerops_runtime.foundation.challenge_routes import router as challenge_router
from keplerops_runtime.foundation.clients import router as client_lifecycle_router
from keplerops_runtime.foundation.config import CONFIG, NOT_FOUND
from keplerops_runtime.foundation.health import router as health_router
from keplerops_runtime.foundation.policy_routes import router as policy_router
from keplerops_runtime.foundation.portal import router as portal_router
from keplerops_runtime.foundation.telemetry import TRACER
from keplerops_runtime.foundation.telemetry import router as telemetry_lifecycle_router
from keplerops_runtime.modules.m01.routes import router as m01_router
from keplerops_runtime.modules.m02.data_supply import router as m02_data_router
from keplerops_runtime.modules.m02.model_supply import router as m02_model_router
from keplerops_runtime.modules.m02.routes import router as m02_router
from keplerops_runtime.modules.m02.runtime_supply import router as m02_runtime_router
from keplerops_runtime.modules.m02.spearphish import router as m02_spearphish_router
from keplerops_runtime.modules.m02.web_supply import router as m02_web_router
from keplerops_runtime.modules.m03.documents import router as m03_documents_router
from keplerops_runtime.modules.m03.evaluation import router as m03_evaluation_router
from keplerops_runtime.modules.m03.expansion import router as m03_expansion_router
from keplerops_runtime.modules.m03.routes import router as m03_router
from keplerops_runtime.modules.m04.expansion import router as m04_expansion_router
from keplerops_runtime.modules.m04.routes import router as m04_router
from keplerops_runtime.modules.m05.expansion import router as m05_expansion_router
from keplerops_runtime.modules.m05.routes import router as m05_router
from keplerops_runtime.modules.m06.expansion import router as m06_expansion_router
from keplerops_runtime.modules.m06.service import router as m06_router
from keplerops_runtime.modules.m07.datasets import router as m07_dataset_router
from keplerops_runtime.modules.m07.expansion import router as m07_expansion_router
from keplerops_runtime.modules.m07.jobs import router as m07_job_router
from keplerops_runtime.modules.m07.routes import router as m07_router
from keplerops_runtime.modules.m08.corpora import router as m08_corpus_router
from keplerops_runtime.modules.m08.jobs import router as m08_job_router
from keplerops_runtime.modules.m08.platform import router as m08_platform_router
from keplerops_runtime.modules.m09.attempts import router as m09_attempt_router
from keplerops_runtime.modules.m09.candidates import router as m09_candidate_router
from keplerops_runtime.modules.m09.evaluations import router as m09_evaluation_router
from keplerops_runtime.modules.m09.platform import router as m09_platform_router
from keplerops_runtime.modules.m09.transitions import router as m09_transition_router
from keplerops_runtime.modules.m10.artifacts import router as m10_artifact_router
from keplerops_runtime.modules.m10.attempts import router as m10_attempt_router
from keplerops_runtime.modules.m10.effects import router as m10_effect_router
from keplerops_runtime.modules.m10.impact import router as m10_impact_router
from keplerops_runtime.proof.gateway_receipts import router as gateway_receipt_router
from keplerops_runtime.proof.ingest_routes import router as proof_ingest_router
from keplerops_runtime.proof.receipt_routes import router as proof_receipt_router


app = FastAPI(title="KeplerOps range service", docs_url=None, redoc_url=None)

for router in (
    client_lifecycle_router,
    telemetry_lifecycle_router,
    health_router,
    portal_router,
    challenge_router,
    m01_router,
    m02_data_router,
    m02_model_router,
    m02_web_router,
    m02_spearphish_router,
    m02_runtime_router,
    m02_router,
    m03_documents_router,
    m03_evaluation_router,
    m03_expansion_router,
    m03_router,
    m04_expansion_router,
    m04_router,
    m05_expansion_router,
    m05_router,
    m06_expansion_router,
    m06_router,
    m07_dataset_router,
    m07_expansion_router,
    m07_job_router,
    m07_router,
    m08_corpus_router,
    m08_job_router,
    m08_platform_router,
    m09_candidate_router,
    m09_evaluation_router,
    m09_platform_router,
    m09_transition_router,
    m09_attempt_router,
    m10_artifact_router,
    m10_effect_router,
    m10_impact_router,
    m10_attempt_router,
    policy_router,
    proof_ingest_router,
    gateway_receipt_router,
    proof_receipt_router,
):
    app.include_router(router)


@app.middleware("http")
async def trusted_server_trace(request: Request, call_next):
    server = request.scope.get("server")
    internal_ingest = (
        isinstance(server, (list, tuple)) and len(server) == 2 and server[1] == 4319
    )
    if request.url.path.startswith("/v1/research/") and not internal_ingest:
        return JSONResponse(status_code=404, content={"detail": NOT_FOUND})
    if not _telemetry_enabled():
        return await call_next(request)
    with trusted_root_span(
        TRACER,
        "keplerops.http.server",
        {
            "http.request.method": request.method,
            "url.path": request.url.path,
            "keplerops.asset.id": str(CONFIG.get("asset_id")),
        },
    ):
        return await call_next(request)


@app.exception_handler(Exception)
async def bounded_error(_: Request, error: Exception) -> JSONResponse:
    if isinstance(error, HTTPException):
        return JSONResponse(
            status_code=error.status_code, content={"detail": error.detail}
        )
    correlation_id = secrets.token_hex(8)
    return JSONResponse(
        status_code=500,
        content={"detail": "request failed", "correlation_id": correlation_id},
    )
