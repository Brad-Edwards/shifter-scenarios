"""Import real OPC UA device settings through FUXA's supported project API."""
import asyncio
import json
import pathlib
import time

import requests
from asyncua import ua
from qualify_opcua import connect

ROOT = pathlib.Path("/slice")
URL = "http://fuxa:1881"


def session_for_fuxa(bootstrap=False) -> requests.Session:
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
    session = requests.Session()
    deadline = time.monotonic() + 45
    while True:
        try:
            response = session.post(URL + "/api/signin", json={"username": "admin", "password": credentials["fuxa"]}, timeout=5)
            break
        except requests.ConnectionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    if response.ok:
        session.headers["x-access-token"] = response.json()["data"]["token"]
    elif not bootstrap:
        response.raise_for_status()
    return session


def _apply_users_and_settings(session: requests.Session, credentials: dict) -> None:
    """Create or update FUXA accounts and write settings. Safe to call on a live range."""
    for username, key, fullname, group in [
        ("admin", "fuxa", "ARWC compatibility operator", -1),
        ("operator", "fuxa_operator", "ARWC site operator", 2),
        ("viewer", "fuxa_viewer", "ARWC observation", 1),
    ]:
        session.post(URL + "/api/users", json={"params": {"username": username, "fullname": fullname,
            "password": credentials[key], "groups": group, "info": "{}"}}, timeout=15)
        # 200/201 = created; ignore errors for existing accounts (idempotent).
    settings = ROOT / ".operator/fuxa-settings.js"
    settings.write_text("module.exports = {...require('../settings.default.js'), secureEnabled: true, userRole: false, secretCode: " + json.dumps(credentials["fuxa_session"]) + ", tokenExpiresIn: '1h'};\n")
    settings.chmod(0o644)


async def main() -> None:
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
    session = session_for_fuxa(bootstrap=True)

    # Check whether the OPC UA project is already imported (device crr-plc with ≥1 tag).
    # If so, skip the destructive project re-import and only update accounts and settings.
    project = session.get(URL + "/api/project", timeout=15).json()
    existing_tags = len((project.get("devices") or {}).get("crr-plc", {}).get("tags") or {})
    if existing_tags > 0:
        print(f"FUXA project already configured ({existing_tags} tags). Skipping re-import.")
        _apply_users_and_settings(session, credentials)
        print("FUXA accounts and settings updated without touching the device project.")
        return

    # First-time setup: import the full OPC UA project.
    register = json.loads((ROOT / "tags.json").read_text())
    client = await connect("reader")
    try:
        namespace = await client.get_namespace_index(register["namespace_uri"])
    finally:
        await client.disconnect()
    tags = {}
    for tag in register["tags"]:
        name = tag["variable"]
        tags[name] = {"id": name, "name": name, "address": f"ns={namespace};s=CRR.{name}",
                      "type": {"REAL": "Float", "UINT": "UInt16", "BOOL": "Boolean"}[tag["type"]],
                      "daq": {"enabled": False}, "options": {}}
    project["devices"] = {"crr-plc": {"id": "crr-plc", "name": "Cairn Reach PLC", "type": "OPCUA",
                                       "enabled": True, "polling": 500, "property": {"address": "opc.tcp://plc:4840/arwc"}, "tags": tags}}
    session.post(URL + "/api/project", json=project, timeout=30).raise_for_status()
    # Import replaces the project database, including its device credential table.
    # Write credentials afterwards; the ordinary device reconnect picks them up.
    session.post(URL + "/api/device", json={"params": {"query": "security", "name": "crr-plc", "value": {
        "mode": {"securityMode": 3, "securityPolicy": "http://opcfoundation.org/UA/SecurityPolicy#Basic256Sha256"},
        "uid": "operator", "pwd": credentials["opcua"],
    }}}, timeout=15).raise_for_status()
    _apply_users_and_settings(session, credentials)
    print("FUXA imported the real native OPC UA namespace and encrypted operator connection.")


if __name__ == "__main__":
    asyncio.run(main())
