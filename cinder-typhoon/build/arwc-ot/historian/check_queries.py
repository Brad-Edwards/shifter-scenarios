"""Read the provisioned Grafana queries through its native PostgreSQL backend."""
import copy
import json
import pathlib
import time

import requests

ROOT = pathlib.Path("/slice")


def main():
    credentials = json.loads((ROOT / ".operator/history-credentials.json").read_text())
    session = requests.Session()
    session.auth = ("history", credentials["grafana_viewer"])
    response = session.get("http://grafana:3000/api/dashboards/uid/arwc-history", timeout=15)
    response.raise_for_status()
    dashboard = response.json()["dashboard"]
    results = []
    for panel in dashboard["panels"]:
        target = copy.deepcopy(panel["targets"][0])
        target.update(datasource={"type": "postgres", "uid": "arwc-postgres"}, intervalMs=1000, maxDataPoints=1000)
        response = session.post("http://grafana:3000/api/ds/query", json={"from": str(int((time.time()-900)*1000)), "to": str(int(time.time()*1000)), "queries": [target]}, timeout=30)
        response.raise_for_status()
        result = response.json()["results"]["A"]
        if result.get("error"):
            raise RuntimeError(panel["title"] + ": " + result["error"])
        frames = result.get("frames", [])
        points = sum(len((f.get("data", {}).get("values") or [[]])[0]) for f in frames)
        results.append({"panel": panel["title"], "returned_rows": points})
        if panel["type"] == "timeseries" and points == 0:
            details = [{"name": f.get("schema", {}).get("name"), "meta": f.get("schema", {}).get("meta"),
                        "fields": f.get("schema", {}).get("fields")} for f in frames]
            print(json.dumps({"panel": panel["title"], "query": target, "frames": details}, indent=2))
            raise RuntimeError("No native query data for " + panel["title"])
    (ROOT / ".operator/history-queries.json").write_text(json.dumps(results, indent=2)+"\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
