"""Normal operating path qualification on the isolated compatibility VM."""
import asyncio
import json
import pathlib
import queue
import time
import uuid

import paho.mqtt.client as mqtt
import psycopg
import requests
from asyncua import ua
from configure_fuxa import session_for_fuxa, URL
from qualify_opcua import connect

ROOT = pathlib.Path("/slice")


def wait_for(check, description, seconds=35):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.25)
    raise AssertionError(description)


async def sequence(channel):
    client = await connect("reader")
    try:
        ns = await client.get_namespace_index("urn:arwc:crr:tags")
        current = await client.get_node(ua.NodeId("CRR." + channel + "Accepted", ns)).read_value()
        return (current % 65535) + 1
    finally:
        await client.disconnect()


def main():
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
    observations = {}
    session = session_for_fuxa()
    def tags():
        response = session.get(URL + "/api/getTagValue", params={"ids": json.dumps(["LevelM", "PositionPct", "HmiAccepted", "IoHealthy", "Owner"])}, timeout=10)
        response.raise_for_status()
        return {v["id"]: v.get("value") for v in response.json()}
    wait_for(lambda: tags().get("LevelM") == 8.0 and tags().get("IoHealthy") == True, "FUXA did not read real PLC I/O")
    seq = asyncio.run(sequence("Hmi"))
    for name, value in (("HmiTargetPct", 25.0), ("HmiSequence", seq)):
        session.post(URL + "/api/setTagValue", json={"tags": [{"id": name, "value": value}]}, timeout=10).raise_for_status()
    wait_for(lambda: tags().get("HmiAccepted") == seq and abs((tags().get("PositionPct") or 0)-25.0) <= 0.1, "FUXA command did not reach equipment feedback")
    assert tags()["Owner"] == 1
    observations["fuxa_hmi"] = {"sequence": seq, "feedback_pct": tags()["PositionPct"], "owner": 1}
    session.post(URL + "/api/setTagValue", json={"tags": [{"id": "HmiRemoteEnabled", "value": True}]}, timeout=10).raise_for_status()

    outcomes = queue.Queue()
    subscribed = queue.Queue()
    broker = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
    broker.username_pw_set("operator", credentials["mqtt"])
    broker.tls_set(ca_certs=str(ROOT / ".operator/mosquitto/ca.pem"))
    broker.on_message = lambda client, userdata, message: outcomes.put(json.loads(message.payload))
    broker.on_connect = lambda client, userdata, flags, reason, properties: client.subscribe("arwc/crr/outcomes/operator", qos=1)
    broker.on_subscribe = lambda *args: subscribed.put(True)
    broker.connect("mosquitto", 8883)
    broker.loop_start()
    try:
        subscribed.get(timeout=10)
        request = {"id": str(uuid.uuid4()), "sequence": asyncio.run(sequence("Remote")), "target_pct": 40.0, "expires_at": time.time()+60}
        broker.publish("arwc/crr/commands/operator", json.dumps(request), qos=1).wait_for_publish(timeout=10)
        stages = []
        deadline = time.monotonic()+40
        while time.monotonic() < deadline:
            result = outcomes.get(timeout=max(1, deadline-time.monotonic()))
            if result.get("id") == request["id"]:
                stages.append(result["status"])
                if result["status"] in ("completed", "uncertain"):
                    break
        assert stages == ["received", "dispatched", "plc_accepted", "completed"], stages
        wait_for(lambda: abs((tags().get("PositionPct") or 0)-40.0) <= 0.1 and tags().get("Owner") == 2, "MQTT command lacks real equipment feedback")
        # MQTT QoS redelivery is a normal operating condition; it must not actuate twice.
        broker.publish("arwc/crr/commands/operator", json.dumps(request), qos=1).wait_for_publish(timeout=10)
        repeated = outcomes.get(timeout=10)
        assert repeated == {"id": request["id"], "status": "completed", "duplicate": True}, repeated
        observations["mqtt_command"] = {"id": request["id"], "stages": stages, "feedback_pct": tags()["PositionPct"], "redelivery": "no redispatch"}
    finally:
        broker.disconnect()
        broker.loop_stop()

    with psycopg.connect(host="postgres", dbname="historian", user="reader", password=credentials["reader"]) as db:
        sample = wait_for(lambda: db.execute("SELECT source_time,ingested_at,value,transport_quality,process_quality FROM process_history WHERE tag='position_pct' AND source_time>now()-interval '10 seconds' AND value=40 AND ingested_at IS NOT NULL ORDER BY source_time DESC LIMIT 1").fetchone(), "Historian lacks the actual measured outcome")
        assert sample[3:] == ("Good", "Good"), sample
        assert sample[1] >= sample[0], sample
        observations["historian"] = dict(zip(("source_time", "ingested_at", "position_pct", "transport_quality", "process_quality"), map(str, sample)))

    grafana = requests.Session()
    grafana.auth = ("admin", credentials["grafana"])
    dashboard = grafana.get("http://grafana:3000/api/dashboards/uid/arwc-history", timeout=10)
    dashboard.raise_for_status()
    query = grafana.post("http://grafana:3000/api/ds/query", json={"from": str(int((time.time()-60)*1000)), "to": str(int(time.time()*1000)), "queries": [{"refId": "A", "datasource": {"type": "postgres", "uid": "arwc-postgres"}, "format": "table", "rawSql": "SELECT source_time, value FROM process_history WHERE tag='position_pct' AND source_time>now()-interval '1 minute' ORDER BY source_time DESC LIMIT 5"}]}, timeout=15)
    query.raise_for_status()
    result = query.json()["results"]["A"]
    assert not result.get("error"), result.get("error")
    assert result["frames"][0]["data"]["values"][0], "Grafana did not query PostgreSQL history"
    observations["historical_viewer"] = {"dashboard": dashboard.json()["dashboard"]["uid"], "postgres_rows": len(result["frames"][0]["data"]["values"][0])}
    output = ROOT / ".operator/path-evidence.json"
    output.write_text(json.dumps(observations, indent=2)+"\n")
    print(json.dumps(observations, indent=2))


if __name__ == "__main__":
    main()
