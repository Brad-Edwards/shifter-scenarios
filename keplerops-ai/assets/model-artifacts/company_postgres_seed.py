#!/usr/bin/env python3
"""Render ordinary company dataset metadata into an isolated PostgreSQL schema."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "company_state"
OWNER = "keplerops-company-state"
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]{2,127}$")
REQUIRED_FIELDS = {
    "id",
    "project_ref",
    "owner_ref",
    "version",
    "created_at",
    "digest",
    "source_path",
}


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def load_datasets(path: Path) -> list[dict[str, Any]]:  # NOSONAR - cohesive validation.
    # The immutable PostgreSQL image build supplies the committed corpus path.
    corpus = yaml.safe_load(path.read_text(encoding="utf-8"))  # NOSONAR
    if not isinstance(corpus, dict) or corpus.get("schema_version") != 1:
        raise ValueError("company state must use schema version 1")
    rows = corpus.get("datasets")
    if not isinstance(rows, list) or not rows:
        raise ValueError("company state must declare datasets")

    identifiers: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != REQUIRED_FIELDS:
            raise ValueError("company dataset has an invalid schema")
        identifier = row.get("id")
        if (
            not isinstance(identifier, str)
            or not IDENTIFIER.fullmatch(identifier)
            or identifier.startswith(("kep-m", "challenge-", "flag-"))
        ):
            raise ValueError("company dataset has an invalid or reserved id")
        if identifier in identifiers:
            raise ValueError(f"duplicate company dataset id: {identifier}")
        identifiers.add(identifier)
        if not isinstance(row.get("digest"), str) or not DIGEST.fullmatch(row["digest"]):
            raise ValueError(f"company dataset has an invalid digest: {identifier}")
        normalized.append(dict(row))
    return sorted(normalized, key=lambda item: item["id"])


def dataset_records(path: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for row in load_datasets(path):
        payload = canonical_json(row)
        records.append(
            {
                "dataset_id": row["id"],
                "project_ref": row["project_ref"],
                "owner_ref": row["owner_ref"],
                "version": str(row["version"]),
                "represented_created_at": row["created_at"],
                "declared_digest": row["digest"],
                "canonical_payload": payload,
                "object_digest": sha256(payload),
            }
        )
    return records


def manifest_digest(records: list[dict[str, str]]) -> str:
    joined = "\n".join(record["object_digest"] for record in records)
    return sha256(joined)


def render_sql(path: Path) -> str:
    records = dataset_records(path)
    expected_digest = manifest_digest(records)
    values = ",\n".join(
        "    ("
        + ", ".join(
            sql_literal(record[field])
            for field in (
                "dataset_id",
                "project_ref",
                "owner_ref",
                "version",
                "represented_created_at",
                "declared_digest",
                "canonical_payload",
                "object_digest",
            )
        )
        + ")"
        for record in records
    )
    return f"""\\set ON_ERROR_STOP on
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $company_state_collision$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = '{SCHEMA}') THEN
        RAISE EXCEPTION 'ownership collision: schema {SCHEMA} already exists';
    END IF;
END
$company_state_collision$;

CREATE SCHEMA {SCHEMA};
COMMENT ON SCHEMA {SCHEMA} IS 'owner={OWNER}';

CREATE TABLE {SCHEMA}.datasets (
    dataset_id text PRIMARY KEY CHECK (dataset_id ~ '^[a-z][a-z0-9-]{{2,127}}$'),
    project_ref text NOT NULL,
    owner_ref text NOT NULL,
    version text NOT NULL,
    represented_created_at timestamptz NOT NULL,
    declared_digest text NOT NULL CHECK (declared_digest ~ '^sha256:[0-9a-f]{{64}}$'),
    canonical_payload text NOT NULL CHECK (jsonb_typeof(canonical_payload::jsonb) = 'object'),
    object_digest text NOT NULL CHECK (object_digest ~ '^sha256:[0-9a-f]{{64}}$'),
    CONSTRAINT company_dataset_namespace CHECK (
        dataset_id !~ '^(kep-m|challenge-|flag-)'
    )
);
CREATE INDEX company_datasets_project_created_idx
    ON {SCHEMA}.datasets (project_ref, represented_created_at);
CREATE INDEX company_datasets_owner_idx
    ON {SCHEMA}.datasets (owner_ref);

INSERT INTO {SCHEMA}.datasets (
    dataset_id,
    project_ref,
    owner_ref,
    version,
    represented_created_at,
    declared_digest,
    canonical_payload,
    object_digest
) VALUES
{values};

CREATE TABLE {SCHEMA}.readback_manifest (
    namespace text PRIMARY KEY CHECK (namespace = '{SCHEMA}.datasets'),
    owner_id text NOT NULL CHECK (owner_id = '{OWNER}'),
    object_count integer NOT NULL CHECK (object_count > 0),
    canonical_digest text NOT NULL CHECK (canonical_digest ~ '^sha256:[0-9a-f]{{64}}$')
);
INSERT INTO {SCHEMA}.readback_manifest
    (namespace, owner_id, object_count, canonical_digest)
VALUES
    ('{SCHEMA}.datasets', '{OWNER}', {len(records)}, '{expected_digest}');

CREATE VIEW {SCHEMA}.dataset_readback AS
SELECT
    dataset_id AS object_id,
    canonical_payload,
    object_digest
FROM {SCHEMA}.datasets;

DO $company_state_readback$
DECLARE
    actual_count integer;
    actual_digest text;
    invalid_digests integer;
BEGIN
    SELECT
        count(*),
        'sha256:' || encode(
            digest(
                convert_to(string_agg(object_digest, E'\\n' ORDER BY object_id), 'UTF8'),
                'sha256'
            ),
            'hex'
        ),
        count(*) FILTER (
            WHERE object_digest <> 'sha256:' || encode(
                digest(convert_to(canonical_payload, 'UTF8'), 'sha256'),
                'hex'
            )
        )
    INTO actual_count, actual_digest, invalid_digests
    FROM {SCHEMA}.dataset_readback;

    IF actual_count <> {len(records)}
        OR actual_digest <> '{expected_digest}'
        OR invalid_digests <> 0 THEN
        RAISE EXCEPTION 'company dataset native readback digest mismatch';
    END IF;
END
$company_state_readback$;
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--company-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rendered = render_sql(args.company_state)
    # The Docker build selects this output inside its private build workspace.
    args.output.write_text(rendered, encoding="utf-8")  # NOSONAR
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
