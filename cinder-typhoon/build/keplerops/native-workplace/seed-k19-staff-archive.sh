#!/bin/sh
# K19.1 seed: staff_archive_handovers table in Kanboard PostgreSQL.
# Uses the DATABASE_URL from the kanboard.env to extract the password.
# Idempotent: ON CONFLICT DO NOTHING.
set -eu

# Extract password from DATABASE_URL (postgres://user:pass@host:port/db)
export PGPASSWORD=$(echo "$DATABASE_URL" | sed 's|.*://[^:]*:\([^@]*\)@.*|\1|')

psql <<'SQL'
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
);
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
ON CONFLICT (subject) DO NOTHING;
SELECT subject, template FROM staff_archive_handovers;
SQL
echo "K19.1 staff_archive_handovers seeded."
