from __future__ import annotations

from context_poisoning import ContextEmbedder
from context_poisoning import ContextPoisoningError
from context_poisoning import RetrievalHit
from context_poisoning import chunk_document
from context_poisoning import score_bucket
from context_poisoning import vector_literal
from domain import SessionClaims
from fastapi import HTTPException
from functools import lru_cache
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready
from keplerops_runtime.foundation.config import CONFIG, CONTEXT_EMBEDDING_UNAVAILABLE, CONTEXT_INDEX_UNAVAILABLE, PROOF_SERVICE_UNAVAILABLE, SHA256_PREFIX, _regular_owner_file
from keplerops_runtime.modules.m01.store import _agent_digest
from pathlib import Path
from typing import Any
import hashlib
import hmac
import time


@lru_cache(maxsize=1)
def _context_embedder() -> ContextEmbedder:
    path = CONFIG.get("embedding_model_path")
    if not isinstance(path, str):
        raise HTTPException(status_code=503, detail=CONTEXT_EMBEDDING_UNAVAILABLE)
    try:
        return ContextEmbedder(Path(path))
    except ContextPoisoningError:
        raise HTTPException(status_code=503, detail=CONTEXT_EMBEDDING_UNAVAILABLE) from None

def _context_vectors(texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
    try:
        return _context_embedder().embed(texts)
    except ContextPoisoningError:
        raise HTTPException(status_code=503, detail=CONTEXT_EMBEDDING_UNAVAILABLE) from None

def _context_chunks(content: str, words_per_chunk: int, overlap_words: int) -> tuple[str, ...]:
    try:
        return chunk_document(
            content,
            words_per_chunk=words_per_chunk,
            overlap_words=overlap_words,
        )
    except ContextPoisoningError:
        raise HTTPException(status_code=422, detail="invalid context document") from None

def _insert_context_chunks(
    connection: Any,
    *,
    document_id: str,
    revision: int,
    chunks: tuple[str, ...],
) -> None:
    vectors = _context_vectors(chunks)
    for order, (content, vector) in enumerate(zip(chunks, vectors)):
        chunk_id = hashlib.sha256(
            f"{document_id}:{revision}:{order}".encode("ascii")
        ).hexdigest()[:32]
        connection.execute(
            "INSERT INTO retrieval_chunks "
            "(chunk_id, document_id, chunk_order, revision, content, embedding) "
            "VALUES (%s, %s, %s, %s, %s, %s::vector) ON CONFLICT DO NOTHING",
            (chunk_id, document_id, order, revision, content, vector_literal(vector)),
        )

def _ensure_trusted_context_chunks() -> None:
    with _postgres() as connection:
        trusted = connection.execute(
            "SELECT d.id, d.content, d.current_revision FROM retrieval_documents d "
            "WHERE d.provenance='trusted' AND NOT EXISTS ("
            "SELECT 1 FROM retrieval_chunks c WHERE c.document_id=d.id "
            "AND c.revision=d.current_revision)",
        ).fetchall()
        for document_id, content, revision in trusted:
            if not isinstance(document_id, str) or not isinstance(content, str):
                raise HTTPException(status_code=503, detail=CONTEXT_INDEX_UNAVAILABLE)
            _insert_context_chunks(
                connection,
                document_id=document_id,
                revision=int(revision),
                chunks=_context_chunks(content, 96, 16),
            )

def _ensure_context_index(session: SessionClaims) -> int:
    generation = _require_ready()
    _ensure_trusted_context_chunks()
    with _postgres() as connection:
        current = connection.execute(
            "SELECT COALESCE(MAX(revision), 0) FROM retrieval_index_revisions "
            "WHERE range_instance=%s AND participant=%s AND reset_generation=%s",
            (session.range_instance, session.participant, generation),
        ).fetchone()
        revision = int(current[0]) if current is not None else 0
        if revision == 0:
            counts = connection.execute(
                "SELECT COUNT(DISTINCT d.id), COUNT(c.chunk_id) "
                "FROM retrieval_documents d JOIN retrieval_chunks c ON c.document_id=d.id "
                "AND c.revision=d.current_revision WHERE d.provenance='trusted' OR "
                "(d.range_instance=%s AND d.participant=%s AND d.reset_generation=%s)",
                (session.range_instance, session.participant, generation),
            ).fetchone()
            connection.execute(
                "INSERT INTO retrieval_index_revisions "
                "(range_instance, participant, reset_generation, revision, document_count, chunk_count) "
                "VALUES (%s, %s, %s, 1, %s, %s)",
                (
                    session.range_instance,
                    session.participant,
                    generation,
                    int(counts[0]),
                    int(counts[1]),
                ),
            )
            revision = 1
    return revision

def _search_context(
    session: SessionClaims, query: str, *, top_k: int
) -> tuple[tuple[RetrievalHit, ...], int]:
    index_revision = _ensure_context_index(session)
    query_vector = vector_literal(_context_vectors((query,))[0])
    generation = _require_ready()
    with _postgres() as connection:
        rows = connection.execute(
            "SELECT d.id, c.chunk_id, d.provenance, d.claimed_authority, "
            "1 - (c.embedding <=> %s::vector) AS score, c.revision "
            "FROM retrieval_chunks c JOIN retrieval_documents d ON d.id=c.document_id "
            "WHERE c.revision=d.current_revision AND (d.provenance='trusted' OR "
            "(d.provenance IN ('participant', 'model') AND d.range_instance=%s "
            "AND d.participant=%s "
            "AND d.reset_generation=%s)) ORDER BY c.embedding <=> %s::vector, c.chunk_id LIMIT %s",
            (
                query_vector,
                session.range_instance,
                session.participant,
                generation,
                query_vector,
                top_k,
            ),
        ).fetchall()
    hits = tuple(
        RetrievalHit(
            document_id=str(row[0]),
            chunk_id=str(row[1]),
            provenance=str(row[2]),
            claimed_authority=str(row[3]),
            rank=rank,
            score=float(row[4]),
            index_revision=int(row[5]),
        )
        for rank, row in enumerate(rows, start=1)
    )
    return hits, index_revision

def _context_passages(hits: tuple[RetrievalHit, ...]) -> str:
    if not hits:
        raise HTTPException(status_code=503, detail=CONTEXT_INDEX_UNAVAILABLE)
    chunk_ids = [hit.chunk_id for hit in hits]
    with _postgres() as connection:
        rows = connection.execute(
            "SELECT c.chunk_id, c.content, d.claimed_authority FROM retrieval_chunks c "
            "JOIN retrieval_documents d ON d.id=c.document_id WHERE c.chunk_id=ANY(%s)",
            (chunk_ids,),
        ).fetchall()
    by_id = {str(row[0]): (str(row[1]), str(row[2])) for row in rows}
    return "\n".join(
        f"[{hit.rank}] authority={by_id[hit.chunk_id][1]} content={by_id[hit.chunk_id][0]}"
        for hit in hits
        if hit.chunk_id in by_id
    )

def _trusted_context() -> str:
    with _postgres() as connection:
        rows = connection.execute(
            "SELECT claimed_authority, content FROM retrieval_documents "
            "WHERE provenance='trusted' ORDER BY id",
        ).fetchall()
    if not rows:
        raise HTTPException(status_code=503, detail="trusted context unavailable")
    return "\n".join(f"authority={row[0]} content={row[1]}" for row in rows)

def _retrieval_document_content(document_id: str) -> tuple[str, str, str]:
    with _postgres() as connection:
        row = connection.execute(
            "SELECT provenance, claimed_authority, content FROM retrieval_documents "
            "WHERE id=%s",
            (document_id,),
        ).fetchone()
    if row is None or not all(isinstance(value, str) for value in row):
        raise HTTPException(status_code=404, detail="context document not found")
    return str(row[0]), str(row[1]), str(row[2])

def _response_digest(session: SessionClaims, label: str, response: str) -> str:
    token_file = CONFIG.get("service_token_file")
    if not isinstance(token_file, str):
        raise HTTPException(status_code=503, detail=PROOF_SERVICE_UNAVAILABLE)
    key = _regular_owner_file(Path(token_file))
    material = f"{session.range_instance}:{session.participant}:{label}:{response}".encode()
    return SHA256_PREFIX + hmac.new(key, material, hashlib.sha256).hexdigest()

def _context_document_id(session: SessionClaims, content: str) -> str:
    return _agent_digest(
        session, "context-document", f"{time.time_ns()}:{content}"
    ).removeprefix(SHA256_PREFIX)[:24]

def _participant_context_hits(hits: tuple[RetrievalHit, ...]) -> list[dict[str, Any]]:
    return [
        {
            "document_id": hit.document_id,
            "chunk_id": hit.chunk_id,
            "provenance": hit.provenance,
            "claimed_authority": hit.claimed_authority,
            "rank": hit.rank,
            "score_bucket": score_bucket(hit.score),
            "document_revision": hit.index_revision,
        }
        for hit in hits
    ]
