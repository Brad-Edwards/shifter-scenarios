from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, ERROR_RESPONSES, NOT_FOUND, OBJECTIVE_ATTEMPTED_EVENT, WORKFLOW_COMPLETED_EVENT
from keplerops_runtime.foundation.policy_client import _policy
from keplerops_runtime.foundation.telemetry import _capture, _observe
from keplerops_runtime.modules.m01.store import _agent_digest
from keplerops_runtime.modules.m03 import ContextDocumentRequest, ContextReindexRequest, ContextSearchRequest
from keplerops_runtime.modules.m03.index import _context_chunks, _context_document_id, _ensure_context_index, _insert_context_chunks, _participant_context_hits, _search_context
from typing import Annotated
from typing import Any
import time

router = APIRouter()


@router.post("/v1/context/documents", status_code=201, responses=ERROR_RESPONSES)
async def write_context_document(
    request: ContextDocumentRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _policy(session, "submit_evaluation"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    chunks = _context_chunks(
        request.content, request.words_per_chunk, request.overlap_words
    )
    document_id = _context_document_id(session, request.content)
    with _postgres() as connection:
        connection.execute(
            "INSERT INTO retrieval_documents "
            "(id, title, claimed_authority, provenance, content, range_instance, participant, reset_generation) "
            "VALUES (%s, %s, %s, 'participant', %s, %s, %s, %s)",
            (
                document_id,
                request.title,
                request.claimed_authority,
                request.content,
                session.range_instance,
                session.participant,
                generation,
            ),
        )
        _insert_context_chunks(
            connection,
            document_id=document_id,
            revision=1,
            chunks=chunks,
        )
    _ensure_context_index(session)
    _capture(session, signal="http_body", content=request.content)
    digest = _agent_digest(session, "context-document-digest", request.content)
    _observe(
        session,
        event_name=WORKFLOW_COMPLETED_EVENT,
        outcome_id="context-poisoning",
        status="recorded",
        artifact_digest=digest,
        record_count=len(chunks),
        iteration_count=1,
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
    )
    return {
        "document_id": document_id,
        "document_revision": 1,
        "chunk_count": len(chunks),
        "status": "indexed",
    }

@router.post("/v1/context/search", responses=ERROR_RESPONSES)
async def search_context(
    request: ContextSearchRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _policy(session, "read_context"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    started = time.monotonic_ns()
    hits, index_revision = _search_context(session, request.query, top_k=request.top_k)
    _observe(
        session,
        event_name=OBJECTIVE_ATTEMPTED_EVENT,
        outcome_id="context-poisoning",
        status="recorded",
        duration_ms=(time.monotonic_ns() - started) // 1_000_000,
        query_count=1,
        record_count=len(hits),
        iteration_count=index_revision,
        state_digest=_agent_digest(session, "context-query", request.query),
    )
    return {
        "index_revision": index_revision,
        "hits": _participant_context_hits(hits),
    }

@router.post("/v1/context/reindex", responses=ERROR_RESPONSES)
async def reindex_context_document(
    request: ContextReindexRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _policy(session, "submit_evaluation"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    chunks = _context_chunks(request.content, 96, 16)
    with _postgres() as connection:
        row = connection.execute(
            "SELECT current_revision FROM retrieval_documents WHERE id=%s "
            "AND provenance='participant' AND range_instance=%s AND participant=%s "
            "AND reset_generation=%s FOR UPDATE",
            (
                request.document_id,
                session.range_instance,
                session.participant,
                generation,
            ),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        document_revision = int(row[0]) + 1
        connection.execute(
            "UPDATE retrieval_documents SET content=%s, current_revision=%s WHERE id=%s",
            (request.content, document_revision, request.document_id),
        )
        _insert_context_chunks(
            connection,
            document_id=request.document_id,
            revision=document_revision,
            chunks=chunks,
        )
        row = connection.execute(
            "SELECT COALESCE(MAX(revision), 1) FROM retrieval_index_revisions "
            "WHERE range_instance=%s AND participant=%s AND reset_generation=%s",
            (session.range_instance, session.participant, generation),
        ).fetchone()
        index_revision = int(row[0]) + 1
        counts = connection.execute(
            "SELECT COUNT(DISTINCT d.id), COUNT(c.chunk_id) FROM retrieval_documents d "
            "JOIN retrieval_chunks c ON c.document_id=d.id AND c.revision=d.current_revision "
            "WHERE d.provenance='trusted' OR (d.range_instance=%s AND d.participant=%s "
            "AND d.reset_generation=%s)",
            (session.range_instance, session.participant, generation),
        ).fetchone()
        connection.execute(
            "INSERT INTO retrieval_index_revisions "
            "(range_instance, participant, reset_generation, revision, document_count, chunk_count) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                session.range_instance,
                session.participant,
                generation,
                index_revision,
                int(counts[0]),
                int(counts[1]),
            ),
        )
    _capture(session, signal="http_body", content=request.content)
    _observe(
        session,
        event_name=WORKFLOW_COMPLETED_EVENT,
        outcome_id="context-poisoning",
        status="recorded",
        artifact_digest=_agent_digest(session, "context-reindex", request.content),
        record_count=len(chunks),
        iteration_count=document_revision,
        workflow_run_id=f"index-{index_revision}",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
    )
    return {
        "document_id": request.document_id,
        "document_revision": document_revision,
        "index_revision": index_revision,
        "chunk_count": len(chunks),
        "status": "reindexed",
    }
