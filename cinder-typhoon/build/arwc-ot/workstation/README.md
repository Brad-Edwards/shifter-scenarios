# Cairn Reach engineering desktop

This image supplies Xfce and XRDP, the official OpenPLC Editor 4.3.4, Firefox
ESR, FreeOpcUa client GUI 1.0.2, PostgreSQL tools, Mosquitto clients, and the
native compiler. It runs inside the existing ARWC VM on the supervisory network.
The participant has no host or Docker administration authority.
Native RDP application qualification passed on November 13, 2026 (UTC), including live graphical FBD debugging and maintenance download.
See the [qualification record](evidence/build.json).

## Manual development build

Use `cinder-arwc-ot-compat-363` in `prod-mgau4w`, `us-central1-a`. Copy this
directory to `/opt/arwc-ot-compat/slice/workstation`. Keep the existing shared
`build/participant-host/shifter-participant-readiness` script at
`/opt/arwc-ot-compat/participant-host/shifter-participant-readiness`. Build only on that VM:

```sh
cd /opt/arwc-ot-compat/slice
bash workstation/build-workstation.sh
bash workstation/setup-workstation.sh
```

The first preparation resolves public Debian packages and Python wheels into
`.operator/workstation-assets`. Subsequent builds verify that offline bundle
against the reviewed checksums. The Docker build installs with networking
disabled. It does not use a CI bake pipeline or download packages at participant
runtime. Keep the pinned bundle on the persistent build VM for repeat builds.

For an intentional dependency update, run `prepare_assets.py --refresh` on the
VM. It preserves the previous bundle. Review and update the source locks before
building from the refreshed bundle.

Build output is in `.operator/workstation-image-build.log`. The architecture
preflight checks the native Compose model, membership in the supervisory network, absence
of host/Docker mounts, and the pinned browser sandbox profile. Six deliberate
configuration mutations must be detected. This preflight is not desktop QA.

Setup starts only the engineering container. It creates private development RDP
access and copies the current native project and role-specific connection notes
into its home volume. It preserves an existing participant project. Setup sends
no PLC request and does not download a controller program.

## Use the desktop

The development RDP endpoint is the VM's port `3389`, through approved private
access. User `fieldlink` has the development password in the VM's private
`.operator/workstation-credentials.json`. Do not copy that password into reports
or the QA coordination file. Final range credentials use BigRAE's existing
participant contract during integration, not this development credential.

Use the desktop or Applications menu entries for the HMI, process history,
OpenPLC Editor, OPC UA browser, and Engineering notes. The native controller
project is in `~/CairnReach/controller`. The private connection notes and public
server certificates are in `~/CairnReach/Connections`.

Open the project in OpenPLC Editor. Inspect the native graphical logic and IEC blocks.
Open **Device → Configuration** in the project tree.
Check the Runtime v4 IP address.
Use its Connect button with the engineering role from the private connection notes.
Then use Debugger to read live project variables.
Open **Device → Runtime Status** for native scan and controller statistics.
Build Options supplies compilation and upload actions.
The disabled start/stop control cannot connect the Editor.
The lower “No file selected” area shows documentation.
Coordinate an authorized program download with the active site QA. A download
can reset the controller; it is not a read-only operation.

The OPC UA browser uses the real server, native security policy, and reader
identity listed in the notes. PostgreSQL has the normal `arwc-history` libpq
service and private password file. The published tag register, CSV I/O list,
CSV OPC UA list, and network diagram are in `/usr/share/arwc-ot/`.
Read-only challenge field sheets and engineering references are installed under
`~/CairnReach/Briefs/` from image-owned files. W17 supplies the observation
sheet and instrument reference; W18 supplies the native I/O register and
history-provenance note; W21 supplies the native project handover and
commissioning acceptance note; W25 supplies the bounded operating instruction
and envelope sheet; W29 supplies the allocation export and reconciliation
method; W30 supplies the remote operating plan and handback brief; W33 supplies
the peak-hour operating window, schedule template, commissioning brief, and
bounded dispatcher client. They direct the participant to FUXA, OPC UA, native history,
and OpenPLC's own project, debugger, and Runtime Status views. W21 is
observation-only: do not accept an upload prompt, start or stop the PLC, or force
a variable. W25 permits only its two named local FUXA requests and requires the
second request to restore the normal baseline.
W29 is read-only: keep the corporate tariff, allocation, and paper report
separate from the timestamped `UsableVolumeML` product series.
W30 permits one named dispatcher request after remote selection and requires a
later local FUXA request to restore manual A20/B20. Treat broker receipt,
durable dispatcher state, PLC acceptance, and measured completion separately;
never retry an uncertain result automatically.
W33 uses a completed W30 record to calibrate response delay and gain, then
runs twelve reviewed setpoints through that same dispatcher. It requires a
local FUXA handback and labels the short commissioning run separately from its
one-hour volume and cost projection.

This component also works with the earlier compatibility fixture. Its native
application accounts and project can differ from the completed two-outlet site.
The connection notes identify the installed fixture. The joined utility image
uses the separate operator/viewer roles and complete site project.

## Images, identities, and access

The image contains locked participant/root accounts and public software only.
XRDP creates its private TLS identity at container start. The image reuses the
existing participant readiness executable and its pinned path manifest. Development passwords,
the current private controller project, and per-range connections are injected
after image creation. Do not commit an initialized container or copy its home
volume into a released VM image. The private bake must recreate mutable desktop
state and identities through the integrated range initialization.

The container uses the maintained non-root browser sandbox arrangement. The
Editor selects the native user namespace sandbox with `--disable-setuid-sandbox`.
This removes the setuid helper path; it preserves the browser sandbox. It adds
no host administration capability, does not share host IPC, and does not disable
the browser sandbox. BigRAE continues to own RDP/VPN delivery and participant
credentials. Deferred image delivery in #370 supplies the final pack binding.
Generic credential delivery stays in the platform; ARWC adds no password-copy shim.

## Qualification

Coordinate through root `qa-test.json`. QA must log in through real RDP and use
the native applications: FUXA operation, history, actual graphical PLC logic,
online variables, namespace browsing, historical queries, and authorized project
download. Check these without runtime Internet or external accounts. Confirm
the participant remains separate from host/Docker administration. Port readiness
and developer preflights do not establish participant acceptance.
