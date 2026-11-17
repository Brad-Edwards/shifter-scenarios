#!/bin/bash
# Preserve a development disk exactly; never run release-image preparation here.
set -euo pipefail
umask 077
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
action=${1-}
project=${2-}
image=${3-}
destination=${4-}
account=bedwards@paloaltonetworks.com
source_vm=cinder-arwc-ot-compat-363
zone=us-central1-a

fail() { echo "$*" >&2; exit 1; }
[[ $project == prod-mgau4w ]] || fail 'Use the approved project prod-mgau4w explicitly.'
[[ $image =~ ^cinder-arwc-ot-backup-[a-z0-9-]+$ && ${#image} -le 63 && $image != *- ]] \
  || fail 'Use a new cinder-arwc-ot-backup-* machine-image name.'
case "$action" in
  backup) [[ $# == 3 ]] || fail 'usage: golden-vm.sh backup PROJECT BACKUP_NAME' ;;
  restore)
    [[ $# == 4 && $destination =~ ^cinder-arwc-ot-restore-[a-z0-9-]+$ && ${#destination} -le 63 && $destination != *- ]] \
      || fail 'usage: golden-vm.sh restore PROJECT BACKUP_NAME cinder-arwc-ot-restore-NAME'
    ;;
  *) fail 'Choose backup or restore.' ;;
esac
[[ $(gcloud config get-value account 2>/dev/null) == "$account" ]] || fail "Use account $account."
command -v jq >/dev/null
cloud=(gcloud --project="$project" --account="$account")

private_image() {
  "${cloud[@]}" compute machine-images get-iam-policy "$image" --format=json \
    | jq -e 'all(.bindings[]?.members[]?; . != "allUsers" and . != "allAuthenticatedUsers")' >/dev/null \
    || fail 'Cannot establish private machine-image IAM policy.'
}

if [[ $action == backup ]]; then
  existing=$("${cloud[@]}" compute machine-images list --filter="name=$image" --format='value(name)')
  [[ -z $existing ]] || fail 'Backup already exists; choose a new immutable name.'
  status=$("${cloud[@]}" compute instances describe "$source_vm" --zone="$zone" --format='value(status)')
  [[ $status == RUNNING || $status == TERMINATED ]] || fail 'Source must be running or stopped.'
  restart=0
  cleanup() {
    result=$?
    trap - EXIT
    if ((restart)); then
      if ! "${cloud[@]}" compute instances start "$source_vm" --zone="$zone" --quiet; then
        echo 'Source restart failed; restore its running state before other work.' >&2
        result=1
      fi
    fi
    exit "$result"
  }
  trap cleanup EXIT
  if [[ $status == RUNNING ]]; then
    restart=1
    "${cloud[@]}" compute instances stop "$source_vm" --zone="$zone" --quiet
  fi
  "${cloud[@]}" compute machine-images create "$image" \
    --source-instance="$source_vm" --source-instance-zone="$zone" \
    --storage-location=us-central1 \
    --description='Private qualified ARWC OT recovery backup; contains original credentials and identities.'
  if ((restart)); then
    "${cloud[@]}" compute instances start "$source_vm" --zone="$zone" --quiet
    restart=0
  fi
else
  properties=$("${cloud[@]}" compute machine-images describe "$image" --format='json(status,sourceInstance)')
  jq -e --arg source "projects/$project/zones/$zone/instances/$source_vm" \
    '.status == "READY" and (.sourceInstance | endswith($source))' <<<"$properties" >/dev/null \
    || fail 'Backup is not ready or does not belong to the approved source VM.'
  private_image
  existing=$("${cloud[@]}" compute instances list --filter="name=$destination" --format='value(name)')
  [[ -z $existing ]] || fail 'Restore destination already exists; never overwrite it.'
  "${cloud[@]}" compute instances create "$destination" --zone="$zone" \
    --source-machine-image="$image" --machine-type=e2-standard-4 \
    --network-interface=subnet=cinder-arwc-carrier,no-address \
    --no-service-account --no-scopes --tags=cinder-arwc-carrier \
    --labels=scenario=cinder-typhoon,purpose=ot-backup-restore \
    --metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE,serial-port-enable=FALSE \
    --metadata-from-file="startup-script=$root/restore-guest.sh"
  "${cloud[@]}" compute instances describe "$destination" --zone="$zone" \
    --format='table(name,status,networkInterfaces[0].networkIP)'
  echo 'Wait for /var/lib/arwc-ot-backup-restore.ready, then ask QA to check this copy.'
  exit 0
fi
[[ $("${cloud[@]}" compute machine-images describe "$image" --format='value(status)') == READY ]] \
  || fail 'Backup capture has not reached READY.'
private_image
"${cloud[@]}" compute machine-images describe "$image" \
  --format='json(name,id,status,sourceInstance,creationTimestamp,selfLink)'
