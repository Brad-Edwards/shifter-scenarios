"""Focused field reconnect, local ownership, and retained-state checks."""
import argparse
import asyncio
import hashlib
import json
import pathlib
import time

import psycopg
from asyncua import ua
from configure_fuxa import session_for_fuxa, URL
from qualify_opcua import connect

ROOT = pathlib.Path("/slice")


async def readings():
    client = await connect("reader")
    try:
        ns = await client.get_namespace_index("urn:arwc:crr:tags")
        result = {}
        for name in ("IoHealthy", "RequestedTargetPct", "PositionPct", "HmiAccepted", "HmiRemoteEnabled", "Owner"):
            result[name] = await client.get_node(ua.NodeId("CRR." + name, ns)).read_value()
        return result
    finally:
        await client.disconnect()


def main():
    mode = argparse.ArgumentParser()
    mode.add_argument("phase", choices=("field-down", "field-up", "local-priority", "retained"))
    phase = mode.parse_args().phase
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
    session = session_for_fuxa()
    def history_quality():
        with psycopg.connect(host="postgres", dbname="historian", user="reader", password=credentials["reader"]) as db:
            row = db.execute("SELECT process_quality FROM process_history WHERE tag='level_m' AND source_time>now()-interval '4 seconds' ORDER BY source_time DESC LIMIT 1").fetchone()
            return row[0] if row else None
    if phase == "local-priority":
        before = asyncio.run(readings())
        assert before["Owner"] == 2, "First run the remote operating path"
        for name, value in (("HmiTargetPct", 35.0), ("HmiSequence", before["HmiAccepted"] % 65535 + 1)):
            session.post(URL + "/api/setTagValue", json={"tags": [{"id": name, "value": value}]}, timeout=10).raise_for_status()
    deadline = time.monotonic() + 70
    while time.monotonic() < deadline:
        try:
            values = asyncio.run(readings())
            quality = history_quality()
            if phase == "field-down":
                passed = values["IoHealthy"] is False and quality == "FieldUnavailable"
            elif phase == "field-up":
                passed = values["IoHealthy"] is True and quality == "Good"
            else:
                passed = values["IoHealthy"] is True and values["HmiRemoteEnabled"] is False and values["RequestedTargetPct"] == 35.0 and abs(values["PositionPct"]-35.0) < 0.1 and quality == "Good"
                if phase == "local-priority":
                    passed = passed and values["Owner"] == 1
                # Reconnection must reach FUXA's real subscription too.
                response = session.get(URL + "/api/getTagValue", params={"ids": '["RequestedTargetPct","IoHealthy"]'}, timeout=10)
                response.raise_for_status()
                hmi = {r["id"]: r.get("value") for r in response.json()}
                passed = passed and hmi.get("RequestedTargetPct") == 35.0 and hmi.get("IoHealthy") == True
            if passed:
                result = {"phase": phase, "observations": values, "historian_quality": quality,
                          "server_certificate_sha256": hashlib.sha256((ROOT / ".operator/server-cert.pem").read_bytes()).hexdigest()}
                (ROOT / f".operator/{phase}-evidence.json").write_text(json.dumps(result, indent=2)+"\n")
                print(json.dumps(result, indent=2))
                return
        except (ConnectionError, OSError, asyncio.TimeoutError):
            pass
        time.sleep(1)
    raise AssertionError(f"Operating state did not converge during {phase}")


if __name__ == "__main__":
    main()
