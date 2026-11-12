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


async def main() -> None:
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
    register = json.loads((ROOT / "tags.json").read_text())
    client = await connect("reader")
    try:
        namespace = await client.get_namespace_index(register["namespace_uri"])
    finally:
        await client.disconnect()
    session = session_for_fuxa(bootstrap=True)
    project = session.get(URL + "/api/project", timeout=15).json()
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
    session.post(URL + "/api/users", json={"params": {"username": "admin", "fullname": "ARWC compatibility operator", "password": credentials["fuxa"], "groups": -1, "info": "{}"}}, timeout=15).raise_for_status()
    settings = ROOT / ".operator/fuxa-settings.js"
    settings.write_text("module.exports = {...require('../settings.default.js'), secureEnabled: true, secretCode: " + json.dumps(credentials["fuxa_session"]) + ", tokenExpiresIn: '1h'};\n")
    settings.chmod(0o644)
    print("FUXA imported the real native OPC UA namespace and encrypted operator connection.")


if __name__ == "__main__":
    asyncio.run(main())
