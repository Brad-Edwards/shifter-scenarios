# Bake the private ARWC OT image

Use the approved development project `prod-mgau4w`, account
`bedwards@paloaltonetworks.com`, and zone `us-central1-a`.
The source VM is `cinder-arwc-ot-compat-363` in the golden range VPC.
This procedure uses the existing manual bake script. It adds no CI/CD pipeline.

This release work is deferred. Complete OT development and QA on the existing
golden-VPC VMs first. VM bakes follow later challenge design and testing.
The current OT development work does not design challenges.

## Fix the release inputs

Finish desktop and joined operating QA. Record compiler load, native PLC timing,
and the shared-host resource limits. Preserve the qualified legacy image names.

On the development VM, from `/opt/arwc-ot-compat/slice`, capture the cached images:

```sh
python3 image/capture_inventory.py --output .operator/runtime-inventory.json
```

Copy only that credential-free file to `image/runtime-inventory.json` in the
release source. Commit the inventory with all required component source.
The bake accepts an explicit committed ref; it excludes working-tree changes.
A prepared feature branch can be used before its PR is merged.

The inventory must describe the final qualified desktop image, including its
standard D-Bus package and service. Do not capture an earlier image tag while
QA relies on a temporary patch in an older container.

## Make the private image

Coordinate the source VM stop/start with QA first. Run the manual bake from
the repository root, with an immutable source commit and a new image suffix:

```sh
bash cinder-typhoon/build/gcp-images/bake-image.sh \
  arwc prod-mgau4w ot-RELEASE_SUFFIX \
  cinder-arwc-ot-compat-363 SOURCE_COMMIT
```

Use lowercase GCE name components for the suffix. The result is
`cinder-arwc-ot-RELEASE_SUFFIX`.

OT mode copies the development disk without deploying to the existing golden.
It restarts the source VM after the copy. It creates a temporary private bake VM
and installs only the committed production source there. The temporary clone
removes development state and checks its cached software identities.
The bake trap deletes the temporary VM and stage image and restarts the source
if an intermediate step fails. Source images and qualified legacy images stay intact.

The guarded preparation script runs only on a temporary `cinder-arwc-bake-*` VM.
It removes all containers and mutable volumes, operator directories, private
projects, development homes, logs, and identities. It keeps the qualified OCI
images and production source. It fails if an unhandled operator home remains.
Never run destructive preparation on the development VM.

## Qualify and bind the image

Create a fresh private qualification VM from the new image in the approved VPC.
Boot without runtime package downloads. Verify image-owned initialization,
fresh product identities, and the shared native participant readiness contract.
Use a second fresh instance to confirm identities differ. Remove temporary
qualification resources after the checks.

Publish the exact image and pack identity through BigRAE's existing image
profile and env-pack contracts. Add the ARWC desktop account and RDP surface;
preserve the existing confined connector SSH entry. Keep the adapter limited
to its existing fixed pairing and verification actions.

Use QA through root `qa-test.json` for the participant OpenVPN path first,
then the RDP path and full normal-operation checklist in the OT plan.
Verify restart preserves settings, physical state, history, the dispatcher
journal, and participant project edits. A fresh range resets these through
new first-boot state. Do not migrate challenge or incident content in this work.

Copy the qualified private image to `prod-2hl4ce` through the existing approved
GCP image-copy procedure. Preserve the original in `prod-mgau4w` and confirm
both images remain private. Keep the old release available for rollback.
