# Cairn Reach remote dispatcher

This service maps the fixed authenticated MQTT request path to the native PLC's
remote command channel. It does not decide process interlocks or replace the
HMI. Use the [contract](contract.json) and [design](design.md) as the reference.

## Development installation

Use `cinder-arwc-ot-compat-363` in `prod-mgau4w`, `us-central1-a`. First complete
the [site setup](../site/README.md). Keep source in the persistent
`/opt/arwc-ot-compat/slice` directory. Coordinate with active QA, then run:

```sh
cd /opt/arwc-ot-compat/slice
bash dispatch/setup-dispatcher.sh
```

Setup installs the native database journal and a separate OPC UA client identity,
disables retained messages on the existing narrow broker, restarts Mosquitto,
and starts `site-dispatcher`. It does not send an equipment request. The older
one-outlet `dispatcher` fixture is stopped and has a compatibility profile.
Do not start that fixture alongside the site dispatcher.

For subsequent stack operations, combine the base and site files with
`dispatch/compose.yaml`. Include `historian/compose.yaml` when installed. The
dispatcher has supervisory access only, runs without root or added capabilities,
and receives only its own database, MQTT, and OPC UA credentials. It does not
mount the complete operator credential directory.

Private credentials remain in the VM's `.operator` directory. The requesting
MQTT user is `operator`, with the existing `mqtt` password. The service uses the
distinct `dispatcher` broker user and the `ua_dispatcher` OPC UA identity.
Certificate material is development state with a 30-day validity. Bake and
integration work must create fresh private identities; do not publish these
credentials or copy them into source or QA reports.

## Normal operating path

Use Site controls in FUXA to enable remote selection. Send a non-retained QoS 1
request through the existing TLS broker using the operator account and fixed
request topic. The complete envelope contains a fresh UUID, the Cairn Reach
asset ID, manual or automatic mode, both manual positions, total automatic flow,
and an absolute expiry within 120 seconds. `expires_at` is a numeric Unix epoch
timestamp in UTC seconds, with optional fractional seconds. It is not an ISO
8601 string. Field names and bounds are in the
contract. Do not supply a user identity or PLC sequence in the envelope.

The dispatcher chooses the next consumed PLC sequence and stages the complete
request. The PLC can accept or reject it. Watch the outcome topic and compare
the result with both measured outlet values in FUXA. Native MQTT PUBACK means
broker receipt; `received`, `dispatched`, `plc_accepted` or `plc_rejected`, and
`completed` describe separate application stages. Completion needs stable
measured feedback from both outlets. Acknowledgement alone is not completion.

A normal HMI request has local priority and removes remote selection. Local
takeover ends remote work as `superseded`. Missing or ambiguous feedback ends it
as `uncertain`. An expired request cannot be committed. Operators inspect the
site before choosing a fresh request after an uncertain result.

Supersession applies while a request is in flight. An already completed request
keeps its historical completion result when the HMI later takes ownership.

Repeat the same UUID and complete payload to retrieve its recorded state.
A repeat does not produce another PLC operation. A changed payload under the
same UUID returns a conflict. Restart marks unfinished requests uncertain and
never resumes them. Durable requests and transitions remain available through
the PostgreSQL reader's `dispatch_history` view. Broader retention and the
combined utility dashboard are integration work in #369.

## Verification

Run focused developer checks on the VM:

```sh
sudo docker compose -f compose.yaml -f site/compose.yaml run --rm -T tools python /slice/dispatch/test_model.py
sudo docker compose -f compose.yaml -f site/compose.yaml run --rm -T tools python /slice/dispatch/test_journal.py
```

The model checks do not connect to equipment. Database fixtures and mutations
are rolled back. They cover request scope, finite ranges, expiry, sequence wrap,
both-outlet completion, duplicate identity, payload conflicts, restart, and
preservation of terminal results. They do not establish broker-to-equipment QA.

Coordinate live installation and normal operating tests only through the root
`qa-test.json`. Let QA choose the mechanics and use the documented HMI/remote
path. Check receipt versus acceptance versus completion, local priority,
ordinary retries, reconnect, restart, and measured feedback. Keep incident,
vulnerability, and challenge work out of this component task.
