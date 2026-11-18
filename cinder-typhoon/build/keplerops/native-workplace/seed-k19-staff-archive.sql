-- K19 seed: staff_archive_handovers table in the fieldlink_staff database.
-- k-staff reads this table for the archive handover (K19.2) and the delegation
-- relation (K19.3 -> K20). Idempotent: ON CONFLICT DO NOTHING plus guarded ALTER.
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
ALTER TABLE staff_archive_handovers ADD COLUMN IF NOT EXISTS delegation_spn TEXT;
ALTER TABLE staff_archive_handovers ADD COLUMN IF NOT EXISTS service_relation TEXT;
INSERT INTO staff_archive_handovers (
    subject, provisioner, provisioner_type, idp, idp_config,
    issued_by, template, template_eku, grant_name, archive_ref, vouched_by,
    delegation_spn, service_relation
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
        'keplerops-staff (fieldlink-enrollment) via Keycloak keplerops realm',
        NULL,
        NULL
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
UPDATE staff_archive_handovers
SET delegation_spn = 'HTTP/staff.keplerops.test@KEPLEROPS.TEST',
    service_relation = 'svc-fieldlink-staff-evan'
WHERE subject = 'evan.calderoux@keplerops.test'
  AND delegation_spn IS NULL;
