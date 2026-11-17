# Cairn Reach PostgreSQL historian

Use maintained Telegraf inputs and its PostgreSQL output for the site's 50 real
OPC UA tags. PostgreSQL stores raw records and quality-aware views. Grafana reads
those views. A small read-only export copies native FUXA alarm records.

## Development setup

Use `cinder-arwc-ot-compat-363` in `prod-mgau4w`, `us-central1-a`. Start with the
[site setup](../site/README.md) and keep all work under the persistent
`/opt/arwc-ot-compat/slice` directory. Copy this directory there, then run:

```sh
cd /opt/arwc-ot-compat/slice
bash historian/setup-history.sh
```

This installs the fixed PostgreSQL schema and roles, creates daily partitions,
starts maintenance and alarm export, and replaces the collector configuration.
It restarts the collector and Grafana. The PLC and HMI controls keep running.
It preserves existing raw compatibility tables and measurement records.

For subsequent stack operations, combine all three files:

```sh
sudo docker compose -f compose.yaml -f site/compose.yaml -f historian/compose.yaml ps
```

Do not run the older compatibility or site configuration scripts as historian
maintenance. They install the earlier fixture configurations. If a development
rebuild needs those scripts, reapply the HMI and historian setups afterwards.
The final integrated setup is issue #369.

## Operator and engineering access

Open **Process history** from the HMI. Grafana remains at the existing private
supervisory address `172.29.63.25:3000`. The read-only product account is
`history`; its `grafana_viewer` password remains in the VM's private
`.operator/history-credentials.json`. Keep credentials out of reports and the
coordination file. Configuration remains an administrator function.

The dashboard supplies reservoir level and volume, both outlet positions and
flows, total flow, native alarms and acknowledgements, and observed PLC command
decisions. Units match the published register. Bad-quality values and acquisition
gaps remain blank. The line does not connect across a missing interval.

The PostgreSQL `reader` role can select `process_history`, `alarm_history`,
`command_history`, and `historian_tag_catalog`. Each measurement exposes source,
collection, and ingestion times separately. The catalog records stable NodeIds,
the register digest, engineering ranges, and Modbus scaling provenance.

The separate `dmz_reader` can select only `dmz_process_history`: reservoir level,
usable volume, total flow, and quality. This does not deploy a DMZ integration
or grant access to corporate planning data. Native acquisition has no control
write permission.

## Events and limits

FUXA remains the source of alarm activation, return-to-normal, acknowledgement,
and acknowledging-user data. Export preserves those native fields and retries
after connection loss. Alarm records use a 30-day activation-time window.

The native OPC UA listener records PLC accepted/rejected sequence changes.
Initial observations are baselines, not commands. The historical view contains
observed channel decisions, not a complete transaction audit or user identity.
The bounded notification queue cannot recover decisions made during an outage.
The dispatcher's durable request/transition history is a separate record; its
two-outlet expansion is issue #367. No exporter invents missing events.

Measurements have a maximum seven-day retention; command signals have a maximum
30-day retention. Daily partition maintenance runs every minute. It removes old
partitions sooner when database allocation reaches 7 GiB. An insert guard stops
ingestion at 8 GiB. Current-day partitions are retained. These are database
growth thresholds, not filesystem quotas; retain headroom for PostgreSQL WAL,
indexes, images, and other VM data.

If current-day data alone reaches the high threshold, inspect capacity and the
retention policy before resuming collection. The collector buffers at most
10,000 metrics, about 200 seconds at the nominal 50-tag rate. Longer outages
can lose samples; the resulting gap must remain visible. Container logs for
acquisition, export, and maintenance are rotated with fixed size limits.

## Verification

All runtime checks run on the development VM. The focused developer checks are:

```sh
sudo docker compose -f compose.yaml -f site/compose.yaml -f historian/compose.yaml run --rm -T tools python /slice/historian/test_database.py
sudo docker compose -f compose.yaml -f site/compose.yaml -f historian/compose.yaml run --rm -T tools python /slice/historian/check_installation.py
```

The SQL fixtures and mutations are rolled back. They do not enter published
history. The installation check reads real acquisition counters and timestamp
provenance. It does not establish operating, reconnect, or browser acceptance.
Coordinate that QA through the root `qa-test.json`, using the documented normal
operating path and approved private access.
