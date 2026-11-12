# Bake the private BigRAE images

This is a manual release runbook. It is not a CI/CD pipeline. It turns the three
accepted golden ranges into private, reusable GCE custom images without copying
their participant state or per-range keys.

## Inputs

- A clean checkout of the release commit.
- `gcloud`, Terraform, Docker, and IAP access to the bake project.
- The project ID confirmed by the operator before any cloud command.
- One unused immutable image suffix, such as `event-20261109-02`.

The script refuses an existing final image name. Do not delete and reuse a
released name.

## Bake

Run these commands in three terminals. They are independent and can run at the
same time when project quota permits:

```bash
./cinder-typhoon/build/gcp-images/bake-image.sh training PROJECT_ID event-20261109-02
./cinder-typhoon/build/gcp-images/bake-image.sh keplerops PROJECT_ID event-20261109-02
./cinder-typhoon/build/gcp-images/bake-image.sh arwc PROJECT_ID event-20261109-02
```

Each command does the following:

1. Uses the existing phase deploy script to synchronize the release and build
   its containers on the accepted golden VM.
2. Stops the golden VM only long enough to create a private staging image, then
   starts it again.
3. Starts a disposable bake VM from that staging image.
4. Removes containers, volumes, generated operator material, Docker build
   cache, logs, machine identity, and SSH host keys from the disposable VM.
5. Installs the fixed first-boot, pairing, and readiness helpers.
6. Creates the final private custom image and verifies that its IAM policy has
   no public member.
7. Deletes the disposable VM and staging image. The final image and a local,
   gitignored describe record remain.

The describe records are written under `build/gcp-images/.operator/`. Record
the image name, numeric image ID, source commit, and creation time in the release
handoff.

## First boot

The image-owned service creates fresh range keys and Docker volumes, starts the
phase, and waits for its core services. The runtime adapter then exchanges only
the KeplerOps and ARWC public CA certificates, supplies ARWC's allocated private
address to KeplerOps, verifies all three phases, and writes the participant-host
readiness markers for Training and KeplerOps.

## Release check

Before binding an image, confirm:

- all three image names and numeric IDs match the bake records;
- all three image statuses are `READY`;
- no image IAM policy names `allUsers` or `allAuthenticatedUsers`;
- the binding names the exact custom-image resources, not an image family;
- the Training and KeplerOps readiness manifest digests match the files in the
  release commit.

After the BigRAE range passes the product QA run, hand the same range to human
testers for RDP participant-path testing. Load testing uses fresh BigRAE ranges
from the same three image IDs.
