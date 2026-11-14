#!/bin/sh
set -eu
metabase_password=$(cat /run/secrets/metabase_db_password)
planning_password=$(cat /run/secrets/planning_reader_password)
postgrest_password=$(cat /run/secrets/postgrest_password)
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set ON_ERROR_STOP=1 --set metabase_password="$metabase_password" \
  --set planning_password="$planning_password" --set postgrest_password="$postgrest_password" <<'SQL'
SELECT format('CREATE ROLE metabase LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE', :'metabase_password')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metabase')
\gexec
SELECT 'CREATE DATABASE metabase OWNER metabase'
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'metabase')
\gexec
SELECT format('CREATE ROLE planning_reader LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE', :'planning_password')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'planning_reader')
\gexec
GRANT CONNECT ON DATABASE planning TO planning_reader;
GRANT USAGE ON SCHEMA public TO planning_reader;
SELECT 'CREATE ROLE dmz_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE'
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dmz_reader')
\gexec
SELECT format('CREATE ROLE pgrst_authenticator LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L', :'postgrest_password')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pgrst_authenticator')
\gexec
GRANT dmz_reader TO pgrst_authenticator;
ALTER ROLE pgrst_authenticator SET default_transaction_read_only = on;
SQL
