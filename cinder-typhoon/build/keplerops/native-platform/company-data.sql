CREATE SCHEMA IF NOT EXISTS support AUTHORIZATION fieldlink_data_owner;
CREATE TABLE IF NOT EXISTS support.customer_migration_history (
    former_name text PRIMARY KEY,
    former_tenant text NOT NULL,
    former_revision text NOT NULL,
    current_tenant text NOT NULL,
    current_revision text NOT NULL,
    effective_date date NOT NULL
);
ALTER TABLE support.customer_migration_history OWNER TO fieldlink_data_owner;
INSERT INTO support.customer_migration_history VALUES
('ARWC FieldLink legacy','TEN-ARWC-019','FLK-6.9.8','TEN-ARWC-047','FLK-7.4.2','2026-02-17')
ON CONFLICT (former_name) DO NOTHING;
REVOKE ALL ON SCHEMA support FROM PUBLIC;
REVOKE ALL ON support.customer_migration_history FROM PUBLIC;
GRANT USAGE ON SCHEMA support TO rowan_data;
GRANT SELECT ON support.customer_migration_history TO rowan_data;
CREATE SCHEMA IF NOT EXISTS workspace AUTHORIZATION rowan_data;

-- K15.4: export partition_bindings table for partition join validation.
-- Records which tenant/partition/connector_revision combinations are valid for each export.
-- The join must resolve against real PostgreSQL records (not K3s ConfigMap stubs).
CREATE SCHEMA IF NOT EXISTS export AUTHORIZATION fieldlink_data_owner;
CREATE TABLE IF NOT EXISTS export.partition_bindings (
    export_id text NOT NULL,
    tenant text NOT NULL,
    partition_id text NOT NULL,
    connector_revision text NOT NULL,
    revision integer NOT NULL,
    is_current boolean NOT NULL DEFAULT true,
    PRIMARY KEY (export_id, tenant, partition_id)
);
ALTER TABLE export.partition_bindings OWNER TO fieldlink_data_owner;
INSERT INTO export.partition_bindings VALUES
    ('EXP-2841', 'TEN-ARWC-019', 'PART-ARWC-01', 'FLK-7.4.2', 6, true),
    ('EXP-2841', 'TEN-OTHER-001', 'PART-ARWC-02', 'FLK-7.3.1', 5, false)
ON CONFLICT (export_id, tenant, partition_id) DO NOTHING;
REVOKE ALL ON SCHEMA export FROM PUBLIC;
REVOKE ALL ON export.partition_bindings FROM PUBLIC;
GRANT USAGE ON SCHEMA export TO rowan_data;
GRANT SELECT ON export.partition_bindings TO rowan_data;
