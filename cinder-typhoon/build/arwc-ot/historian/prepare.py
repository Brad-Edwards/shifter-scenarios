"""Configure the native collector, fixed PostgreSQL schema, and product roles."""
import hashlib
import json
import pathlib
import secrets
import sys

import psycopg
from psycopg import sql
import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from configure_fuxa import URL, session_for_fuxa
from prepare_services import write

ROOT = pathlib.Path("/slice")
HERE = ROOT / "historian"


def collector_config(register):
    contract = json.loads((HERE / "contract.json").read_text())
    common = '''  endpoint = "opc.tcp://plc:4840/arwc"
  security_policy = "Basic256Sha256"
  security_mode = "SignAndEncrypt"
  auth_method = "UserName"
  username = "reader"
  password = "${UA_PASSWORD}"
  remote_certificate = "/run/pki/server-cert.pem"
  certificate = "/run/pki/telegraf-cert.pem"
  private_key = "/run/pki/telegraf-key.pem"
  timestamp = "source"
'''
    text = '''[agent]
  interval = "1s"
  flush_interval = "1s"
  precision = "1us"
  metric_buffer_limit = 10000
  omit_hostname = true
[[outputs.postgresql]]
  connection = "host=postgres user=collector password=${PG_PASSWORD} dbname=historian sslmode=disable"
  schema = "ot_history"
  timestamp_column_type = "timestamp with time zone"
  tags_as_jsonb = true
  fields_as_jsonb = true
  create_templates = []
  add_column_templates = []
[[processors.starlark]]
  source = \'\'\'
def apply(metric):
    metric.fields["collected_at_ns"] = Metric("collection_clock").time
    # PostgreSQL JSONB does not accept IEEE 754 NaN; replace with 0.0 so the
    # row is stored rather than the whole batch being dropped.
    # Starlark type() returns a string ("float"), not the Python type object.
    for key in list(metric.fields):
        v = metric.fields[key]
        if type(v) == "float" and str(v) in ("nan", "NaN", "inf", "-inf"):
            metric.fields[key] = 0.0
    if metric.name == "command_signals":
        key = metric.tags["variable"]
        value = metric.fields.get("value")
        if key in state and state[key] == value:
            return None
        metric.fields["observation"] = "transition" if key in state else "baseline"
        state[key] = value
    return metric
\'\'\'
[[inputs.opcua]]
''' + common
    for tag in register["tags"]:
        text += f'''[[inputs.opcua.group]]
  name = "process_samples"
  namespace_uri = {json.dumps(register['namespace_uri'])}
  identifier_type = "s"
  default_tags = {{asset={json.dumps(register['asset'])}, unit={json.dumps(tag['unit'])}, variable={json.dumps(tag['variable'])}, series={json.dumps(tag['table'])}}}
  [[inputs.opcua.group.nodes]]
    name = "value"
    identifier = "CRR.{tag['variable']}"
'''
    text += "[[inputs.opcua_listener]]\n" + common + '''  connect_fail_behavior = "retry"
  subscription_interval = "100ms"
'''
    for variable, event in contract["command_signals"].items():
        text += f'''[[inputs.opcua_listener.group]]
  name = "command_signals"
  namespace_uri = {json.dumps(register['namespace_uri'])}
  identifier_type = "s"
  default_tags = {{asset={json.dumps(register['asset'])}, variable={json.dumps(variable)}, channel={json.dumps(event['channel'])}, decision={json.dumps(event['decision'])}}}
  [[inputs.opcua_listener.group.nodes]]
    name = "value"
    identifier = "CRR.{variable}"
    [inputs.opcua_listener.group.nodes.monitoring_params]
      sampling_interval = "100ms"
      queue_size = 256
      discard_oldest = true
      [inputs.opcua_listener.group.nodes.monitoring_params.data_change_filter]
        trigger = "StatusValue"
        deadband_type = "None"
'''
    return text


def main():
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
    config_path = ROOT / ".operator/history-credentials.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    for key in ("history_maintenance", "event_exporter", "dmz_reader", "fuxa_history", "grafana_viewer"):
        config.setdefault(key, secrets.token_urlsafe(24))
    write(config_path, json.dumps(config, indent=2) + "\n")
    register_file = ROOT / "site/tags.json"
    register = json.loads(register_file.read_text())
    digest = hashlib.sha256(register_file.read_bytes()).hexdigest()
    with psycopg.connect(host="postgres", dbname="historian", user="historian", password=credentials["postgres"], autocommit=True) as db:
        for role in ("history_maintenance", "event_exporter", "dmz_reader"):
            if not db.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                db.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(config[role])))
        db.execute("CREATE SCHEMA IF NOT EXISTS ot_history AUTHORIZATION history_maintenance")
        # Preserve fixture records while removing its collector's old DDL rights.
        db.execute("REASSIGN OWNED BY collector TO history_maintenance")
        db.execute("REVOKE CREATE ON SCHEMA public FROM collector")
        db.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM collector")
        db.execute("GRANT USAGE ON SCHEMA ot_history TO collector, event_exporter")
        for table in ("process_samples", "command_signals"):
            db.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS ot_history.{} (
                time timestamptz NOT NULL, tags jsonb NOT NULL, fields jsonb NOT NULL,
                ingested_at timestamptz NOT NULL DEFAULT clock_timestamp()
                ) PARTITION BY RANGE (ingested_at)''').format(sql.Identifier(table)))
            db.execute(sql.SQL("ALTER TABLE ot_history.{} OWNER TO history_maintenance").format(sql.Identifier(table)))
            db.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {} ON ot_history.{} ((tags->>'variable'), time)").format(sql.Identifier(table + "_variable_time"), sql.Identifier(table)))
            if table == "process_samples":
                db.execute("CREATE INDEX IF NOT EXISTS process_samples_series_time ON ot_history.process_samples ((tags->>'series'), time)")
            db.execute(sql.SQL("GRANT INSERT ON ot_history.{} TO collector").format(sql.Identifier(table)))
        db.execute('''CREATE TABLE IF NOT EXISTS ot_history.tag_catalog (
            variable text PRIMARY KEY, series text UNIQUE NOT NULL, node_id text NOT NULL,
            unit text NOT NULL, register_sha256 text NOT NULL, definition jsonb NOT NULL, scaling jsonb NOT NULL)''')
        for tag in register["tags"]:
            db.execute('''INSERT INTO ot_history.tag_catalog VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (variable) DO UPDATE SET series=EXCLUDED.series,node_id=EXCLUDED.node_id,
                unit=EXCLUDED.unit,register_sha256=EXCLUDED.register_sha256,definition=EXCLUDED.definition,scaling=EXCLUDED.scaling''',
                (tag["variable"], tag["table"], f"nsu={register['namespace_uri']};s=CRR.{tag['variable']}", tag["unit"], digest,
                 psycopg.types.json.Jsonb(tag), psycopg.types.json.Jsonb(register["modbus"])))
        db.execute('''CREATE TABLE IF NOT EXISTS ot_history.alarm_events (
            name text NOT NULL, type text NOT NULL, ontime timestamptz NOT NULL, offtime timestamptz,
            acktime timestamptz, acknowledging_user text, text text, alarm_group text, value text,
            native_status text, origin text NOT NULL DEFAULT 'FUXA native alarm engine',
            observed_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY(name,type,ontime))''')
        db.execute("ALTER TABLE ot_history.alarm_events OWNER TO history_maintenance")
        db.execute("GRANT SELECT,INSERT,UPDATE ON ot_history.alarm_events TO event_exporter")
        try:
            db.execute((HERE / "views.sql").read_text())
        except Exception as e:
            # views.sql may fail if finalize_history.py already created a
            # public.process_history view with different columns (the two are
            # incompatible). The historian's own views (ot_history.*) are what
            # the collector and challenge cards use; skip the public wrapper
            # rather than aborting the entire setup.
            print(f"Warning: views.sql failed ({e}); continuing without public wrapper views.")
        # Fixed database guard, independent of the maintenance process being alive.
        limit = json.loads((HERE / "contract.json").read_text())["retention"]["database_high_bytes"]
        db.execute(sql.SQL('''CREATE OR REPLACE FUNCTION ot_history.check_capacity() RETURNS trigger
            LANGUAGE plpgsql AS $body$ BEGIN
              IF pg_database_size(current_database()) >= {} THEN
                RAISE EXCEPTION 'Historian storage threshold reached; inspect retention and capacity' USING ERRCODE='53100';
              END IF; RETURN NULL; END $body$''').format(sql.Literal(limit)))
        for table in ("process_samples", "command_signals", "alarm_events"):
            db.execute(sql.SQL("DROP TRIGGER IF EXISTS capacity_guard ON ot_history.{}").format(sql.Identifier(table)))
            db.execute(sql.SQL("CREATE TRIGGER capacity_guard BEFORE INSERT ON ot_history.{} FOR EACH STATEMENT EXECUTE FUNCTION ot_history.check_capacity()").format(sql.Identifier(table)))
    write(ROOT / ".operator/telegraf.conf", collector_config(register))
    write(ROOT / ".operator/history-maint.env", "PGUSER=history_maintenance\nPGPASSWORD=" + config["history_maintenance"] + "\n")
    write(ROOT / ".operator/history-export.env", "PGUSER=event_exporter\nPGPASSWORD=" + config["event_exporter"] + "\nFUXA_PASSWORD=" + config["fuxa_history"] + "\n")
    session = session_for_fuxa()
    session.post(URL + "/api/users", json={"params": {"username": "history-export", "fullname": "Read-only alarm history export",
        "password": config["fuxa_history"], "groups": 1, "info": "{}"}}, timeout=15).raise_for_status()
    from dashboard import dashboard
    write(ROOT / ".operator/grafana/boards/history.json", json.dumps(dashboard(), indent=2) + "\n", 0o644)
    grafana = requests.Session()
    grafana.auth = ("admin", credentials["grafana"])
    response = grafana.get("http://grafana:3000/api/users/lookup", params={"loginOrEmail": "history"}, timeout=10)
    if response.status_code == 404:
        response = grafana.post("http://grafana:3000/api/admin/users", json={"name": "ARWC history reader", "login": "history", "password": config["grafana_viewer"]}, timeout=10)
    response.raise_for_status()
    print("Configured native 50-tag acquisition and separate historian product roles.")


if __name__ == "__main__":
    main()
