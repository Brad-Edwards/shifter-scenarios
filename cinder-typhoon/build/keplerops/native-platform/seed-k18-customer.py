#!/usr/bin/env python3
"""K18.4 seed: support.customer_records table in fieldlink_data PostgreSQL.

Creates the support schema and customer_records table, then inserts
the CUSTREC-047-R6 record needed for K18.4 federated session access.

This seed is idempotent (ON CONFLICT DO NOTHING).
"""

from __future__ import annotations

import os
import sys

import psycopg2


def main() -> None:
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgres://fieldlink_admin:@fieldlink-postgres:5432/fieldlink_data",
    )
    conn = psycopg2.connect(db_url, connect_timeout=10)
    with conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS support")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS support.customer_records (
                    record_id TEXT PRIMARY KEY,
                    tenant TEXT NOT NULL,
                    connector_revision TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    case_ref TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                INSERT INTO support.customer_records
                    (record_id, tenant, connector_revision, asset, case_ref)
                VALUES ('CUSTREC-047-R6', 'TEN-ARWC-047', 'FLK-7.4.2', 'CRR-OG2', 'SUP-2841')
                ON CONFLICT (record_id) DO NOTHING
            """)
    conn.close()
    print("K18.4 customer record seeded: CUSTREC-047-R6 in support.customer_records")


if __name__ == "__main__":
    main()
