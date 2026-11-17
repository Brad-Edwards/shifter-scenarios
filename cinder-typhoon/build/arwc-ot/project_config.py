"""Shared product configuration for the compatibility and site Editor projects."""
import json
import pathlib
import secrets


def write_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def operator_credentials(root: pathlib.Path) -> dict:
    operator = root / ".operator"
    operator.mkdir(mode=0o700, exist_ok=True)
    operator.chmod(0o700)
    path = operator / "credentials.json"
    credentials = json.loads(path.read_text()) if path.exists() else {}
    for key in ("plc", "opcua", "postgres", "mqtt", "ua_dispatcher", "ua_reader", "collector", "reader", "pg_dispatcher", "mqtt_dispatcher", "grafana", "fuxa", "fuxa_session", "fuxa_operator", "fuxa_viewer"):
        credentials.setdefault(key, secrets.token_urlsafe(24))
    write_json(path, credentials)
    path.chmod(0o600)
    settings = operator / "fuxa-settings.js"
    if not settings.exists():
        settings.write_text("module.exports = {...require('../settings.default.js'), secureEnabled: false};\n")
        settings.chmod(0o644)
    for name in ("telegraf.env", "grafana.env"):
        path = operator / name
        if not path.exists():
            path.touch(mode=0o600)
    (operator / "postgres_password").write_text(credentials["postgres"], encoding="utf-8")
    return credentials


def opcua_server(register: dict, credentials: dict) -> dict:
    nodes = [{
        "id": tag["variable"], "pouName": "main", "variablePath": tag["variable"], "variableType": tag["type"],
        "nodeId": "CRR." + tag["variable"], "browseName": tag["variable"], "displayName": tag["variable"],
        "description": tag.get("description", "Cairn Reach " + tag["variable"]), "nodeType": "variable",
        "permissions": {"viewer": "r", "operator": "rw" if tag["write"] and tag["variable"].startswith("Hmi") else "r",
                        "engineer": "rw" if tag["write"] and tag["variable"].startswith("Remote") else "r"},
    } for tag in register["tags"]]
    return {
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
            "cycleTimeMs": 100, "addressSpace": {"namespaceUri": register["namespace_uri"], "nodes": nodes},
        },
    }
