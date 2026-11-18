#!/bin/sh
set -eu
umask 077

chown arwc-data:arwc-data /var/lib/arwc-data
chmod 0700 /var/lib/arwc-data
install -d -o arwc-data -g arwc-data -m 0700 \
  /var/lib/arwc-data/audit \
  /var/lib/arwc-data/auth \
  /var/lib/arwc-data/state \
  /var/lib/arwc-data/results
install -d -o arwc-data -g arwc-integration -m 0750 \
  /var/lib/arwc-data/integration
install -d -o arwc-data -g arwc-archive-source -m 0750 \
  /var/lib/arwc-data/archive

python3 /usr/local/libexec/arwc-handover.py wait \
  --service arwc-data \
  --accepted-hash /var/lib/arwc-data/auth/corporate-session.sha256
chown arwc-data:arwc-data /var/lib/arwc-data/auth/corporate-session.sha256
chmod 0400 /var/lib/arwc-data/auth/corporate-session.sha256

for file in server.crt server.key; do
  install -o arwc-data -g arwc-data -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

# W09.4: the OT-site overlay mounts the operating-reader Basic identity at
# /run/arwc-operating-reader.json (root 0600). Copy it to an arwc-data-readable
# path so the integration session can hand those credentials to the participant.
if [ -r /run/arwc-operating-reader.json ]; then
  install -o arwc-data -g arwc-data -m 0400 \
    /run/arwc-operating-reader.json /tmp/arwc-operating-reader.json
fi

install -d -o postgres -g postgres -m 0700 "$PGDATA"
install -d -o postgres -g postgres -m 2775 /var/run/postgresql
chown postgres:postgres /var/run/postgresql
chmod 2775 /var/run/postgresql
if [ ! -s "$PGDATA/PG_VERSION" ]; then
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
# W23.2: write role for the controlled-allocation endpoint (UPDATE on allocation_ledger only).
if ! gosu postgres psql -Atqc "SELECT 1 FROM pg_roles WHERE rolname='svc-planner-write'" | grep -qx 1; then
  gosu postgres psql -d arwc -v ON_ERROR_STOP=1 <<'SQL' >/dev/null
CREATE ROLE "svc-planner-write" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
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

-- reconciliation_copy and arwc_reconcile_copy removed from embedded Postgres:
-- W07.3 uses the real SECURITY DEFINER function and table in corporate-db instead.
-- The only valid invocation is via the native Metabase /api/dataset injection.

CREATE TABLE IF NOT EXISTS allocation_ledger (
  record_id text PRIMARY KEY,
  revision integer NOT NULL,
  district text NOT NULL,
  asset text NOT NULL,
  planning_window text NOT NULL,
  committed_ml numeric(5,2) NOT NULL,
  unit text NOT NULL,
  effective_from timestamptz NOT NULL,
  effective_to timestamptz NOT NULL
);
ALTER TABLE allocation_ledger ADD COLUMN IF NOT EXISTS effective_from timestamptz;
ALTER TABLE allocation_ledger ADD COLUMN IF NOT EXISTS effective_to timestamptz;
INSERT INTO allocation_ledger
  (record_id,revision,district,asset,planning_window,committed_ml,unit,effective_from,effective_to)
VALUES
  ('ALLOC-2026-DP3-R9',9,'Cairn Reach','AST-CRR-017','ALLOC-2026-DP3',12.00,'ML',
   '2026-11-01T00:00:00Z','2026-12-01T00:00:00Z')
ON CONFLICT (record_id) DO UPDATE SET
  effective_from=EXCLUDED.effective_from,effective_to=EXCLUDED.effective_to;
ALTER TABLE allocation_ledger ALTER COLUMN effective_from SET NOT NULL;
ALTER TABLE allocation_ledger ALTER COLUMN effective_to SET NOT NULL;

CREATE TABLE IF NOT EXISTS settlement_tariff (
  record_id text PRIMARY KEY,
  revision integer NOT NULL,
  planning_window text NOT NULL,
  asset text NOT NULL,
  currency text NOT NULL,
  rate_per_ml numeric(9,2) NOT NULL,
  unit text NOT NULL,
  effective_from timestamptz NOT NULL,
  effective_to timestamptz NOT NULL
);
INSERT INTO settlement_tariff VALUES
  ('TAR-CRR-DP3-R4',4,'ALLOC-2026-DP3','AST-CRR-017','USD',2400.00,'USD/ML',
   '2026-11-01T00:00:00Z','2026-12-01T00:00:00Z')
ON CONFLICT (record_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS meter_export (
  record_id text PRIMARY KEY,
  revision integer NOT NULL,
  planning_window text NOT NULL,
  usable_reserve_ml numeric(5,2) NOT NULL,
  unit text NOT NULL,
  instrument_a text NOT NULL,
  instrument_b text NOT NULL
);
INSERT INTO meter_export VALUES
  ('MTR-CRR-DP3-R12',12,'ALLOC-2026-DP3',12.40,'ML','FIT-CRR-204A','FIT-CRR-204B')
ON CONFLICT (record_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS business_reserve_report (
  record_id text PRIMARY KEY,
  revision integer NOT NULL,
  planning_window text NOT NULL,
  reported_ml numeric(5,2) NOT NULL,
  duplicate_transfer text NOT NULL,
  asset text NOT NULL,
  unit text NOT NULL,
  as_of timestamptz NOT NULL
);
ALTER TABLE business_reserve_report ADD COLUMN IF NOT EXISTS asset text;
ALTER TABLE business_reserve_report ADD COLUMN IF NOT EXISTS unit text;
ALTER TABLE business_reserve_report ADD COLUMN IF NOT EXISTS as_of timestamptz;
INSERT INTO business_reserve_report
  (record_id,revision,planning_window,reported_ml,duplicate_transfer,asset,unit,as_of)
VALUES
  ('RPT-CRR-DP3-R7',7,'ALLOC-2026-DP3',13.40,'TRN-DP3-118','AST-CRR-017','ML',
   '2026-11-09T00:00:00Z')
ON CONFLICT (record_id) DO UPDATE SET
  asset=EXCLUDED.asset,unit=EXCLUDED.unit,as_of=EXCLUDED.as_of;
ALTER TABLE business_reserve_report ALTER COLUMN asset SET NOT NULL;
ALTER TABLE business_reserve_report ALTER COLUMN unit SET NOT NULL;
ALTER TABLE business_reserve_report ALTER COLUMN as_of SET NOT NULL;

REVOKE ALL ON reserve_report_current, district_allocation_adjustment,
  allocation_ledger, settlement_tariff, meter_export, business_reserve_report FROM PUBLIC;
GRANT SELECT ON reserve_report_current, district_allocation_adjustment,
  allocation_ledger, settlement_tariff, meter_export, business_reserve_report TO "svc-planner-query";
GRANT UPDATE (committed_ml, revision) ON public.allocation_ledger TO "svc-planner-write";
SQL

exec setpriv --reuid=arwc-data --regid=arwc-data --init-groups \
  python3 /opt/planning-data/planning_data.py
