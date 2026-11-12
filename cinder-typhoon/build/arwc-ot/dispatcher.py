"""Small compatibility fixture: authenticated MQTT requests to PLC request tags.

One worker owns the remote request sequence. PostgreSQL prevents MQTT redelivery
from issuing a second command. Restart never automatically replays an uncertain
command. This is a development fixture for #367, not the complete site service.
"""
import asyncio
import json
import logging
import math
import pathlib
import queue
import time
import uuid

import paho.mqtt.client as mqtt
import psycopg
from asyncua import ua
from qualify_opcua import connect

OPERATOR = pathlib.Path("/slice/.operator")
REQUEST = "arwc/crr/commands/operator"
OUTCOME = "arwc/crr/outcomes/operator"
LOG = logging.getLogger("dispatcher")


async def operate(request: dict, notify) -> None:
    client = await connect("dispatcher")
    try:
        ns = await client.get_namespace_index("urn:arwc:crr:tags")
        def node(name):
            return client.get_node(ua.NodeId("CRR." + name, ns))
        if not await node("IoHealthy").read_value():
            raise ValueError("field I/O unavailable")
        if not await node("HmiRemoteEnabled").read_value():
            raise ValueError("local operator has not enabled remote operation")
        accepted = await node("RemoteAccepted").read_value()
        if request["sequence"] != (accepted % 65535) + 1:
            raise ValueError("request sequence must follow PLC accepted sequence")
        await node("RemoteTargetPct").write_value(ua.Variant(request["target_pct"], ua.VariantType.Float))
        # The sequence commits the staged target; each channel has its own writer.
        await node("RemoteSequence").write_value(ua.Variant(request["sequence"], ua.VariantType.UInt16))
        notify("dispatched")
        deadline = min(request["expires_at"], time.time() + 30)
        acknowledged = False
        while time.time() < deadline:
            if not await node("IoHealthy").read_value():
                raise ValueError("field I/O lost while awaiting feedback")
            if await node("RemoteAccepted").read_value() == request["sequence"]:
                if not acknowledged:
                    notify("plc_accepted")
                    acknowledged = True
                # Ownership and retained target are independent of broker delivery.
                target = await node("RequestedTargetPct").read_value()
                owner = await node("Owner").read_value()
                if owner != 2 or abs(target - request["target_pct"]) > 0.05:
                    raise ValueError("request superseded by local operator")
                if abs(await node("PositionPct").read_value() - target) <= 0.1:
                    notify("completed")
                    return
            await asyncio.sleep(0.2)
        raise ValueError("PLC/equipment feedback deadline exceeded")
    finally:
        await client.disconnect()


def validate(payload: bytes) -> dict:
    request = json.loads(payload)
    if set(request) != {"id", "sequence", "target_pct", "expires_at"}:
        raise ValueError("unexpected command fields")
    uuid.UUID(request["id"])
    if type(request["sequence"]) is not int or not 1 <= request["sequence"] <= 65535:
        raise ValueError("invalid sequence")
    for name in ("target_pct", "expires_at"):
        if type(request[name]) not in (float, int) or not math.isfinite(request[name]):
            raise ValueError("invalid numeric field")
    if not 0 <= request["target_pct"] <= 100:
        raise ValueError("target outside equipment range")
    if not time.time() < request["expires_at"] <= time.time() + 120:
        raise ValueError("request expired or deadline exceeds 120 seconds")
    request["target_pct"] = float(request["target_pct"])
    return request


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    credentials = json.loads((OPERATOR / "credentials.json").read_text())
    inbox = queue.Queue(maxsize=16)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="crr-dispatcher", protocol=mqtt.MQTTv5)
    client.username_pw_set("dispatcher", credentials["mqtt_dispatcher"])
    client.tls_set(ca_certs=str(OPERATOR / "mosquitto/ca.pem"))
    def connected(client, userdata, flags, reason, properties):
        if not reason.is_failure:
            client.subscribe(REQUEST, options=mqtt.SubscribeOptions(qos=1, retainAsPublished=True))
            LOG.info("Subscribed to authenticated operator request path")
    def received(client, userdata, message):
        if message.topic == REQUEST and not message.retain:
            try:
                inbox.put_nowait(message.payload)
            except queue.Full:
                LOG.warning("Command queue full; operator must retry with same request ID")
    client.on_connect = connected
    client.on_message = received
    client.connect("mosquitto", 8883, keepalive=30)
    client.loop_start()
    with psycopg.connect(host="postgres", dbname="historian", user="dispatcher", password=credentials["pg_dispatcher"], autocommit=True) as db:
        # Unfinished requests require operator reconciliation, never silent replay.
        db.execute("UPDATE command_events SET status='uncertain' WHERE status IN ('received','dispatched','plc_accepted')")
        while True:
            payload = inbox.get()
            try:
                request = validate(payload)
            except (ValueError, TypeError, KeyError):
                LOG.warning("Invalid or expired request ignored")
                continue
            inserted = db.execute("INSERT INTO command_events (id,sequence,target_pct,status,principal) VALUES (%s,%s,%s,'received','operator') ON CONFLICT DO NOTHING RETURNING id",
                                  (request["id"], request["sequence"], request["target_pct"])).fetchone()
            if not inserted:
                row = db.execute("SELECT status,sequence,target_pct FROM command_events WHERE id=%s", (request["id"],)).fetchone()
                client.publish(OUTCOME, json.dumps({"id": request["id"], "status": row[0], "duplicate": True}), qos=1)
                continue
            def notify(status):
                db.execute("UPDATE command_events SET status=%s WHERE id=%s", (status, request["id"]))
                db.execute("INSERT INTO command_transitions (command_id,status) VALUES (%s,%s)", (request["id"], status))
                client.publish(OUTCOME, json.dumps({"id": request["id"], "status": status}), qos=1)
                LOG.info("Command %s: %s", request["id"], status)
            notify("received")
            try:
                asyncio.run(operate(request, notify))
            except Exception as error:
                # No credentials or request bodies enter logs.
                LOG.error("Command %s requires reconciliation (%s)", request["id"], type(error).__name__)
                notify("uncertain")


if __name__ == "__main__":
    main()
