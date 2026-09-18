# Private runtime installation package

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
python runtime-pack/build.py --output /tmp/private-runtime-pack/polaris-0.2.0.tar
python -m pytest runtime-pack/tests -q
```

The build regenerates byte checksums, validates the package, prints its canonical
digest, and produces a deterministic uncompressed tar for tenant upload. Upload
with pack name `polaris`. Install the adapter manifest separately and bind its
`host` and `directory` targets to the corresponding compiled guests.

Local evidence covers package validation, the actual compiled plan, and pure AWS
and GCP placement with synthetic image profiles. It does not verify deployed
images, cloud behavior, participant access or live model requests. The
adapter image must be delivered to a registry, the participant image rebuilt with the pinned
client, and both cloud deployments qualified before cutover. Keep those records
in this private repository. A locally built SDK wheel is sufficient for this work;
SDK publication is a separate release-model decision.
