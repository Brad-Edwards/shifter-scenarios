# ARWC OT compatibility slice

This directory implements issue #363. The normal operating paths passed on the
dedicated GCP VM on November 12, 2026 (UTC). See [qualification.json](evidence/qualification.json)
for observations and [versions.md](versions.md) for pinned products and licenses.
The [platform plan](../../docs/design/arwc-ot-platform-plan.md) defines the complete site.

This fixture contains one outlet, real IEC logic, real product interfaces, and
an intentionally small I/O response model. Site sequences, graphics, alarms,
workstations, and participant qualification belong to issues #364–#370.

## Proven paths

- Remote I/O → Modbus TCP → OpenPLC logic → encrypted native OPC UA → FUXA.
- FUXA request → PLC acceptance → Modbus output → measured outlet position.
- Authenticated TLS MQTT request → dispatcher → PLC acceptance → measured position.
- MQTT redelivery returns the recorded outcome without another dispatch.
- Telegraf → PostgreSQL → Grafana queries of those same canonical records.
- Local HMI takeover disables remote operation. Field loss changes process quality.
- Field recovery and controller restart restore subscriptions and collection.
- The setpoint survives controller restart; remote enable resets to local control.
- Official Editor compilation and GUI startup work with networking disabled.

FUXA's ordinary tag API exercised its real driver for these checks. This is
component compatibility evidence, not participant UI or full-site acceptance.

## Test VM

Run builds, compilation, and runtime checks on this dedicated VM.

| Setting | Value |
| --- | --- |
| Account | `bedwards@paloaltonetworks.com` |
| Project | `prod-mgau4w` |
| VM / zone | `cinder-arwc-ot-compat-363` / `us-central1-a` |
| VPC / subnet | `cinder-arwc-golden` / `cinder-arwc-carrier` |
| Private address | `10.77.59.6` |
| Size | `e2-standard-4`, 80 GB balanced disk |
| Access | IAP SSH and OS Login; no public IP |
| Cloud identity | No service account or OAuth scopes |
| Slice | `/tmp/arwc-ot-363` |
| Upstream products / project | `/opt/arwc-ot-compat/upstream` / `/opt/arwc-ot-compat/work/arwc-compat` |

The VM uses existing NAT and IAP rules. Golden hosts and participant ranges
are unchanged. Both Compose networks are internal. No service publishes a host
port. The VM can reach the bridge addresses for development through IAP SSH.
Stop the VM when active development ends; retain its disk for subsequent issues.

## Manual setup

Create the VM only if it does not exist:

```sh
bash cinder-typhoon/build/arwc-ot/create-test-vm.sh prod-mgau4w
```

Wait for `/var/lib/arwc-ot-compat-ready`. Copy this directory through IAP to
`/tmp/arwc-ot-363`. Exclude `.operator/` and `__pycache__/` from all transfers.
Run these commands as the IAP operator on the VM:

```sh
cd /tmp/arwc-ot-363
sudo bash prepare-upstream.sh
bash setup-slice.sh
```

Preparation needs Internet access for public product downloads and package
installation. Setup uses the official Editor scaffold, compiler, and download
interface. It adds no build pipeline. Runtime containers have no Internet route.

Setup generates passwords, broker certificates, client keys, and product state
under gitignored `.operator/` and named Docker volumes. Keep them on the VM.
Do not print, commit, archive, or copy that directory. Public qualification
results are the explicit `*-evidence.json` files only.

To update the slice, transfer only changed source files and rerun setup.
The script preserves existing credentials and data. A recreated PLC container
needs another Editor download; restarting the container preserves its program.

## Focused qualification

Run these commands on the VM after setup:

```sh
sudo docker compose run --rm -T tools python /slice/qualify_opcua.py
sudo docker compose run --rm -T tools python /slice/qualify_paths.py
sudo docker compose run --rm -T tools python /slice/qualify_state.py local-priority
sudo docker compose stop io
sudo docker compose run --rm -T tools python /slice/qualify_state.py field-down
sudo docker compose start io
sudo docker compose run --rm -T tools python /slice/qualify_state.py field-up
sudo docker compose restart plc
sudo docker compose run --rm -T tools python /slice/qualify_state.py retained
python3 qualify_editor.py
```

These checks exercise normal operations only. Use the fixture's addresses;
do not direct these clients at golden or participant systems.

Build and setup logs are `/tmp/arwc-ot-{build,setup,upload}.log`. The offline
Editor logs are `/tmp/arwc-ot-offline-compile.log` and `/tmp/arwc-ot-editor-ui.log`.
Do not publish full product logs without checking them for generated credentials.

## Component handoff

[tags.json](tags.json) is the common protocol contract. It defines 13 tags,
types, units, scaling, Modbus offsets/functions, stable OPC UA identities,
access, timestamps, field freshness, ownership, and restart behavior.

Use [main.st](main.st) and the generated Editor project for #364. Use
[configure_fuxa.py](configure_fuxa.py) and the plugin image for #365. Use the
collector, PostgreSQL view, and Grafana provisioning for #366. Use
[dispatcher.py](dispatcher.py) as the limited integration fixture for #367.
Use the pinned Editor and offline checks for #368. Each component can proceed
from this PR's branch without waiting for a merge.

The dispatcher is deliberately small. It accepts only one authenticated topic
and one outlet. It records receipt, dispatch, acceptance, and equipment completion
separately. Interrupted commands require operator reconciliation and never replay
automatically. It is not the complete site service or a substitute for BigRAE.

History preserves raw transport quality and source time. A derived view adds
ingestion time and field quality; trends show gaps for unavailable field data.
Pre-migration samples have unknown ingestion time. FUXA does not use PostgreSQL
as its native DAQ backend: Grafana supplies the maintained historical viewer.

The native OpenPLC OPC UA plugin needs one source correction: call asyncua's
application-URI setter after initialization. [patch_opcua_identity.py](patch_opcua_identity.py)
checks the exact original source hash before applying it. The unmodified image
failed the endpoint/certificate identity check; the corrected image passed.
No replacement OPC UA bridge is required.

Clients use signed, encrypted OPC UA sessions and distinct product users.
The qualification client and Telegraf pin the public server certificate. FUXA
uses its standard plugin certificate handling. Browser services use HTTP only
on the isolated development bridge. Participant HTTPS ingress, workstation
roles, certificate lifecycle, and full-site operations remain downstream work.
