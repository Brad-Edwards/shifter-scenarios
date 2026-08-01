# Physical Lab Contract

## Required Capability

The physical branch performs real sensor and countermeasure operations for
`kep-m08-i` and `kep-m06-m`. It is not a video stream of a simulation and does
not accept uploaded captures. A participant leases, observes and changes an
actual remote environment while the actual verifier consumes fresh camera
frames.

## Bench BOM

Each interchangeable labgrid place contains:

- Raspberry Pi 5 or small x86 controller running a pinned labgrid exporter;
- one commercially available Android handset or HDMI consumer display that
  presents participant countermeasure content;
- one UVC camera with locked focus/exposure controls available to the verifier;
- motorized pan/tilt or linear position control with absolute home sensors;
- addressable/dimmable white light with measured lux feedback;
- remotely switched power for controller, display/handset, camera and light;
- an independent wide-angle witness camera showing the display/device,
  actuator and primary camera in one live frame;
- printed bench ID and randomized liveness display visible to both cameras;
- current/temperature sensing and a physical travel limit/emergency stop; and
- a calibration target plus known clean and negative-control patterns.

Minimum event capacity is 12 operational places plus two cold spares. Final
count is increased if load rehearsal cannot keep p95 reservation wait below ten
minutes and p95 complete calibration-plus-countermeasure occupancy below 75
minutes for the expected full-catalog cohort.

## Control And Media Protocol

- labgrid owns reservation, exclusive place acquisition, exporter resources and
  release. The participant uses the normal labgrid client from Kali.
- A range-scoped opaque lease token addresses one place and cannot enumerate
  another range's lease, media or telemetry.
- Actuator commands use documented bounded units and travel/rate limits.
- Primary and witness live video use WebRTC with range-scoped TURN credentials;
  the verifier consumes the primary UVC stream directly, not a participant
  upload.
- Every capture binds lease, bench, randomized challenge, monotonic sequence,
  timestamp, primary/witness frame hashes, actuator/light telemetry, model and
  preprocessing digests, decision and participant pattern digest.
- A challenge is issued after reservation and must be visibly satisfied by a
  fresh position/light/display change before the evaluation window closes.

## Safety And Containment

- No laser, high-intensity light, hazardous material, uncontrolled heat,
  unrestricted motor command or public camera is permitted.
- Participant content is constrained to the display/printable-pattern area and
  scanned only for file safety, not attack semantics.
- Actuators enforce hardware and software limits; watchdog returns the bench to
  home and cuts motor/light power on control loss.
- Video contains only range equipment. It is retained for the active attempt
  and QA evidence window, then deleted according to the range lifecycle.
- Physical emergency stop and remote administrator power-off are management
  safety controls, never participant proof.

## Calibration And Countermeasure Acceptance

`kep-m08-i` requires:

1. exclusive lease and current randomized liveness challenge;
2. clean baseline at home position and standard light;
3. participant-commanded position and light changes within published ranges;
4. synchronized primary/witness frames and telemetry; and
5. verifier output for each fresh state.

`kep-m06-m` additionally requires:

1. participant-created pattern digest shown on the actual display/handset;
2. one clean control and qualifying treated capture under at least three
   randomized position/light combinations;
3. the published localized size/placement bound;
4. target model effect across the required capture fraction while clean
   utility controls remain; and
5. exact model, preprocessing and pattern continuity.

Direct uploaded inference, prerecorded video, software camera, stale frame,
management actuation and another lease's media fail before model scoring.

## Reset, Sanitization And Failure

Failed-attempt reset stops capture, removes participant content, homes
actuators, restores standard light, clears lease-scoped media, power-cycles the
display when required, runs clean/negative controls and releases the place.
A successful report remains in the range's ordinary evaluation records while
the bench itself is sanitized identically.

A bench failing witness video, telemetry, liveness, home sensors, clean controls
or safety checks is quarantined. The participant receives a replacement lease
and their operation attempt is not charged. If event capacity cannot provide a
real place, the physical operations are unavailable and their ATLAS rows remain
unproved; there is no software fallback.

## Build And Load Proof

Before candidate acceptance:

- the exact BOM, firmware, exporter, verifier and calibration digests are in
  `component-lock.yaml`;
- two different benches produce equivalent clean and qualifying results;
- replay/upload/cross-range/expired-lease negative tests pass;
- disconnect, watchdog, emergency-stop and replacement-lease behavior pass;
- sanitization proves no prior participant pattern or media remains; and
- a 12-place queue rehearsal satisfies the wait and occupancy targets.
