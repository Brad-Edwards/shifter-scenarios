#!/bin/bash
set -euo pipefail
umask 077

chown arwc-data:arwc-data /var/lib/arwc-data
chmod 0700 /var/lib/arwc-data
install -d -o arwc-data -g arwc-data -m 0700 \
  /var/lib/arwc-data/audit \
  /var/lib/arwc-data/auth \
  /var/lib/arwc-data/state \
  /var/lib/arwc-data/results

session=/run/arwc-corporate/handover/corporate-session
for _ in $(seq 1 60); do
  [[ -s $session ]] && break
  sleep 1
done
[[ -s $session ]]
tr -d '\n' < "$session" | sha256sum | awk '{print $1}' \
  > /var/lib/arwc-data/auth/corporate-session.sha256
chown arwc-data:arwc-data /var/lib/arwc-data/auth/corporate-session.sha256
chmod 0400 /var/lib/arwc-data/auth/corporate-session.sha256

for file in server.crt server.key; do
  install -o arwc-data -g arwc-data -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

install -d -o postgres -g postgres -m 0700 "$PGDATA"
chown postgres:postgres /var/run/postgresql
chmod 2775 /var/run/postgresql
if [[ ! -s $PGDATA/PG_VERSION ]]; then
  gosu postgres initdb -D "$PGDATA" --auth-local=trust --auth-host=scram-sha-256 >/dev/null
  cat >>"$PGDATA/postgresql.conf" <<'EOF'
listen_addresses = '*'
password_encryption = 'scram-sha-256'
EOF
  cat >"$PGDATA/pg_hba.conf" <<'EOF'
local all all trust
host all all 127.0.0.1/32 trust
host all all ::1/128 trust
host all all 10.77.60.0/24 scram-sha-256
EOF
fi

gosu postgres pg_ctl -D "$PGDATA" -w start >/dev/null
if ! gosu postgres psql -Atqc "SELECT 1 FROM pg_roles WHERE rolname='svc-planner-query'" | grep -qx 1; then
  gosu postgres psql -v ON_ERROR_STOP=1 <<'SQL' >/dev/null
CREATE ROLE "svc-planner-query" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE DATABASE arwc;
SQL
fi

gosu postgres psql -d arwc -v ON_ERROR_STOP=1 <<'SQL' >/dev/null
CREATE TABLE IF NOT EXISTS reserve_report_current (
  record_id text PRIMARY KEY,
  district text NOT NULL,
  period text NOT NULL,
  amount_ml numeric(5,2) NOT NULL,
  detail text NOT NULL
);
INSERT INTO reserve_report_current VALUES
  ('RPT-CRR-RESERVE-R7','Cairn Reach','ALLOC-2026-DP3',13.40,'ordinary planner reserve report')
ON CONFLICT (record_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS district_allocation_adjustment (
  record_id text PRIMARY KEY,
  district text NOT NULL,
  period text NOT NULL,
  amount_ml numeric(5,2) NOT NULL,
  detail text NOT NULL
);
INSERT INTO district_allocation_adjustment VALUES
  ('ADJ-CRR-DP3-17','Cairn Reach','ALLOC-2026-DP3',-1.00,'duplicate transfer TRN-DP3-118')
ON CONFLICT (record_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS reconciliation_copy (
  record_id text PRIMARY KEY,
  revision integer NOT NULL,
  source_record text NOT NULL,
  database_identity text NOT NULL
);

CREATE OR REPLACE FUNCTION arwc_reconcile_copy(requested text)
RETURNS TABLE(record_id text, revision integer, source_record text, database_identity text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF requested <> 'REC-CRR-DP3-17' THEN
    RAISE EXCEPTION 'reconciliation record is not available';
  END IF;
  INSERT INTO reconciliation_copy VALUES
    ('REC-CRR-DP3-17-COPY',1,'REC-CRR-DP3-17','svc-planner-query')
  ON CONFLICT ON CONSTRAINT reconciliation_copy_pkey DO NOTHING;
  RETURN QUERY
    SELECT r.record_id, r.revision, r.source_record, r.database_identity
    FROM reconciliation_copy AS r WHERE r.record_id='REC-CRR-DP3-17-COPY';
END;
$$;

REVOKE ALL ON reserve_report_current, district_allocation_adjustment, reconciliation_copy FROM PUBLIC;
GRANT SELECT ON reserve_report_current, district_allocation_adjustment TO "svc-planner-query";
REVOKE ALL ON FUNCTION arwc_reconcile_copy(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION arwc_reconcile_copy(text) TO "svc-planner-query";
SQL

exec setpriv --reuid=arwc-data --regid=arwc-data --init-groups \
  python3 /opt/planning-data/planning_data.py
