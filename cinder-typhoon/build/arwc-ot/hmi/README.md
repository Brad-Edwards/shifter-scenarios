# Cairn Reach operator HMI

This is a native FUXA 1.3.5 project for the two-outlet site controller. It uses
the qualified OPC UA driver and the site's 50-tag register. The PLC owns control
decisions. PostgreSQL owns measurement history.

## Install on the development VM

Use the existing `cinder-arwc-ot-compat-363` VM in `prod-mgau4w`. First complete
the [site setup](../site/README.md). Copy this directory and the updated
`project_config.py` into `/opt/arwc-ot-compat/slice`, then run:

```sh
cd /opt/arwc-ot-compat/slice
bash hmi/setup-hmi.sh
python3 hmi/test_project.py
```

Import replaces the FUXA project, discovers the actual OPC UA namespace, and
restores the encrypted device connection. It preserves existing passwords and
adds separate operator and viewer passwords. Rerunning the site fixture import
replaces these screens; rerun HMI setup afterwards.

Use the existing approved private access method. FUXA is available on the VM's
supervisory bridge at `172.29.63.21:1881`. It has no public port. Credentials
remain in the VM's `.operator/credentials.json`: `fuxa_operator` for `operator`,
`fuxa_viewer` for `viewer`, and `fuxa` for configuration user `admin`. Do not
copy credentials into reports or the QA coordination file.

## Operate the site

Start with the overview. It shows measured reservoir level and usable volume,
both outlet measurements, actual mode, control owner, and field-data quality.
Open either outlet faceplate for permissive, motion, target, and fault status.

On Site controls, enter both proposed manual positions and the proposed total
automatic flow. Press Enter in each numeric field. Select the proposed mode,
then select **Apply complete request**. The PLC consumes the new sequence and
either accepts or rejects the complete request. Compare the accepted settings
and decision with the measured positions and flows. An accepted HMI request
removes remote selection. Select remote again when dispatcher control is needed.

**OPERATOR STOP** disarms motion. Clearing stop does not resume an old request.
Check the permissives and apply a fresh request. **Reset PLC travel faults**
generates a reset pulse for both outlets. It is separate from alarm acknowledgement.

Use the native alarm indicator in the header for current alarms, acknowledgement,
and return-to-normal history. **Process history** opens the existing Grafana
PostgreSQL view. Expanded collection and both-outlet history belong to #366.

## Access and quality

The operator can issue requests and acknowledge alarms. The viewer can read
the screens. Configuration needs the administrator account. These are native
FUXA groups and permissions; there is no additional authorization service.

Field-data quality is separate from the OPC UA connection. An unavailable field
link must show **UNAVAILABLE**, inhibit operation through PLC permissives, and
raise the field alarm. Loss of the PLC connection must retain the native FUXA
connection warning and must not be presented as healthy live data.

## QA handoff

Coordinate only through the repository-root `qa-test.json`. Use normal browser
affordances, the real operator/viewer accounts, and this operating path. Check
navigation, units, proposed/accepted/measured values, manual and automatic modes,
local priority, stop/reset, alarms, quality, and the history link. Record product
failures and the visible result. This is component QA; final participant ingress
and connected utility acceptance remain downstream.
