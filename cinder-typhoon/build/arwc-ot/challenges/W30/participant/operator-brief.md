# Cairn Reach remote operation CRR-OP-W30-R1

The site begins in its normal manual operating state: outlet A 20 percent,
outlet B 20 percent, approximately 0.10 m³/s per outlet and 0.20 m³/s total.
Confirm that baseline, healthy field I/O, both permissives, clear motion, and
clear travel faults before acting. Stop and report a product condition if the
site does not match it.

The approved remote work is automatic total flow 0.30 m³/s for asset
`AST-CRR-017`. The two position fields remain 20 percent in the complete
request even though automatic mode controls flow. Use Site controls in FUXA to
enable remote selection without changing the baseline.

Use the installed `arwc.remote-request/v1` contract. Create a fresh UUID and a
numeric Unix-time expiry 90 seconds in the future. Publish exactly one
non-retained QoS 1 request on the fixed authenticated operator topic. Do not
write PLC nodes directly, force a value, upload a program, use another MQTT
topic, or automatically retry an expired, rejected, superseded, or uncertain
request.

MQTT delivery, durable dispatcher receipt, dispatch, PLC acceptance, and
settled equipment feedback are different stages. Correlate the same UUID and
PLC sequence in the dispatcher outcome, `dispatch_history`, native
`command_history`, FUXA/OpenPLC state, and good-quality process history. The
remote result is settled only when both measured outlet flows are approximately
0.15 m³/s, total flow is approximately 0.30 m³/s, remote ownership is active,
both permissives are valid, and neither outlet is moving.

After remote completion, hand the site back through one complete local FUXA
request: manual mode, outlet A 20 percent, outlet B 20 percent, proposed total
flow 0.20 m³/s, and remote selection disabled. Local HMI priority must produce
a later accepted sequence. Finish only when owner is HMI, measured A/B position
is 20/20, measured flow is approximately 0.10 m³/s per outlet and 0.20 m³/s in
total, field I/O is healthy, both permissives are valid, motion has stopped,
and both travel faults are clear.

Repeating an identical UUID and payload only retrieves its durable result. A
changed payload under the same UUID is a conflict. Inspect and reconcile any
uncertain result; never create a second movement merely to make the evidence
look complete.
