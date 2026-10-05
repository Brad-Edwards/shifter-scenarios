# Private runtime installation package

`polaris-direct/` is the tenant-uploadable launch package for the keyless GCP
Vertex adapter (`panw.polaris-direct`). The broker-backed `polaris` pack and
its `model-needs.json` enrollment are retired with the broker adapter. Build it
with:

```sh
python runtime-pack/build.py --output /tmp/private-runtime-pack/polaris-direct-0.3.0.tar
```

Install the `panw.polaris-direct` adapter with explicit GCP project, region, and
model parameters, upload this pack, then bind the pack's `host` and `directory`
targets to the installed adapter. Pack upload and adapter installation are
tenant content operations; they do not require a core Shifter deployment. An
update to an existing pack needs a new package version and the current digest as
its expected revision; a first registration has no expected digest. The tenant
still needs Private Google Access, a minimally scoped range-host Vertex
identity, the required GCP APIs and selected models enabled, and participant web
egress if public search is part of the workstation task.
For that search capability, enable the administrator-selected GCP host image
profile's public-web option in the pack assignment; leave the directory
profile's option off. The setting applies to new ranges, so reprovision an
already launched range before using it as web-access evidence.
When creating a CTF for this pack, clear the event's "Visible instance OS types"
field (show all), or include `linux`. The form defaults to `kali`, but the
compiled workstation guest declares `os: linux`; leaving the default would
hide the workstation from participants even when the range is ready.

The pack declares the `claude-code` feature on the `a14-kali` host with
destination `/opt/shifter/bin/claude`. Shifter acquires and delivers the binary
at range realization; the host image bind-mounts that directory into the
participant container. No image or pack carries Claude Code.

`polaris-direct/` is the tenant-uploadable RAES 3.5.0 launch wrapper for the separately
installed runtime adapter. It describes the baked container host and directory
guest. The maintained logical scenario, images, content and answers remain in
the owning `../polaris/` tree.

The outer VM network selection is deliberately left open. In RAES 3.5.0,
omitting the infrastructure block preserves this intent; an authored block with
default empty links does not. The provider host can allocate the outer LAN.
Internal container topology is owned by the baked image and private adapter.

Build with the public contracts, without installing Shifter:

```sh
python -m pip install -r runtime-pack/requirements.txt
python runtime-pack/build.py --output /tmp/private-runtime-pack/polaris-direct-0.3.0.tar
python -m pytest runtime-pack/tests/test_package.py -q
```

The build regenerates byte checksums, validates the package, prints its canonical
digest, and produces a deterministic uncompressed tar for tenant upload. Upload
with pack name `polaris-direct`.

Local evidence covers package validation and the archive's reproducibility. It
does not verify deployed images, cloud behavior, participant access or live
model requests. Keep live qualification records in this private repository.

## Direct GCP deployment prerequisite

Before launching this pack on a GCP tenant, set its deployment's
`GCP_RANGE_PRIVATE_GOOGLE_ACCESS` GitHub Environment variable to `true` and run
the tenant's normal deploy workflow. Verify the deployed `platform-runtime`
setting is `true` and a newly created range subnet has Private Google Access
enabled. Changing the variable cannot repair an existing range; destroy and
reprovision it through the normal CTF controls.
