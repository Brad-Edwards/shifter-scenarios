#!/bin/bash
set -euo pipefail
project=${1:?Usage: create-test-vm.sh GCP_PROJECT_ID}
[[ $project =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || exit 2
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
zone=us-central1-a
golden=cinder-arwc-golden
instance=cinder-arwc-ot-compat-363
subnet=cinder-arwc-carrier

account=$(gcloud auth list --filter=status:ACTIVE --format='value(account)')
[[ -n $account ]] || { echo 'An active GCP account is required.' >&2; exit 1; }
network=$(gcloud compute instances describe "$golden" --project="$project" --zone="$zone" \
  --format='value(networkInterfaces[0].network)')
[[ $network == "https://www.googleapis.com/compute/v1/projects/$project/global/networks/cinder-arwc-golden" ]] || {
  echo 'The ARWC golden network does not match the requested project.' >&2; exit 1;
}
echo "Account: $account; project: $project; VPC: $golden; test VM: $instance"
gcloud compute instances create "$instance" \
  --project="$project" --zone="$zone" \
  --machine-type=e2-standard-4 --boot-disk-size=80GB --boot-disk-type=pd-balanced \
  --image=debian-12-bookworm-v20260921 --image-project=debian-cloud \
  --subnet="$subnet" --no-address --no-service-account --no-scopes \
  --tags=cinder-arwc-carrier \
  --labels=scenario=cinder-typhoon,segment=arwc,purpose=ot-compatibility,issue=363 \
  --metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE,serial-port-enable=FALSE \
  --metadata-from-file="startup-script=$root/bootstrap-test-vm.sh" \
  --shielded-secure-boot --shielded-vtpm --shielded-integrity-monitoring
