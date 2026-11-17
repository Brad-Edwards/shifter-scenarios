"""Seed development-only desktop access and current native project data."""
import json
import pathlib
import secrets
import socket
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".operator"
CONTAINER = "cinder-arwc-ot-engineering"


def docker(*args, input=None):
    return subprocess.run(["sudo", "docker", *args], input=input, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def copy(path, destination):
    docker("cp", str(path), CONTAINER + ":" + destination)


def seed_connections(project=None):
    """Deliver product connections without changing BigRAE's participant password."""
    credentials = json.loads((PRIVATE / "credentials.json").read_text())
    history_path = PRIVATE / "history-credentials.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else {}
    docker("exec", CONTAINER, "install", "-d", "-o", "2500", "-g", "2500", "-m", "0700", "/home/fieldlink/CairnReach/Connections")
    if project is None:
        project = pathlib.Path("/opt/arwc-ot-compat/work/arwc-site")
        if not project.exists():
            project = pathlib.Path("/opt/arwc-ot-compat/work/arwc-compat")
    exists = subprocess.run(["sudo", "docker", "exec", CONTAINER, "test", "-f", "/home/fieldlink/CairnReach/controller/project.json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if exists.returncode:
        copy(project, "/home/fieldlink/CairnReach/controller")
    notes = PRIVATE / "workstation-connections.md"
    text = "# Current Cairn Reach role connections\n\nKeep this file private to the engineering desk.\n\n"
    for label, endpoint, username, password in [
        ("FUXA operation", "http://fuxa:1881", "operator" if "fuxa_operator" in credentials else "admin", credentials.get("fuxa_operator", credentials["fuxa"])),
        ("PLC engineering", "https://plc:8443", "engineer", credentials["plc"]),
        ("OPC UA reader", "opc.tcp://plc:4840/arwc", "reader", credentials["ua_reader"]),
        ("PostgreSQL history", "postgres:5432 / historian", "reader", credentials["reader"]),
        ("MQTT operator", "mosquitto:8883", "operator", credentials["mqtt"]),
    ]:
        text += f"## {label}\n\nEndpoint: `{endpoint}`\n\nUser: `{username}`\n\nPassword: `{password}`\n\n"
    if history.get("grafana_viewer"):
        text += "## Grafana history\n\nUser: `history`\n\nPassword: `" + history["grafana_viewer"] + "`\n\n"
    else:
        text += "## Grafana compatibility fixture\n\nUser: `admin`\n\nPassword: `" + credentials["grafana"] + "`\n\n"
    notes.write_text(text)
    notes.chmod(0o600)
    copy(notes, "/home/fieldlink/CairnReach/Connections/README.md")
    operating = PRIVATE / "integration-bridge/operating-reader.json"
    operating_client = "/home/fieldlink/CairnReach/Connections/operating-history.json"
    missing_client = subprocess.run(["sudo", "docker", "exec", CONTAINER, "test", "-e", operating_client],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0
    if operating.exists() and missing_client:
        client = json.loads(operating.read_text())
        client["endpoint"] = "https://read-data.arwc.test/api/operating-history"
        material = PRIVATE / "workstation-operating-history.json"
        material.write_text(json.dumps(client) + "\n")
        material.chmod(0o600)
        copy(material, "/home/fieldlink/CairnReach/Connections/operating-history.json")
    copy(PRIVATE / "server-cert.pem", "/home/fieldlink/CairnReach/Connections/plc-server-cert.pem")
    copy(PRIVATE / "mosquitto/ca.pem", "/home/fieldlink/CairnReach/Connections/mqtt-ca.pem")
    service = PRIVATE / "workstation-pg-service.conf"
    service.write_text("[arwc-history]\nhost=postgres\nport=5432\ndbname=historian\nuser=reader\n")
    copy(service, "/home/fieldlink/.pg_service.conf")
    password = credentials["reader"].replace("\\", "\\\\").replace(":", "\\:")
    pgpass = PRIVATE / "workstation-pgpass"
    pgpass.write_text("postgres:5432:historian:reader:" + password + "\n")
    pgpass.chmod(0o600)
    copy(pgpass, "/home/fieldlink/.pgpass")
    docker("exec", CONTAINER, "chmod", "0600", "/home/fieldlink/.pgpass", "/home/fieldlink/CairnReach/Connections/README.md")
    docker("exec", CONTAINER, "chown", "-R", "2500:2500", "/home/fieldlink/CairnReach", "/home/fieldlink/.pgpass", "/home/fieldlink/.pg_service.conf")
    docker("exec", CONTAINER, "chmod", "0700", "/home/fieldlink", "/home/fieldlink/CairnReach")
    print("Delivered native role connections and the current project. Existing participant project edits and the participant password were preserved.")


def main():
    if socket.gethostname() != "cinder-arwc-ot-compat-363" or str(ROOT) != "/opt/arwc-ot-compat/slice":
        raise SystemExit("Use the dedicated persistent development VM")
    path = PRIVATE / "workstation-credentials.json"
    desktop = json.loads(path.read_text()) if path.exists() else {"username": "fieldlink", "password": secrets.token_urlsafe(24), "scope": "development only; final range uses BigRAE credentials"}
    path.write_text(json.dumps(desktop, indent=2)+"\n")
    path.chmod(0o600)
    docker("exec", "-i", CONTAINER, "chpasswd", input="fieldlink:" + desktop["password"] + "\n")
    seed_connections()


if __name__ == "__main__":
    main()
