# Private runtime installation package

The default build remains the broker-backed `polaris` pack. For a separate
keyless GCP Vertex variant, run:

```sh
python runtime-pack/build.py --variant direct --output /tmp/private-runtime-pack/polaris-direct.tar
```

The direct archive has pack/scenario identity `polaris-direct` and omits
`model-needs.json`, so it does not enroll the participant in broker spend or
rate limits. The source broker pack is not modified by this build. Install it
with the separate `panw.polaris-direct` adapter and explicit GCP project,
region, and model parameters. Live range qualification is still required.

For the RDP-capable revision, build the `0.2.2` archive from this source and
publish the `0.1.18` adapter distribution as an image by digest. Install the
adapter, upload the new pack revision, then bind the pack's `host` and
`directory` targets to the installed direct adapter. Pack upload and adapter
installation are tenant content operations; they do not require a core Shifter
deployment. An update to an existing pack needs a new package version and the
current digest as its expected revision; a first registration has no expected
digest. The tenant still needs Private Google Access, a minimally scoped
range-host Vertex identity, the required GCP APIs and selected models enabled,
and participant web egress if public search is part of the workstation task.
For that search capability, enable the administrator-selected GCP host image
profile's public-web option in the pack assignment; leave the directory
profile's option off. The setting applies to new ranges, so reprovision an
already launched range before using it as web-access evidence.
When creating a CTF for this pack, clear the event's "Visible instance OS types"
field (show all), or include `linux`. The form defaults to `kali`, but the
compiled workstation guest declares `os: linux`; leaving the default would
hide the workstation from participants even when the range is ready.

`polaris/` is the tenant-uploadable RAES 3.5.0 launch wrapper for the separately
installed runtime adapter. It describes the baked container host and directory
guest. The maintained logical scenario, images, content and answers remain in
the owning `../polaris/` tree.

The outer VM network selection is deliberately left open. In RAES 3.5.0,
omitting the infrastructure block preserves this intent; an authored block with
default empty links does not. Both provider hosts can allocate the outer LAN.
Internal container topology is owned by the baked image and private adapter.

Build with the public contracts, without installing Shifter:

```sh
python -m pip install -r runtime-pack/requirements.txt
python runtime-pack/build.py --output /tmp/private-runtime-pack/polaris-0.2.2.tar
python -m pytest runtime-pack/tests -q
```

The build regenerates byte checksums, validates the package, prints its canonical
digest, and produces a deterministic uncompressed tar for tenant upload. Upload
with pack name `polaris`. Install the adapter manifest separately and bind its
`host` and `directory` targets to the corresponding compiled guests.

`model-needs.json` declares the participant workload's bounded model demand.
Shifter binds it to the verified installed archive digest. It intentionally
contains no provider, account, project, credential, endpoint, or source choice;
tenant administrators select and may later change those sources in Shifter.

Local evidence covers package validation, the actual compiled plan, and pure AWS
and GCP placement with synthetic image profiles. It does not verify deployed
images, cloud behavior, participant access or live model requests. The
adapter image must be delivered to a registry, the participant image rebuilt with the pinned
client, and both cloud deployments qualified before cutover. Keep those records
in this private repository. A locally built SDK wheel is sufficient for this work;
SDK publication is a separate release-model decision.
