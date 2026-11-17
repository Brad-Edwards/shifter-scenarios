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
    delegation_spn TEXT,
    service_relation TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO staff_archive_handovers (
    subject, provisioner, provisioner_type, idp, idp_config,
    issued_by, template, template_eku, grant_name, archive_ref, vouched_by
) VALUES
    (
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
    ),
    (
        'evan.calderoux@keplerops.test',
        'keplerops-staff',
        'OIDC',
        'fieldlink-enrollment',
        'https://identity.keplerops.test/realms/keplerops/.well-known/openid-configuration',
        'FieldKest Enrollment CA',
        'StaffArchiveUser',
        ARRAY['clientAuth'],
        'support-runner-enrollment',
        'REL-FLK-7.4.2-11',
        'keplerops-staff (fieldlink-enrollment) via Keycloak keplerops realm',
        'HTTP/staff.keplerops.test@KEPLEROPS.TEST',
        'svc-fieldlink-staff-evan'
    )
ON CONFLICT (subject) DO NOTHING;
-- Add columns if they don't exist (for existing deployments)
ALTER TABLE staff_archive_handovers ADD COLUMN IF NOT EXISTS delegation_spn TEXT;
ALTER TABLE staff_archive_handovers ADD COLUMN IF NOT EXISTS service_relation TEXT;
-- Update evan's row with delegation fields (idempotent)
UPDATE staff_archive_handovers
SET delegation_spn = 'HTTP/staff.keplerops.test@KEPLEROPS.TEST',
    service_relation = 'svc-fieldlink-staff-evan'
WHERE subject = 'evan.calderoux@keplerops.test'
  AND delegation_spn IS NULL;
SELECT subject, archive_ref FROM staff_archive_handovers ORDER BY subject;
SQL
echo "K19.1 staff_archive_handovers seeded."
