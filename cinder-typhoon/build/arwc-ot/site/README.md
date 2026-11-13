# Cairn Reach site controller

This directory implements issue #364. It contains the two-outlet PLC project,
physical remote I/O, and focused engineering checks. The
[design](design.md) defines the control rules and data flow.

The native, physical-response, live operating, online engineering, and full VM
restart checks passed on November 13, 2026 (UTC). Participant acceptance remains
downstream work.

## Development setup

Use `cinder-arwc-ot-compat-363` in `prod-mgau4w`, zone `us-central1-a`.
Use IAP SSH as `bedwards@paloaltonetworks.com`. Keep the source tree and
operator state in `/opt/arwc-ot-compat/slice`. Do not use `/tmp` for persistent files.

Follow the parent [preparation instructions](../README.md#manual-setup), then run
these commands on the VM:

```sh
cd /opt/arwc-ot-compat/slice
bash site/prepare-test-tools.sh
bash site/setup-site.sh
```

Setup uses the official Editor scaffold, creates `arwc-site`, and downloads the
compiled FBD program through the normal Runtime management interface. It uses
separate site volumes for PLC state, PostgreSQL, FUXA, and Grafana. Earlier
compatibility volumes remain preserved. Do not change operator files independently
of their matching product volumes.

The project is `/opt/arwc-ot-compat/work/arwc-site`. Open it in OpenPLC Editor.
`main.fbd` shows site measurements, both permissive chains, request arbitration,
flow splitting, and two outlet instances. Open the ST blocks for their logic.
Online engineering exposes root variables and the individual function-block fields.

The site Compose override enables ordinary container restart after VM boot.
The PLC restarts disarmed, with remote enable and automatic mode cleared.
Accepted manual positions and automatic flow settings survive. Physical level
and actuator position survive separately in `.operator/site-io/equipment.json`.
The physical model pauses while the VM is stopped.

## Operator contract

[tags.json](tags.json) defines 50 public tags, raw I/O addresses, engineering
units, scaling, request feedback, motion states, and physical parameters.
Original first-outlet identities remain available. `PositionPct` and `FlowM3s`
refer to outlet A; the B tags and `TotalFlowM3s` are explicit.

Stage the two targets, requested mode, and total automatic flow before changing
the request sequence. Read the accepted or rejected sequence and its reason.
Use `HmiSeen` or `RemoteSeen` to select a new sequence after a rejected request.
An unchanged sequence does not issue another operation.

Local requests take precedence and disable remote operation. The HMI must
explicitly enable remote operation again. Operator stop removes both enables.
After field loss, fault, or restart, issue a new valid request to resume.

Manual mode sets independent positions. Automatic mode splits total flow equally
between two maintained native PID blocks, each using its measured outlet flow.
The configured flow deadband stops unnecessary motor reversals near setpoint.

| Loop setting | Value |
| --- | --- |
| Native PID gain | `-1.0` for its `PV - SP` error convention |
| Integral / derivative time | `5.0 s` / `0.0 s` |
| Cycle | `T#100ms` |
| Manual tracking | `X0 = -PositionPct` with the negative gain |
| Regulation starts / stops | Error above `0.0075 m3/s` / within `0.0025 m3/s` |

These values qualify this small physical model. They do not constitute tuning
for a real installation or a safety-instrumented system. VM scheduling provides
no hard real-time guarantee.

## Focused checks

Run builds and all runtime checks on the dedicated VM:

```sh
python3 site/run_controller_tests.py
sudo docker compose -f compose.yaml -f site/compose.yaml run --rm -T tools python /slice/site/test_physics.py
sudo docker compose -f compose.yaml -f site/compose.yaml run --rm -T tools python /slice/site/qualify_site.py operating
python3 site/qualify_engineering.py
```

The native tests execute the actual IEC blocks. They check scaling, request
validation, ownership, modes, permissives, timers, and automatic regulation.
Focused mutations must reach failing assertions. The physical checks cover
travel, mass balance, actuator hold, mechanical response, and persistence.

The live operating check uses real OPC UA requests. It compares PLC results
with independent Modbus registers and coils. It requires both automatic loops
to settle with their motor enables off.

To check field recovery, stop only this stack's `io` service. Run
`qualify_site.py field-down` through the tools service. Start `io`, then run
`qualify_site.py field-up`. Recovery must not replay the inactive request.

Before a controller or VM restart, run `qualify_site.py prepare-restart` through
the tools service. After restart, run `qualify_site.py restart`. This checks
retained settings, physical position, disabled motion, and cleared remote enable.

Product logs and generated reports stay under `.operator/`. The reviewable result
is [evidence/qualification.json](evidence/qualification.json). Do not publish
credentials, keys, generated server configuration, or complete operator directories.

## Component handoff

FUXA, historian, dispatcher, and workstation work can use this branch and its
tag contract. The compatibility fixtures remain in the parent directory.
The current FUXA fixture and history collection expose the original tags;
their complete two-outlet presentation belongs to issues #365 and #366.
The original single-outlet dispatcher stays stopped during site development.

This component qualification does not establish participant UI or integrated
utility acceptance. Those checks remain with the downstream component and
integration work. No incident, vulnerability, challenge, or scoring behavior
is included here.
