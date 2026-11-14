# Private ARWC OT image

Issue #370 is deferred until after later challenge design and testing.
The current work qualifies normal OT on the existing golden-VPC VMs.
The following design records the prepared future image implementation.
Build from committed, reviewable source and qualified cached container images.
Keep the current development VM and qualified legacy images intact.
Do not add a CI/CD build pipeline.

## Preparation and privacy

Create a temporary private clone for image preparation. Copy the committed
production source into its canonical `/opt/cinder-typhoon` layout. Verify the
cached image identifiers against the qualified set before preparing the image.
Run destructive sanitization only on that temporary clone.

Remove all containers, mutable volumes, operator directories, private projects,
connection notes, development logs, shell histories, host identities, and old
initialization markers. Remove the separate compatibility development trees.
Keep the qualified software images, source, public notices, and shared readiness
executable. Never publish the initialized development desktop or its home volume.
Store images only in the approved private GCP projects. Keep the legacy release
available for rollback. Copy qualified images between projects; preserve the source.

## Image-owned initialization

Use the image's first-boot service for fixed application initialization.
BigRAE continues to own provisioning, participant identity, password delivery,
VPN, RDP, readiness enforcement, and range lifecycle. The env-pack declares the fixed image mappings. The scenario adapter keeps
its existing peer pairing and verification responsibilities.

Reuse the qualified component preparation code. Generate fresh product passwords
and trust material within each range. Run the official offline Editor CLI as the
existing participant inside the engineering container. This avoids a second host
Editor installation and avoids running a browser application as root.
Create a fresh scaffold, apply the authored FBD/IEC model, and download it through
the native controller management interface. Deliver the matching project and
private role connections to the participant home.

Prepare the native HMI, historian, dispatcher, and read-only IT bridge before
publishing readiness. Write initialization completion only after every step
succeeds. Write the host readiness marker after the participant surface is usable.
Use the existing shared readiness executable and the pinned path manifest.
Do not substitute a port-only check for participant readiness or acceptance.

## Restart and reset

On an ordinary restart, start the existing services and state. Preserve product
identities, the downloaded program, retained controller settings, physical state,
history, the dispatcher journal, and the participant home. Do not upload a new
program, reset a participant project, or replay an unfinished command.
The controller returns disarmed as defined by the qualified operating contract.

A fresh BigRAE range supplies reset: initialize new mutable state and identities
from the same immutable image. Keep the retained-state and fresh-range cases
separate in the operating runbook and qualification record.

## Qualification

Use a fresh private range to verify boot without package downloads, native
readiness, and participant credentials. Use QA through root `qa-test.json` for
VPN and RDP access and the normal-operation walkthrough in the OT plan.
Verify restart, recovery, and the measured shared-host resource bounds.
Keep incidents, vulnerabilities, challenges, and scoring outside this work.

The native authored-account path must target the verified participant container
when it installs the password published for RDP. The current platform path
installs it on the host. Track that generic fix in the platform repository;
do not add a scenario password copy for ARWC. Image preparation and component
QA can continue while that fix proceeds.
