"""Read back the imported native document and initial live device values."""
import datetime
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from build_project import HERE, validate_project
from configure_fuxa import URL, session_for_fuxa
from project_config import write_json


def main():
    model = json.loads((HERE / "views.json").read_text())
    register = json.loads((HERE / "../site/tags.json").read_text())
    session = session_for_fuxa()
    response = session.get(URL + "/api/project", timeout=15)
    response.raise_for_status()
    project = response.json()
    validate_project(project, model, register)
    names = ["LevelM", "PositionPct", "PositionBPct", "FlowM3s", "FlowBM3s", "IoHealthy", "ProjectRevision"]
    deadline = time.monotonic() + 45
    while True:
        response = session.get(URL + "/api/getTagValue", params={"ids": json.dumps(names)}, timeout=10)
        response.raise_for_status()
        values = {v["id"]: v for v in response.json()}
        if all(values.get(n, {}).get("value") is not None for n in names):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("FUXA did not acquire the live site measurements")
        time.sleep(1)
    if int(values["ProjectRevision"]["value"]) != 364 or not values["IoHealthy"]["value"]:
        raise RuntimeError("The live two-outlet site is not ready")
    report = {"issue": 365, "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "scope": "native import and initial live device values; browser QA pending",
              "views": [v["id"] for v in project["hmi"]["views"]],
              "tags": len(project["devices"]["crr-plc"]["tags"]), "alarms": len(project["alarms"]),
              "scripts": [s["id"] for s in project["scripts"]], "live_values": values}
    write_json(pathlib.Path("/slice/.operator/hmi-installation.json"), report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
