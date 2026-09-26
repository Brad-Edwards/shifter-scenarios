#!/bin/sh
set -eu

ip route replace 10.77.50.0/24 via "$FIELDKEST_GATEWAY"
ip route replace 10.77.51.0/24 via "$FIELDKEST_GATEWAY"
ip route replace 10.77.53.0/24 via "$FIELDKEST_GATEWAY"
ip route replace 10.77.60.0/24 via "$FIELDKEST_GATEWAY"
install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
install -m 0444 /run/fieldkest-tls/ca.crt /tmp/fieldkest-ca.crt

pgdata=/var/lib/postgresql/16/fieldkest-history
if ! gosu postgres test -s "$pgdata/PG_VERSION"; then
  gosu postgres /usr/lib/postgresql/16/bin/initdb -D "$pgdata" --auth-local=trust --auth-host=scram-sha-256 >/dev/null
  gosu postgres sh -c 'printf "listen_addresses = '\''10.77.52.40'\''\nport = 5432\nunix_socket_directories = '\''/tmp'\''\n" >>"$1/postgresql.conf"' sh "$pgdata"
  gosu postgres sh -c 'printf "host all all 10.77.52.0/24 scram-sha-256\n" >>"$1/pg_hba.conf"' sh "$pgdata"
fi
gosu postgres /usr/lib/postgresql/16/bin/pg_ctl -D "$pgdata" -l /tmp/postgresql.log -w start
if ! setpriv --reuid=fieldkest-data --regid=fieldkest-data --init-groups \
  test -s /var/lib/fieldkest-data/backups/BAK-2026-021.json; then
  gosu postgres psql -h /tmp -v ON_ERROR_STOP=1 --dbname postgres <<'SQL'
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'svc_fieldkest_backup') THEN
    CREATE ROLE svc_fieldkest_backup LOGIN PASSWORD 'Backup-FieldKest-2026';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'svc_history_recovery') THEN
    CREATE ROLE svc_history_recovery NOLOGIN;
  END IF;
END $$;
SELECT 'CREATE DATABASE fieldkest_history' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'fieldkest_history')\gexec
SQL
  gosu postgres psql -h /tmp -v ON_ERROR_STOP=1 --dbname fieldkest_history <<'SQL'
CREATE SCHEMA IF NOT EXISTS support;
CREATE TABLE IF NOT EXISTS support.customer_migration_history (
  former_name text PRIMARY KEY,
  former_tenant text NOT NULL,
  former_revision text NOT NULL,
  current_tenant text NOT NULL,
  current_revision text NOT NULL,
  effective_date date NOT NULL
);
INSERT INTO support.customer_migration_history VALUES
  ('ARWC FieldLink legacy','TEN-ARWC-019','FLK-6.9.8','TEN-ARWC-047','FLK-7.4.2','2026-02-17')
ON CONFLICT (former_name) DO NOTHING;
REVOKE ALL ON SCHEMA support FROM PUBLIC;
REVOKE ALL ON support.customer_migration_history FROM PUBLIC;
GRANT USAGE ON SCHEMA support TO svc_fieldkest_backup;
GRANT SELECT ON support.customer_migration_history TO svc_fieldkest_backup;
SQL
  gosu postgres psql -h /tmp --dbname fieldkest_history -tAX -c "SELECT json_build_object('backup_id','BAK-2026-021','source_database','fieldkest_history','schema','support.customer_migration_history','records',json_agg(row_to_json(h))) FROM (SELECT former_name,former_tenant,former_revision,current_tenant,current_revision,effective_date::text AS effective_date FROM support.customer_migration_history ORDER BY former_name) h" >/tmp/BAK-2026-021.json
  setpriv --reuid=fieldkest-data --regid=fieldkest-data --init-groups \
    sh -c 'umask 077; cat > /var/lib/fieldkest-data/backups/BAK-2026-021.json.tmp' \
    </tmp/BAK-2026-021.json
  setpriv --reuid=fieldkest-data --regid=fieldkest-data --init-groups \
    mv /var/lib/fieldkest-data/backups/BAK-2026-021.json.tmp /var/lib/fieldkest-data/backups/BAK-2026-021.json
  rm -f /tmp/BAK-2026-021.json
fi

setpriv --reuid=fieldkest-data --regid=fieldkest-data --init-groups python3 /opt/fieldkest-data/platform_service.py &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true; gosu postgres /usr/lib/postgresql/16/bin/pg_ctl -D "$pgdata" -m fast stop >/dev/null 2>&1 || true' INT TERM EXIT
wait "$api_pid"
