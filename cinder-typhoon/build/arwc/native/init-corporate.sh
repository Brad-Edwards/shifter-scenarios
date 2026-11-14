#!/bin/sh
set -eu
metabase_password=$(cat /run/secrets/metabase_db_password)
planning_password=$(cat /run/secrets/planning_reader_password)
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set ON_ERROR_STOP=1 --set metabase_password="$metabase_password" \
  --set planning_password="$planning_password" <<'SQL'
CREATE ROLE metabase LOGIN PASSWORD :'metabase_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE metabase OWNER metabase;
CREATE ROLE planning_reader LOGIN PASSWORD :'planning_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE planning TO planning_reader;
GRANT USAGE ON SCHEMA public TO planning_reader;
SQL
