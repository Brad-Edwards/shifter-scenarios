"""Generate a local-only Editor project from its standard New Project scaffold."""
import json
import os
import pathlib
import secrets
import shutil
import sys
import socket

ROOT = pathlib.Path(__file__).resolve().parent


def write_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    if socket.gethostname() != "cinder-arwc-ot-compat-363":
        raise RuntimeError("Run configuration on the dedicated compatibility VM")
    os.umask(0o077)
    project = pathlib.Path(sys.argv[1]).resolve()
    metadata = json.loads((project / "project.json").read_text())
    if metadata["meta"]["name"] != "arwc-compat":
        raise ValueError("Expected the dedicated arwc-compat Editor project")
    operator = ROOT / ".operator"
    operator.mkdir(mode=0o700, exist_ok=True)
    credentials_path = operator / "credentials.json"
    if not credentials_path.exists():
        write_json(credentials_path, {key: secrets.token_urlsafe(24) for key in ("plc", "opcua", "postgres", "mqtt")})
    credentials = json.loads(credentials_path.read_text())
    for key in ("ua_dispatcher", "ua_reader", "collector", "reader", "pg_dispatcher", "mqtt_dispatcher", "grafana", "fuxa", "fuxa_session"):
        credentials.setdefault(key, secrets.token_urlsafe(24))
    write_json(credentials_path, credentials)
    settings = operator / "fuxa-settings.js"
    if not settings.exists():
        settings.write_text("module.exports = {...require('../settings.default.js'), secureEnabled: false};\n")
        settings.chmod(0o644)
    for name in ("telegraf.env", "grafana.env"):
        path = operator / name
        if not path.exists():
            path.touch(mode=0o600)
    (operator / "postgres_password").write_text(credentials["postgres"], encoding="utf-8")
    shutil.copyfile(ROOT / "main.st", project / "pous/programs/main.st")
    configuration_path = project / "devices/configuration.json"
    configuration = json.loads(configuration_path.read_text())
    configuration.update(deviceBoard="OpenPLC Runtime v4", runtimeIpAddress="172.29.63.20")
    configuration["persistentStorage"] = {"enabled": True, "path": "/var/run/runtime/retain.bin", "flushSeconds": 1}
    write_json(configuration_path, configuration)

    register = json.loads((ROOT / "tags.json").read_text())
    variables = {tag["variable"]: (tag["type"], tag["write"]) for tag in register["tags"]}
    nodes = [{
        "id": name, "pouName": "main", "variablePath": name, "variableType": datatype,
        "nodeId": "CRR." + name, "browseName": name, "displayName": name,
        "description": "Cairn Reach compatibility outlet " + name, "nodeType": "variable",
        "permissions": {"viewer": "r", "operator": "rw" if writable and name.startswith("Hmi") else "r",
                        "engineer": "rw" if writable and name.startswith("Remote") else "r"},
    } for name, (datatype, writable) in variables.items()]
    server = {
        "name": "CairnReachUA", "protocol": "opcua", "opcuaServerConfig": {
            "server": {"enabled": True, "name": "Cairn Reach site controller", "applicationUri": "urn:arwc:crr:plc",
                       "productUri": "urn:arwc:ot-compat", "bindAddress": "0.0.0.0", "port": 4840, "endpointPath": "/arwc"},
            "securityProfiles": [{"id": "secure", "name": "Signed and encrypted", "enabled": True,
                                  "securityPolicy": "Basic256Sha256", "securityMode": "SignAndEncrypt", "authMethods": ["Username"]}],
            "security": {"serverCertificateStrategy": "auto_self_signed", "serverCertificateCustom": None,
                         "serverPrivateKeyCustom": None, "trustedClientCertificates": []},
            "users": [{"id": user, "type": "password", "username": user, "password": credentials[key],
                       "passwordHash": None, "certificateId": None, "role": role}
                      for user, key, role in (("operator", "opcua", "operator"), ("dispatcher", "ua_dispatcher", "engineer"),
                                              ("reader", "ua_reader", "viewer"))],
            "cycleTimeMs": 100, "addressSpace": {"namespaceUri": "urn:arwc:crr:tags", "nodes": nodes},
        },
    }
    write_json(project / "devices/servers/CairnReachUA.json", server)
    groups = []
    for name, fc, offset, locations in (
        ("Measurements", "4", 0, ["%IW0", "%IW1", "%IW2", "%IW3"]),
        ("Actuator", "16", 0, ["%QW0"]),
    ):
        groups.append({"id": name, "name": name, "functionCode": fc, "cycleTime": 100, "offset": str(offset),
                       "length": len(locations), "errorHandling": "keep-last-value",
                       "ioPoints": [{"id": name + str(i), "name": name + str(i), "type": "UINT", "iecLocation": loc}
                                    for i, loc in enumerate(locations)]})
    write_json(project / "devices/remote/CairnReachIO.json", {
        "name": "CairnReachIO", "protocol": "modbus-tcp", "modbusTcpConfig": {
            "transport": "tcp", "host": "172.29.64.30", "port": 502, "timeout": 1000, "slaveId": 1, "ioGroups": groups,
        },
    })
    print("Configured official Editor project; credentials remain on the test VM.")


if __name__ == "__main__":
    main()
