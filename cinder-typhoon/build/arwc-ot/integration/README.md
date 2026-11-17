# Join the ARWC operating site and IT services

Use the dedicated development VM `cinder-arwc-ot-compat-363` in `prod-mgau4w`,
zone `us-central1-a`. Use account `bedwards@paloaltonetworks.com` and IAP access.
The approved VM has an 80 GiB disk and four virtual CPUs.
Normal operating qualification passed on November 13, 2026 (UTC).
The [development result](evidence/development.json) records the native tools, mechanical fault/reset, recovery, and measured resource limits.
Fresh private images and BigRAE delivery remain deferred.

## Prepare the source

Keep the qualified OT source in `/opt/arwc-ot-compat/slice`.
Place the existing committed IT source in `/opt/arwc-ot-compat/it/cinder-typhoon`.
The IT build requires `build/arwc` and
`assets/narrative/generated/packages/arwc-documents.json` from the same revision.
Copy the integration PR's bridge source and Dockerfile changes into that tree.
Do not copy `.operator` directories or initialized service volumes from another range.

Build only on the development VM. From the OT source directory, run:

```sh
python3 integration/check_bridge.py
python3 integration/check_contract.py
bash integration/build-it.sh
```

The build uses the existing IT Dockerfiles, one service at a time.
Its output stays in the IT tree's `.operator/integration-image-build.log`.
The build does not restart the active OT components.

## Apply the integration

First coordinate the PostgreSQL restart with active QA through root `qa-test.json`.
Keep all completed component results. Apply the joined configuration on the VM:

```sh
cd /opt/arwc-ot-compat/slice
bash integration/setup-integration.sh
```

Preparation appends provenance to the selected historian view. It creates a
native PostgreSQL TLS identity and private bridge connection files. The bridge
uses `dmz_reader` over TLS with server name verification. The exchange network
contains only PostgreSQL and the existing data bridge. Neither forwards IP packets.
The bridge has no membership in the new supervisory or field network.

Setup preserves existing IT operator material. It creates that material only
when the separate development IT tree has no corporate CA. It starts the existing
IT services and enables the selected historical read endpoint. The development
FieldLink listener uses this VM's private address, `10.77.59.6`.
The existing golden range is not a deployment target for these scripts.

## Read operational history

The existing DMZ bridge serves `GET /api/operating-history` over its HTTPS
listener. Use its normal corporate server identity and trust the range's
corporate CA. The separate `operating-reader` account uses HTTP Basic
authentication over TLS. Its private connection record stays in
`.operator/integration-bridge/operating-reader.json` on the OT host.
Do not put the password into reports or the coordination file.

Each response contains at most 900 samples from the preceding five minutes.
The three series are reservoir level, usable volume, and total outlet flow.
Records preserve asset, source time, collection time, ingestion time, value,
unit, process quality, and acquisition origin. A collection gap stays a gap.
A native query failure returns unavailable, with no invented measurements.

The endpoint accepts no caller SQL. It issues one fixed SELECT through the
native PostgreSQL client with a read-only role and a two-second statement limit.
Existing bridge routes and their authorization contracts remain intact.
No legacy completion state enables or disables this operating endpoint.

## Qualification

The developer checks cover authentication before query execution, a bounded
read-only query, preserved values and quality, and restricted error responses.
Focused mutations must fail those checks. The native Compose preflight checks
exchange membership, disabled IP forwarding, and the absence of a published
PostgreSQL port. These checks do not establish participant acceptance.

Use QA through root `qa-test.json` for the joined operating walkthrough.
Use the normal engineering desktop, HMI, PLC, historical viewer, and dispatcher.
Confirm the corporate read matches the actual historical records and identities.
Include active fault reset, maintenance download, communications recovery, and
full VM restart. Preserve legacy service state; do not seed challenge completion.

For active travel-fault reset, use the authored mechanical actuator fixture in
`site/remote_io.py`. Prepare that fixture before a fresh valid operator request.
Choose a requested position different from the held physical feedback.
Wait for healthy field communications before issuing the request.
Changing the I/O fixture can disarm operation; an old request will not replay.
Observe the real PLC timeout and FUXA alarm.
Acknowledge the alarm and reset the actual PLC fault through the operator faceplate.
Restore normal mechanical response and confirm that motion requires a fresh valid request.
A no-fault reset click does not establish this case.

Record CPU, RAM, historical disk growth, desktop/compiler load, and scan timing
with the existing IT services running. The bounded `capture_capacity.py` helper
records host load, Docker statistics, disk space, and native database size.
Run it during normal operation and an authorized engineering download:

```sh
python3 integration/capture_capacity.py --seconds 600 --label joined-operation
```

The helper prints its private output path after completion. Use
`summarize_capacity.py RECORD_PATH` to summarize that selected record.
The helper captures no process arguments, environments, credentials, or packet contents.
Docker CPU percentages use one core as 100%; host CPU uses all cores as 100%.
Use OpenPLC Editor's Runtime Status view for native scan, cycle, latency, and
overrun statistics. The Runtime status interface also supplies these statistics
when `include_stats` is enabled. Keep this optional polling bounded; it adds work
to the controller. Do not infer scan timing from Telegraf's collection interval. State the measured sizing limits before
issue #370 private image qualification. Final BigRAE access uses the platform's
native participant container, RDP, VPN, and credential contracts.

## Bound container logs

The joined Compose files limit each service to three 10 MiB Docker JSON logs.
These limits apply when containers are created; a VM reboot alone does not apply changed limits.
Coordinate container recreation with QA and keep all existing service volumes.
The PLC stores its compiled program and OPC UA identity in its container layer.
Do not recreate it merely to change log settings.
A coordinated maintenance replacement must restore the native project and product trust before operation resumes.
The historian has separate partition retention and an 8 GiB high-water limit.

After QA saves and pauses its work, apply reviewed development settings with:

```sh
bash integration/refresh-development.sh
```

The helper recreates only named OT services and the existing IT stack.
It preserves the PLC container, product volumes, and saved participant project.
The desktop disconnects briefly. QA must reconnect and check actual operation after deployment.
The existing PLC retains its earlier log settings until a separate coordinated maintenance replacement.
