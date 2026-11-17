"""One durable MQTT-to-OPC-UA writer for the normal Cairn Reach request path."""
import asyncio
import json
import logging
import os
import queue
import time

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
import psycopg
from asyncua import Client, ua

from journal import receive, reconcile_restart, transition
from model import CONTRACT, completion, dispatchable, next_sequence, parse_request

LOG = logging.getLogger("site-dispatcher")
READS = ["RemoteSeen", "RemoteAccepted", "RemoteRejected", "RemoteRejectReason", "IoHealthy", "Owner", "AutoMode",
         "RequestedTargetPct", "RequestedTargetBPct", "RequestedFlowM3s", "PositionPct", "PositionBPct",
         "FlowM3s", "FlowBM3s", "MovingA", "MovingB", "PermissiveA", "PermissiveB"]


async def operate(request, notify):
    client = Client("opc.tcp://plc:4840/arwc", timeout=10)
    client.application_uri = "urn:arwc:dispatcher"
    await client.set_security_string("Basic256Sha256,SignAndEncrypt,/run/pki/client-cert.pem,/run/pki/client-key.pem,/run/pki/server-cert.pem")
    client.set_user("dispatcher")
    client.set_password(os.environ["UA_PASSWORD"])
    await client.connect()
    try:
        namespace = await client.get_namespace_index(CONTRACT["namespace_uri"])
        def node(name):
            return client.get_node(ua.NodeId("CRR." + name, namespace))
        async def snapshot():
            return dict(zip(READS, await client.read_values([node(n) for n in READS]), strict=True))
        sequence = next_sequence((await snapshot())[CONTRACT["commit"]["seen"]])
        notify("dispatch_intent", {"sequence": sequence, "origin": "dispatcher journal"})
        for field, tag in CONTRACT["request_tags"].items():
            value = request[field] if field != "mode" else request["mode"] == "automatic"
            kind = ua.VariantType.Boolean if field == "mode" else ua.VariantType.Float
            await node(tag).write_value(ua.Variant(value, kind))
        if time.time() >= request["expires_at"]:
            notify("expired", {"sequence": sequence, "reason": "expired before PLC commit"})
            return
        await node(CONTRACT["commit"]["sequence"]).write_value(ua.Variant(sequence, ua.VariantType.UInt16))
        notify("dispatched", {"sequence": sequence, "origin": "OPC UA sequence write"})
        accepted = False
        settled = 0
        while time.time() < request["expires_at"]:
            state = await snapshot()
            if not accepted and state["RemoteSeen"] == sequence:
                # Seen and this channel's decision reason disambiguate stale
                # Accepted/Rejected values when the 16-bit sequence wraps.
                if state["RemoteRejectReason"] and state["RemoteRejected"] == sequence:
                    notify("plc_rejected", {"sequence": sequence, "reason_code": state["RemoteRejectReason"], "origin": "native PLC decision"})
                    return
                if state["RemoteAccepted"] == sequence and state["RemoteRejectReason"] == 0:
                    notify("plc_accepted", {"sequence": sequence, "origin": "native PLC decision"})
                    accepted = True
            if accepted:
                if not state["IoHealthy"] or not state["PermissiveA"] or not state["PermissiveB"]:
                    notify("uncertain", {"sequence": sequence, "reason": "field feedback or permissive lost"})
                    return
                if state["Owner"] != 2 or state["AutoMode"] != (request["mode"] == "automatic"):
                    notify("superseded", {"sequence": sequence, "owner": state["Owner"], "origin": "native PLC ownership"})
                    return
                settled = settled+1 if completion(request, state) else 0
                if settled >= CONTRACT["feedback"]["settled_samples"]:
                    notify("completed", {"sequence": sequence, "origin": "observed equipment feedback",
                        "position_a_pct": state["PositionPct"], "position_b_pct": state["PositionBPct"],
                        "flow_a_m3s": state["FlowM3s"], "flow_b_m3s": state["FlowBM3s"]})
                    return
            await asyncio.sleep(CONTRACT["feedback"]["poll_seconds"])
        notify("uncertain", {"sequence": sequence, "reason": "feedback deadline reached; inspect equipment"})
    finally:
        await client.disconnect()


def main():
    logging.basicConfig(level=logging.INFO)
    inbox = queue.Queue(maxsize=CONTRACT["maximum_pending_messages"])
    broker = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="crr-site-dispatcher", protocol=mqtt.MQTTv5, manual_ack=True)
    broker.username_pw_set("dispatcher", os.environ["MQTT_PASSWORD"])
    broker.tls_set(ca_certs="/run/pki/ca.pem")
    broker.max_queued_messages_set(32)
    broker.max_inflight_messages_set(16)
    broker.reconnect_delay_set(min_delay=1, max_delay=10)

    def connected(client, userdata, flags, reason, properties):
        if not reason.is_failure:
            client.subscribe(CONTRACT["request_topic"], options=mqtt.SubscribeOptions(qos=1, retainAsPublished=True))
            LOG.info("Connected to the authenticated site request path")

    def arrived(client, userdata, message):
        if message.topic != CONTRACT["request_topic"]:
            return
        if message.retain or message.qos != 1:
            client.ack(message.mid, message.qos)
            LOG.warning("Ignored delivery outside non-retained QoS 1 contract")
            return
        try:
            inbox.put_nowait(message)
        except queue.Full:
            # The receive maximum normally prevents this. Leave delivery
            # unacknowledged; reconciliation/retry still uses the durable ID.
            LOG.warning("Incoming queue full; delivery remains unacknowledged")

    def publish(outcome):
        result = broker.publish(CONTRACT["outcome_topic"], json.dumps(outcome), qos=1, retain=False)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            LOG.warning("Outcome delivery unavailable; durable state is preserved")

    broker.on_connect = connected
    broker.on_message = arrived
    with psycopg.connect(autocommit=True, connect_timeout=10) as db:
        if not db.execute("SELECT pg_try_advisory_lock(367)").fetchone()[0]:
            raise RuntimeError("Another site request writer is already active")
        LOG.info("Marked %s unfinished requests uncertain", reconcile_restart(db))
        properties = Properties(PacketTypes.CONNECT)
        properties.SessionExpiryInterval = 86400
        properties.ReceiveMaximum = CONTRACT["maximum_pending_messages"]
        broker.connect("mosquitto", 8883, keepalive=30, clean_start=False, properties=properties)
        broker.loop_start()
        try:
            while True:
                message = inbox.get()
                try:
                    request = parse_request(message.payload)
                except (ValueError, TypeError, UnicodeError):
                    publish({"status": "invalid", "reason": "request does not match the published site contract"})
                    broker.ack(message.mid, message.qos)
                    continue
                new, outcome = receive(db, request)
                # Receive commits the journal before acknowledging MQTT delivery.
                broker.ack(message.mid, message.qos)
                publish(outcome)
                if not new:
                    continue

                def notify(status, detail):
                    publish(transition(db, request["id"], status, detail))

                if not dispatchable(request, time.time()):
                    notify("expired", {"reason": "expiry is outside the dispatch window"})
                    continue
                try:
                    asyncio.run(operate(request, notify))
                except psycopg.Error:
                    # Exit on journal loss; a new writer must reconcile first.
                    raise
                except Exception as error:
                    LOG.error("Request %s needs reconciliation (%s)", request["id"], type(error).__name__)
                    notify("uncertain", {"reason": "OPC UA feedback unavailable; operator reconciliation required"})
        finally:
            broker.disconnect()
            broker.loop_stop()


if __name__ == "__main__":
    main()
