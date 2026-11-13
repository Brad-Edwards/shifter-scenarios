"""Generate a local-only Editor project from its standard New Project scaffold."""
import json
import os
import pathlib
import shutil
import sys
import socket
from project_config import operator_credentials, opcua_server, write_json

ROOT = pathlib.Path(__file__).resolve().parent


def main() -> None:
    if socket.gethostname() != "cinder-arwc-ot-compat-363":
        raise RuntimeError("Run configuration on the dedicated compatibility VM")
    os.umask(0o077)
    project = pathlib.Path(sys.argv[1]).resolve()
    metadata = json.loads((project / "project.json").read_text())
    if metadata["meta"]["name"] != "arwc-compat":
        raise ValueError("Expected the dedicated arwc-compat Editor project")
    credentials = operator_credentials(ROOT)
    shutil.copyfile(ROOT / "main.st", project / "pous/programs/main.st")
    configuration_path = project / "devices/configuration.json"
    configuration = json.loads(configuration_path.read_text())
    configuration.update(deviceBoard="OpenPLC Runtime v4", runtimeIpAddress="172.29.63.20")
    configuration["persistentStorage"] = {"enabled": True, "path": "/var/run/runtime/retain.bin", "flushSeconds": 1}
    write_json(configuration_path, configuration)

    register = json.loads((ROOT / "tags.json").read_text())
    write_json(project / "devices/servers/CairnReachUA.json", opcua_server(register, credentials))
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
