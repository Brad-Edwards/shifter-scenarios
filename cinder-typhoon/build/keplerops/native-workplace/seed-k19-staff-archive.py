#!/usr/bin/env python3
"""K19.1 seed: staff_archive_handovers table in Kanboard PostgreSQL.

Creates the table and inserts the enrollment trust relationship for
rowan.ito@keplerops.test: who vouched for the StaffArchiveUser cert.

This seed is idempotent (ON CONFLICT DO NOTHING).
"""

from __future__ import annotations

import os
import sys

import psycopg2


def main() -> None:
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgres://fieldlink_staff:@fieldlink-postgres:5432/fieldlink_staff",
    )
    conn = psycopg2.connect(db_url, connect_timeout=10)
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS staff_archive_handovers (
                    subject TEXT PRIMARY KEY,
                    provisioner TEXT NOT NULL,
                    provisioner_type TEXT NOT NULL,
                    idp TEXT NOT NULL,
                    idp_config TEXT NOT NULL,
                    issued_by TEXT NOT NULL,
                    template TEXT NOT NULL,
                    template_eku TEXT[] NOT NULL,
                    grant_name TEXT NOT NULL,
                    archive_ref TEXT NOT NULL,
                    vouched_by TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                INSERT INTO staff_archive_handovers (
                    subject, provisioner, provisioner_type, idp, idp_config,
                    issued_by, template, template_eku, grant_name, archive_ref, vouched_by
                ) VALUES (
                    'rowan.ito@keplerops.test',
                    'keplerops-staff',
                    'OIDC',
                    'fieldlink-enrollment',
                    'https://identity.keplerops.test/realms/keplerops/.well-known/openid-configuration',
                    'FieldKest Enrollment CA',
                    'StaffArchiveUser',
                    ARRAY['clientAuth'],
                    'support-runner-enrollment',
                    'REL-FLK-7.4.2-09',
                    'keplerops-staff (fieldlink-enrollment) via Keycloak keplerops realm'
                )
                ON CONFLICT (subject) DO NOTHING
            """)
    conn.close()
    print("K19.1 staff_archive_handovers seeded.")


if __name__ == "__main__":
    main()
