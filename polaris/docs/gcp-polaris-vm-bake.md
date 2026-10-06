# Baking the Polaris host image on GCP

This runbook bakes the `polaris-vm` GCE custom image: the Debian Docker host that
runs the Polaris Compose stack, including the `a14-kali` participant container.
It is the procedure that produced `shifter-polaris-vm-1790559014` on 2026-09-28.
Pack bindings reference the resulting image by exact name, so a binding and its
image form one compatibility set (see
[the operator runbook](gcp-shifter-operator-runbook.md)).

The bake files live in [`../packer/gcp/`](../packer/gcp/):

| File | Purpose |
| --- | --- |
| `polaris-vm.pkr.hcl` | Packer template for the host image |
| `variables.pkr.hcl`, `locals.pkr.hcl`, `packer.pkr.hcl` | Shared variables, locals and plugin requirements |
| `scripts/polaris/host-setup.sh` | Installs Docker and the Google Cloud SDK; moves the host sshd to port 2222 |
| `scripts/polaris/verify-stack.sh` | Fetches and verifies the stack archive, then builds and starts every Compose service before capture |
| `scripts/common/cleanup.sh` | Pre-capture cleanup |
| `files/polaris_splice_credential.py` | Splice-credential helper installed at `/opt/polaris/libexec` |

`verify-stack.sh` extracts the archive at `/opt/polaris/scenario-dev`, so the
stack lands at `/opt/polaris/scenario-dev/polaris/build`. That directory is the
runtime adapter's contract: its range bootstrap runs Compose there, and Compose
derives the `build_*` project and network names from it. Extracting anywhere
else still bakes and runs, but ranges then fail to provision.

## Inputs

- A tenant GCP project with the image-build network and subnetwork created by
  the platform Terraform (`shifter-<environment>-image-build`), with Cloud NAT
  and an IAP SSH ingress rule.
- The tenant's image-build service account
  (`shifter<environment>-packer@<project>.iam.gserviceaccount.com`). The
  image-build IAP ingress rule targets this account, so the builder must run as
  it.
- Packer 1.11 or later, and `gcloud` authenticated as an operator who can create
  instances and images in the project and use IAP.
- A clean checkout of this repository at the revision to bake. The stack archive
  is `polaris/build/build-v1.tar.gz` from that revision.

## 1. Stage the stack archive

Verify the archive against its sidecar digest:

```sh
(cd polaris/build && sha256sum -c build-v1.tar.gz.sha256)
```

Create the stack bucket if it does not exist, upload the archive, and grant the
builder read access:

```sh
PROJECT=<tenant-project>
BUILDER=shifter<environment>-packer@${PROJECT}.iam.gserviceaccount.com
BUCKET=${PROJECT}-polaris-stack
gcloud storage buckets create "gs://${BUCKET}" --project "${PROJECT}" \
  --location us-central1 --uniform-bucket-level-access --public-access-prevention
gcloud storage cp polaris/build/build-v1.tar.gz \
  "gs://${BUCKET}/polaris/stack/polaris-stack.tar.gz" --project "${PROJECT}"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member "serviceAccount:${BUILDER}" --role roles/storage.objectViewer
```

Record the object generation; the bake pins it:

```sh
gcloud storage objects describe "gs://${BUCKET}/polaris/stack/polaris-stack.tar.gz" \
  --format 'value(generation)'
```

## 2. Bake

```sh
cd polaris/packer/gcp
packer init .
packer build -only=googlecompute.polaris-vm \
  -var "project_id=${PROJECT}" \
  -var "zone=us-central1-a" \
  -var "network=shifter-<environment>-image-build" \
  -var "subnetwork=shifter-<environment>-image-build" \
  -var "service_account_email=${BUILDER}" \
  -var "image_prefix=shifter" \
  -var "source_revision=$(git rev-parse HEAD)" \
  -var "machine_type=e2-standard-8" \
  -var "use_internal_ip=true" \
  -var "polaris_stack_bucket=${BUCKET}" \
  -var "polaris_stack_sha256=$(awk '{print $1}' ../../build/build-v1.tar.gz.sha256)" \
  -var "polaris_stack_generation=<generation>" \
  .
```

`source_revision` must be the full 40-character commit of the checkout. The bake
takes about 40 minutes. It fails closed if the archive digest does not match, the
Compose configuration is invalid, any image fails to build or pull, or any of the
17 services is not running before capture. The result is
`shifter-polaris-vm-<timestamp>` in family `shifter-polaris-vm`. Packer writes
`polaris-vm-manifest.json` locally; do not commit it.

Delete the staged archive object once the image is verified.

## 3. Record the readiness digest

The binding's readiness digest is the SHA-256 of the readiness document from the
same revision:

```sh
sha256sum polaris/build/a14/participant-readiness.json
```

Record the new host image name and readiness digest in
[`runtime-pack/BINDING.md`](../../runtime-pack/BINDING.md) and
`runtime-pack/polaris-direct.binding.json` in the same change.

## 4. Cold-boot the image

Boot a throwaway VM from the image with no service account, on the image-build
subnetwork, tagged for the image-validation IAP rule, with a temporary key for
`hostadmin`:

```sh
ssh-keygen -q -t ed25519 -N "" -f /tmp/polaris-coldboot -C hostadmin
echo "hostadmin:$(cat /tmp/polaris-coldboot.pub)" > /tmp/polaris-coldboot.keys
gcloud compute instances create polaris-coldboot --project "${PROJECT}" \
  --zone us-central1-a --machine-type e2-standard-8 \
  --image <image-name> --boot-disk-size 220GB --boot-disk-type pd-balanced \
  --subnet shifter-<environment>-image-build --no-address \
  --no-service-account --no-scopes --tags shifter-validation \
  --metadata-from-file ssh-keys=/tmp/polaris-coldboot.keys
```

Connect on the management port through IAP and confirm that all 17 containers
are up, port 3389 is listening, and the installed readiness document matches the
digest from step 3:

```sh
ssh -i /tmp/polaris-coldboot -p 2222 \
  -o "ProxyCommand=gcloud compute start-iap-tunnel polaris-coldboot 2222 --listen-on-stdin --zone us-central1-a --project ${PROJECT}" \
  hostadmin@polaris-coldboot \
  'sudo docker ps --format "{{.Names}} {{.Status}}"; sudo ss -ltn; sudo docker exec a14-kali sha256sum /usr/local/share/shifter/participant-readiness.json'
```

Delete the VM and the temporary key afterwards.

## 5. Copy to other tenant projects

A tenant project can take a copy instead of rebaking:

```sh
gcloud compute images create <image-name> --project <target-project> \
  --source-image <image-name> --source-image-project "${PROJECT}" \
  --family shifter-polaris-vm --storage-location us
```

## Replacing or deleting an image

Bindings reference the image by exact name. Before deleting or replacing a
`polaris-vm` image in any project, list the Polaris pack bindings on every tenant
that uses the project and confirm none references it. Deleting a referenced image
does not affect running ranges, but every new range build and every rebuild fails
with "The referenced image resource cannot be found."
