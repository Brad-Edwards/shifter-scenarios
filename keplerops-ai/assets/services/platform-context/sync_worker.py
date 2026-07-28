"""Incremental PostgreSQL context synchronization to OpenSearch and WorkHub."""

from __future__ import annotations

import argparse
import base64
import os
import time
from pathlib import Path
from typing import Any

import httpx
import psycopg
from opensearchpy import NotFoundError, OpenSearch
from psycopg.rows import dict_row

from security import read_secret, validate_range_url
from store import StateStore, canonical_json


CAPTURE_SQL = """
CREATE SCHEMA IF NOT EXISTS platform_context;
CREATE TABLE IF NOT EXISTS platform_context.change_log (
    sequence bigserial PRIMARY KEY,
    source_table text NOT NULL,
    operation text NOT NULL CHECK (operation IN ('SNAPSHOT','INSERT','UPDATE','DELETE')),
    document_id text NOT NULL,
    record jsonb NOT NULL,
    changed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE OR REPLACE FUNCTION platform_context.capture_retrieval_change()
RETURNS trigger LANGUAGE plpgsql AS $capture$
DECLARE
    document_key text;
    captured jsonb;
BEGIN
    IF TG_OP = 'DELETE' THEN
        captured := to_jsonb(OLD);
    ELSE
        captured := to_jsonb(NEW);
    END IF;
    IF TG_TABLE_NAME = 'retrieval_documents' THEN
        document_key := captured->>'id';
    ELSE
        document_key := captured->>'document_id';
    END IF;
    INSERT INTO platform_context.change_log
        (source_table, operation, document_id, record)
    VALUES (TG_TABLE_NAME, TG_OP, document_key, captured);
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END
$capture$;
DO $install$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'platform_context_document_change' AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER platform_context_document_change
        AFTER INSERT OR UPDATE OR DELETE ON retrieval_documents
        FOR EACH ROW EXECUTE FUNCTION platform_context.capture_retrieval_change();
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'platform_context_chunk_change' AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER platform_context_chunk_change
        AFTER INSERT OR UPDATE OR DELETE ON retrieval_chunks
        FOR EACH ROW EXECUTE FUNCTION platform_context.capture_retrieval_change();
    END IF;
END
$install$;
INSERT INTO platform_context.change_log
    (source_table, operation, document_id, record)
SELECT 'retrieval_documents', 'SNAPSHOT', document.id, to_jsonb(document)
FROM retrieval_documents AS document
WHERE NOT EXISTS (
    SELECT 1 FROM platform_context.change_log AS existing
    WHERE existing.source_table = 'retrieval_documents'
      AND existing.document_id = document.id
      AND existing.operation IN ('SNAPSHOT', 'INSERT')
);
"""


INDEX_BODY = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "document_id": {"type": "keyword"},
            "title": {"type": "text", "fields": {"exact": {"type": "keyword"}}},
            "claimed_authority": {"type": "keyword"},
            "provenance": {"type": "keyword"},
            "content": {"type": "text"},
            "range_instance": {"type": "keyword"},
            "participant": {"type": "keyword"},
            "reset_generation": {"type": "integer"},
            "current_revision": {"type": "integer"},
            "created_at": {"type": "date"},
            "chunks": {
                "type": "nested",
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "chunk_order": {"type": "integer"},
                    "revision": {"type": "integer"},
                    "content": {"type": "text"},
                    "embedding": {"type": "keyword", "index": False},
                    "created_at": {"type": "date"},
                },
            },
        },
    },
}


class ContextSync:
    consumer = "postgres-context-v1"

    def __init__(self, store: StateStore) -> None:
        self.store = store
        self.postgres_dsn = self._postgres_dsn()
        self.index_name = os.environ.get(
            "PLATFORM_CONTEXT_OPENSEARCH_INDEX", "keplerops-context-v1"
        )
        opensearch_url = validate_range_url(
            os.environ.get(
                "PLATFORM_CONTEXT_OPENSEARCH_URL",
                # Range-local OpenSearch is an isolated, non-credentialed HTTP service.
                "http://research-index-01.keplerops.lab:9200",  # NOSONAR
            )
        )
        parsed = httpx.URL(opensearch_url)
        ca_file = os.environ.get("PLATFORM_CONTEXT_CA_FILE")
        self.opensearch = OpenSearch(
            hosts=[
                {
                    "host": parsed.host,
                    "port": parsed.port or (443 if parsed.scheme == "https" else 80),
                }
            ],
            use_ssl=parsed.scheme == "https",
            verify_certs=bool(ca_file) or parsed.scheme == "https",
            ca_certs=ca_file,
            ssl_assert_hostname=True,
            ssl_show_warn=True,
            timeout=10,
        )
        self.adapter_url = validate_range_url(
            os.environ.get(
                "PLATFORM_CONTEXT_ADAPTER_URL",
                # The adapter is co-located behind the range's contained service network.
                "http://platform-context.keplerops.lab:8480",  # NOSONAR
            )
        )
        self.token_path = Path(
            os.environ.get(
                "PLATFORM_CONTEXT_TOKEN_FILE", "/run/keplerops/platform-context-token"
            )
        )
        self.verify: bool | str = ca_file if ca_file else True
        self.capture_installed = False

    @staticmethod
    def _postgres_dsn() -> str:
        configured = os.environ.get("PLATFORM_CONTEXT_POSTGRES_DSN")
        if configured:
            return configured
        password = read_secret(
            Path(
                os.environ.get(
                    "PLATFORM_CONTEXT_POSTGRES_PASSWORD_FILE",
                    "/run/keplerops/postgres-password",
                )
            )
        )
        host = os.environ.get(
            "PLATFORM_CONTEXT_POSTGRES_HOST", "dataset-store-01.keplerops.lab"
        )
        ca_file = os.environ.get("PLATFORM_CONTEXT_CA_FILE", "/run/tls/ca.crt")
        return (
            f"host={host} port=5432 dbname=keplerops user=keplerops "
            f"password={password} sslmode=verify-full sslrootcert={ca_file}"
        )

    def install_capture(self) -> None:
        with psycopg.connect(self.postgres_dsn, autocommit=True) as connection:
            connection.execute(CAPTURE_SQL)

    def ensure_index(self) -> None:
        if not self.opensearch.indices.exists(index=self.index_name):
            self.opensearch.indices.create(index=self.index_name, body=INDEX_BODY)

    def changes(self, after: int, limit: int = 100) -> list[dict[str, Any]]:
        with psycopg.connect(
            self.postgres_dsn, autocommit=True, row_factory=dict_row
        ) as connection:
            rows = connection.execute(
                "SELECT sequence, source_table, operation, document_id, record, "
                "changed_at::text AS changed_at "
                "FROM platform_context.change_log WHERE sequence > %s "
                "ORDER BY sequence LIMIT %s",
                (after, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def document(self, document_id: str) -> dict[str, Any] | None:
        with psycopg.connect(
            self.postgres_dsn, autocommit=True, row_factory=dict_row
        ) as connection:
            document = connection.execute(
                "SELECT id AS document_id, title, claimed_authority, provenance, content, "
                "range_instance, participant, reset_generation, current_revision, "
                "to_char(created_at AT TIME ZONE 'UTC', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"') AS created_at "
                "FROM retrieval_documents WHERE id=%s",
                (document_id,),
            ).fetchone()
            if document is None:
                return None
            chunks = connection.execute(
                "SELECT chunk_id, chunk_order, revision, content, embedding::text AS embedding, "
                "to_char(created_at AT TIME ZONE 'UTC', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"') AS created_at FROM retrieval_chunks "
                "WHERE document_id=%s ORDER BY revision, chunk_order",
                (document_id,),
            ).fetchall()
        result = dict(document)
        result["chunks"] = [dict(chunk) for chunk in chunks]
        return result

    def _workhub_put(self, sequence: int, document: dict[str, Any]) -> dict[str, Any]:
        content = (canonical_json(document) + "\n").encode("utf-8")
        request = {
            "request_id": f"sync-{sequence}-put",
            "path": f"context/{document['document_id']}.json",
            "content_base64": base64.b64encode(content).decode("ascii"),
            "message": f"Synchronize context change {sequence}",
        }
        with httpx.Client(
            verify=self.verify, timeout=httpx.Timeout(20.0, connect=3.0)
        ) as client:
            response = client.put(
                f"{self.adapter_url}/v1/workhub/artifacts",
                headers={"Authorization": f"Bearer {read_secret(self.token_path)}"},
                json=request,
            )
            response.raise_for_status()
            return {"request": request, "response": response.json()}

    def _workhub_delete(self, sequence: int, document_id: str) -> dict[str, Any]:
        request = {
            "request_id": f"sync-{sequence}-delete",
            "path": f"context/{document_id}.json",
            "message": f"Remove context change {sequence}",
        }
        with httpx.Client(
            verify=self.verify, timeout=httpx.Timeout(20.0, connect=3.0)
        ) as client:
            response = client.request(
                "DELETE",
                f"{self.adapter_url}/v1/workhub/artifacts",
                headers={"Authorization": f"Bearer {read_secret(self.token_path)}"},
                json=request,
            )
            response.raise_for_status()
            return {"request": request, "response": response.json()}

    def apply(self, change: dict[str, Any]) -> None:
        sequence = int(change["sequence"])
        document_id = str(change["document_id"])
        started = time.perf_counter()
        document = self.document(document_id)
        if document is None:
            operation = "delete"
            try:
                response = self.opensearch.delete(
                    index=self.index_name, id=document_id, refresh=True
                )
            except NotFoundError:
                response = {"result": "not_found"}
            self.store.save_delivery(
                sequence, "opensearch", operation, change, dict(response)
            )
            workhub = self._workhub_delete(sequence, document_id)
        else:
            operation = "upsert"
            response = self.opensearch.index(
                index=self.index_name,
                id=document_id,
                body=document,
                refresh=True,
            )
            self.store.save_delivery(
                sequence, "opensearch", operation, document, dict(response)
            )
            workhub = self._workhub_put(sequence, document)
        self.store.save_delivery(
            sequence, "workhub", operation, workhub["request"], workhub["response"]
        )
        result = {
            "source_sequence": sequence,
            "document_id": document_id,
            "operation": operation,
            "opensearch": dict(response),
            "workhub": workhub["response"],
        }
        self.store.record_event(
            event_name="platform_context.document_synchronized",
            operation=f"context.sync.{operation}",
            status="succeeded",
            request_id=f"sync-{sequence}",
            request={"change": change, "document": document},
            response=result,
            source="keplerops-platform-context-sync-worker",
            duration_ms=(time.perf_counter() - started) * 1_000,
        )
        self.store.advance_cursor(self.consumer, sequence)

    def run_once(self) -> int:
        if not self.capture_installed:
            self.install_capture()
            self.capture_installed = True
        self.ensure_index()
        changes = self.changes(self.store.cursor(self.consumer))
        for change in changes:
            self.apply(change)
        self.store.heartbeat(
            "postgres-sync",
            {
                "state": "ready",
                "cursor": self.store.cursor(self.consumer),
                "processed": len(changes),
            },
        )
        return len(changes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    store = StateStore(
        Path(
            os.environ.get(
                "PLATFORM_CONTEXT_STATE_ROOT", "/var/lib/keplerops-platform-context"
            )
        )
    )
    worker = ContextSync(store)
    if args.once:
        worker.run_once()
        return
    while True:
        processed = worker.run_once()
        if processed == 0:
            time.sleep(max(0.1, args.poll_seconds))


if __name__ == "__main__":
    main()
