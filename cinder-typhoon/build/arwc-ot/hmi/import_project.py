"""Import the authored HMI through native FUXA APIs on the development VM."""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from build_project import build_project
from configure_fuxa import URL, session_for_fuxa
from project_config import operator_credentials, write_json
from qualify_opcua import connect

ROOT = pathlib.Path("/slice")


async def main():
    credentials = operator_credentials(ROOT)
    register = json.loads((ROOT / "site/tags.json").read_text())
    client = await connect("reader")
    try:
        namespace = await client.get_namespace_index(register["namespace_uri"])
    finally:
        await client.disconnect()
    session = session_for_fuxa()
    response = session.get(URL + "/api/project", timeout=15)
    response.raise_for_status()
    project = build_project(response.json(), namespace)
    session.post(URL + "/api/project", json=project, timeout=30).raise_for_status()
    session.post(URL + "/api/device", json={"params": {"query": "security", "name": "crr-plc", "value": {
        "mode": {"securityMode": 3, "securityPolicy": "http://opcfoundation.org/UA/SecurityPolicy#Basic256Sha256"},
        "uid": "operator", "pwd": credentials["opcua"],
    }}}, timeout=15).raise_for_status()
    for username, key, fullname, group in [
        ("admin", "fuxa", "ARWC configuration administrator", -1),
        ("operator", "fuxa_operator", "ARWC site operator", 2),
        ("viewer", "fuxa_viewer", "ARWC observation", 1),
    ]:
        session.post(URL + "/api/users", json={"params": {"username": username, "fullname": fullname,
            "password": credentials[key], "groups": group, "info": "{}"}}, timeout=15).raise_for_status()
    settings = ROOT / ".operator/fuxa-settings.js"
    settings.write_text("module.exports = {...require('../settings.default.js'), secureEnabled: true, userRole: false, secretCode: "
                        + json.dumps(credentials["fuxa_session"]) + ", tokenExpiresIn: '1h'};\n")
    settings.chmod(0o644)
    write_json(ROOT / ".operator/hmi-project.json", project)
    print("Imported four native FUXA views, 50 tags, four alarms, and separate operator/viewer accounts.")


if __name__ == "__main__":
    asyncio.run(main())
