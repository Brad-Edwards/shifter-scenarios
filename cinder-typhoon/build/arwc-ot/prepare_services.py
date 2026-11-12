"""Configure maintained collector, database, broker, and historical viewer."""
import json
import os
import pathlib
import shutil
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg import sql
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = pathlib.Path("/slice")
OPERATOR = ROOT / ".operator"


def write(path: pathlib.Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)


def certificates() -> None:
    broker = OPERATOR / "mosquitto"
    broker.mkdir(exist_ok=True)
    broker.chmod(0o755)
    if (broker / "server.pem").exists():
        return
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ARWC compatibility CA")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
          .not_valid_after(now + timedelta(days=30)).add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .sign(ca_key, hashes.SHA256()))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "mosquitto")]))
            .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=30))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("mosquitto")]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    write(broker / "ca.pem", ca.public_bytes(serialization.Encoding.PEM).decode(), 0o644)
    write(broker / "server.pem", cert.public_bytes(serialization.Encoding.PEM).decode(), 0o644)
    write(broker / "server-key.pem", key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(), 0o640)
    os.chown(broker / "server-key.pem", 1883, 1883)


def main() -> None:
    os.umask(0o077)
    credentials = json.loads((OPERATOR / "credentials.json").read_text())
    register = json.loads((ROOT / "tags.json").read_text())
    with psycopg.connect(host="postgres", dbname="historian", user="historian", password=credentials["postgres"], autocommit=True) as db:
        for user, key in (("collector", "collector"), ("reader", "reader"), ("dispatcher", "pg_dispatcher")):
            if not db.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (user,)).fetchone():
                db.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(user), sql.Literal(credentials[key])))
        db.execute("GRANT CREATE, USAGE ON SCHEMA public TO collector")
        db.execute("GRANT USAGE ON SCHEMA public TO reader")
        db.execute("ALTER DEFAULT PRIVILEGES FOR USER collector IN SCHEMA public GRANT SELECT ON TABLES TO reader")
        db.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO reader")
        db.execute("CREATE TABLE IF NOT EXISTS command_events (id uuid PRIMARY KEY, requested_at timestamptz NOT NULL DEFAULT now(), sequence integer NOT NULL, target_pct double precision NOT NULL, status text NOT NULL, principal text NOT NULL)")
        db.execute("GRANT SELECT, INSERT, UPDATE ON command_events TO dispatcher")
        db.execute("GRANT SELECT ON command_events TO reader")
        db.execute("CREATE TABLE IF NOT EXISTS command_transitions (command_id uuid REFERENCES command_events(id), time timestamptz NOT NULL DEFAULT clock_timestamp(), status text NOT NULL)")
        db.execute("GRANT INSERT ON command_transitions TO dispatcher")
        db.execute("GRANT SELECT ON command_transitions TO reader")

    pki = OPERATOR / "telegraf-pki"
    pki.mkdir(exist_ok=True)
    shutil.copyfile(OPERATOR / "server-cert.pem", pki / "server-cert.pem")

    collector = '''[agent]
  interval = "1s"
  flush_interval = "1s"
  omit_hostname = true
[[outputs.postgresql]]
  connection = "host=postgres user=collector password=${PG_PASSWORD} dbname=historian sslmode=disable"
[[inputs.opcua]]
  endpoint = "opc.tcp://plc:4840/arwc"
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
    for tag in register["tags"]:
        collector += f'''[[inputs.opcua.group]]
  name = "{tag['table']}"
  namespace_uri = "{register['namespace_uri']}"
  identifier_type = "s"
  default_tags = {{asset="{register['asset']}", unit="{tag['unit']}", tag="CRR.{tag['variable']}"}}
  [[inputs.opcua.group.nodes]]
    name = "value"
    identifier = "CRR.{tag['variable']}"
'''
    write(OPERATOR / "telegraf.conf", collector)
    write(OPERATOR / "telegraf.env", f"PG_PASSWORD={credentials['collector']}\nUA_PASSWORD={credentials['ua_reader']}\n")

    certificates()
    broker = OPERATOR / "mosquitto"
    if not (broker / "passwords").exists():
        write(broker / "passwords", f"operator:{credentials['mqtt']}\ndispatcher:{credentials['mqtt_dispatcher']}\n", 0o640)
        os.chown(broker / "passwords", 1883, 1883)
    write(broker / "mosquitto.conf", """listener 8883
allow_anonymous false
password_file /mosquitto/config/passwords
acl_file /mosquitto/config/acl
cafile /mosquitto/config/ca.pem
certfile /mosquitto/config/server.pem
keyfile /mosquitto/config/server-key.pem
persistence true
persistence_location /mosquitto/data/
log_dest stdout
""", 0o644)
    write(broker / "acl", """user operator
topic write arwc/crr/commands/operator
topic read arwc/crr/outcomes/operator
user dispatcher
topic read arwc/crr/commands/operator
topic write arwc/crr/outcomes/operator
""", 0o644)

    provisioning = OPERATOR / "grafana"
    datasource = {"apiVersion": 1, "datasources": [{"name": "ARWC PostgreSQL historian", "uid": "arwc-postgres", "type": "postgres",
        "url": "postgres:5432", "user": "reader", "access": "proxy", "isDefault": True,
        "jsonData": {"database": "historian", "sslmode": "disable", "postgresVersion": 1800},
        "secureJsonData": {"password": "$PG_READER_PASSWORD"}}]}
    write(provisioning / "datasources/historian.yaml", json.dumps(datasource), 0o644)
    write(provisioning / "dashboards/provider.yaml", json.dumps({"apiVersion": 1, "providers": [{"name": "ARWC", "type": "file", "options": {"path": "/etc/grafana/provisioning/boards"}}]}), 0o644)
    panels = []
    for index, (table, title, unit) in enumerate((("level_m", "Reservoir level", "lengthm"), ("position_pct", "Outlet position", "percent"), ("flow_m3s", "Measured outlet flow", "flowcms"))):
        panels.append({"id": index + 1, "type": "timeseries", "title": title, "gridPos": {"x": index*8, "y": 0, "w": 8, "h": 10},
                       "datasource": {"type": "postgres", "uid": "arwc-postgres"},
                       "targets": [{"refId": "A", "format": "time_series", "rawSql": f"SELECT source_time AS time, CASE WHEN process_quality='Good' THEN value ELSE NULL END AS value FROM process_history WHERE tag='{table}' AND $__timeFilter(source_time) ORDER BY source_time"}],
                       "fieldConfig": {"defaults": {"unit": unit, "custom": {"spanNulls": False}}, "overrides": []}})
    dashboard = {"uid": "arwc-history", "title": "Cairn Reach process history", "schemaVersion": 41, "version": 1,
                 "time": {"from": "now-15m", "to": "now"}, "refresh": "5s", "panels": panels}
    write(provisioning / "boards/history.json", json.dumps(dashboard), 0o644)
    for directory in provisioning.rglob("*"):
        if directory.is_dir():
            directory.chmod(0o755)
    provisioning.chmod(0o755)
    write(OPERATOR / "grafana.env", f"GF_SECURITY_ADMIN_PASSWORD={credentials['grafana']}\nPG_READER_PASSWORD={credentials['reader']}\n")
    print("Configured collector, PostgreSQL roles, MQTT broker, and PostgreSQL historical panels.")


if __name__ == "__main__":
    main()
