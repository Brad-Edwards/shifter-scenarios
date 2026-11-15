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
