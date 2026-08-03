# Physical Lane Materialization

## Status

The repository does not contain an authentic physical-bench implementation or
a vendor digital twin that can replace one. The catalog audit found no reusable
physical or consumer-hardware precedent outside KeplerOps AI Systems. The
existing campaign source provides the labgrid coordinator, client, exporter
configuration, reservation model, evidence schema and verifier, but it does not
provide the devices or the bench-side `keplerops-bench` implementation.

Two operations therefore remain unavailable until real equipment is attached:

- `kep-m08-i`, **Calibration Bench**;
- `kep-m06-m`, **Prepare A Physical Countermeasure**.

There is no software-camera, prerecorded-video, uploaded-image or hand-built
simulation fallback. Disabling these operations also removes proof for
`AML.T0041`, `AML.T0008.001` and `AML.T0008.003`.

## Minimum Bill Of Materials

The smallest development lane is one complete bench. Event capacity is twelve
active benches and two identically configured cold spares, as specified in
`physical-lab-contract.md`.

Each bench requires:

| Quantity | Component | Required property |
| ---: | --- | --- |
| 1 | Raspberry Pi 5 or small x86 controller | Debian-compatible OS, Ethernet, enough USB ports, and a stable hardware identity |
| 1 | Android handset or HDMI display | Presents participant-supplied countermeasure content without software camera substitution |
| 1 | Primary UVC camera | Stable USB serial; manual focus and exposure controls exposed to the controller |
| 1 | Independent wide-angle UVC witness camera | Shows the display/device, primary camera, actuator and liveness display in one frame |
| 1 | Motorized pan/tilt or linear stage | Absolute home sensor, bounded travel and a controller-accessible position reading |
| 1 | Dimmable white light | Bounded intensity command and measured lux feedback |
| 1 | Switched power device | At least four independently addressed outlets for controller, display, cameras and light; labgrid supports SiS-PM or compatible network power resources |
| 1 | Current and temperature monitor | Controller-readable measurements covering the limits in `hardware/evidence-contract.yaml` |
| 1 | Physical emergency stop | Removes actuator and high-current lighting power independently of software |
| 1 | Calibration target | Fixed clean, negative-control and geometry references |
| 1 | Liveness display | Shows the current bench ID and randomized liveness payload in both cameras |

Every USB resource must expose a stable serial or path. Every bench must carry a
printed identifier matching `kepler-bench-NN`; copied identifiers are not
accepted.

## Topology

```text
Kali labgrid client
        |
        | range-scoped coordinator access and opaque reservation token
        v
labgrid coordinator ---------------- operator health and quarantine control
        |
        | gRPC registration; exclusive place ownership
        v
bench exporter host -- SSH/isolated proxy --> keplerops-bench service
        |                                    |-- liveness display
        |-- primary UVC camera               |-- actuator control/home sensor
        |-- witness UVC camera               |-- light control/lux feedback
        |-- switched power                   |-- current/temperature telemetry
        |
        +-- range-scoped WebRTC/TURN media --> Kali browser
```

The coordinator manages inventory and mutual exclusion. Media and device data
do not traverse the coordinator: the workstation reaches exporter resources
through the exporter host or its SSH isolated-mode proxy. TURN credentials,
lease tokens and evidence objects must be range scoped.

## Bench-Side Contract

The controller must provide a non-root `kepler-bench` account accessible with
the provisioned participant SSH identity. Its `keplerops-bench` executable must
implement these bounded commands:

- `status`: return bench ID, exporter resource identities, device firmware,
  model, preprocessing and compute-profile digests, home state, safety state
  and current calibration validity;
- `view`: return the range-scoped primary and witness WebRTC endpoints for the
  active lease;
- `home`: restore actuator and light defaults and confirm absolute sensors;
- `display`: install content into the physical display area and return its
  SHA-256 digest;
- `position` and `light`: apply bounded commands and return measured position,
  lux, current and temperature;
- `capture`: issue or answer the current randomized liveness prompt and capture
  synchronized primary and witness frames;
- `exercise`: perform the clean/change/reset sequence and stream the raw
  evidence archive defined by `hardware/evidence-contract.yaml` to stdout;
- `sanitize`: remove participant content and lease media, home the bench, run
  clean and negative controls, and return the final state.

`exercise` must use the actual UVC devices and measured telemetry. It must not
accept frame paths, image uploads or caller-supplied measurement values.

## Materialization Procedure

1. Assemble one complete bench and record every USB serial, USB path, power
   outlet, controller address, actuator limit and sensor calibration.
2. Install the pinned labgrid exporter from
   `template/hardware/component-lock.env` on the controller. Install the
   bench-side service and configure SSH key-only access for `kepler-bench`.
3. Copy `template/hardware/exporter.env.example` to an operator-owned bench
   environment file outside the scenario tree. Populate only observed hardware
   identities; do not invent placeholder values.
4. Render `template/hardware/exporter.yaml.example` with that environment and
   start `template/hardware/compose.exporter.yaml` on the controller. Use
   labgrid isolated exporter mode when the range cannot directly route to the
   controller.
5. Start the range-side coordinator and client with
   `template/scripts/start-hardware.sh`. Reconcile the declared places from
   `template/hardware/pool.yaml` only after each corresponding exporter is
   online.
6. Bind the participant workstation to the hardware network, install
   `/etc/labgrid/participant-remote.yaml`, provision its read-only bench SSH
   identity, and configure range-scoped WebRTC/TURN access.
7. Set `KEPLEROPS_HARDWARE_GATE14_PLACE` to the real development bench and run
   `template/baseline/hardware-place.sh`. Then run
   `template/baseline/hardware-participant.sh` from the normal workstation
   path.
8. Run `kep-m08-i` exactly as written in `modules/m08/qa.md`. Admit the
   operation only when the normal calibration report passes
   `modules/m08/validate.sh kep-m08-i` and all negative controls fail.
9. Run `kep-m06-m` exactly as written in `modules/m06/qa.md`. Admit the
   operation only when the physical-evaluation report passes
   `modules/m06/validate.sh kep-m06-m` and all negative controls fail.
10. Repeat the clean and qualifying path on a second independently assembled
    bench before treating the lane as reproducible. Build the remaining active
    and spare benches from the same locked component and calibration records.

## Admission Evidence

Neither operation appears in a playtest assignment until all of the following
are retained in the operator evidence set:

- exporter inventory showing the declared real resources online;
- successful exclusive reservation, acquisition and release from Kali;
- synchronized fresh primary and witness frames with randomized liveness;
- measured actuator, home-sensor, lux, current and temperature telemetry;
- exact device, model, preprocessing and compute-profile digests;
- accepted clean, changed and reset evidence archives;
- rejection of uploaded images, software cameras, prerecorded and stale media,
  missing witness frames, out-of-bounds commands and cross-lease evidence;
- successful sanitization with no prior content or media left on the bench;
- watchdog, emergency-stop, exporter-disconnect and replacement-lease proof;
- equivalent clean and qualifying results from two different benches.

At event scale, the final gate also requires twelve active and two spare places
to pass `template/scripts/health-hardware.sh` and a queue rehearsal to meet the
wait and occupancy limits in `physical-lab-contract.md`.

## Source Basis

The design uses labgrid's native coordinator, exporter, client, RemotePlace,
USB video and switched-power resource model. Labgrid provides inventory,
availability tracking, exclusive places and remote access; it does not supply
the physical devices, WebRTC service, verifier model or bench-side control
application. Those remain concrete deployment obligations rather than scenario
simulations.
