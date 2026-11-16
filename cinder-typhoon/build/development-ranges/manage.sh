#!/usr/bin/env bash
set -euo pipefail
umask 077

root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
pack_root=$(CDPATH='' cd -- "$root/../.." && pwd)
scenario_root=${CINDER_DEV_SCENARIO_ROOT:-$pack_root}
scenario_root=$(CDPATH='' cd -- "$scenario_root" && pwd)
# shellcheck source=targets.sh disable=SC1091
source "$root/targets.sh"
archive=
cleanup() {
  [[ -z $archive ]] || rm -f -- "$archive"
}
trap cleanup EXIT

action=${1-}
target=${2-}
project=${3-}
shift $(( $# >= 3 ? 3 : $# ))

case $action in
  preserve|provision|describe|ssh|run|sync|reset|desktop-login|bind-peer|allow-peer) ;;
  *)
    echo 'usage: manage.sh ACTION TARGET GCP_PROJECT [ARGUMENTS]' >&2
    echo 'ACTION: preserve, provision, describe, ssh, run, sync, reset, desktop-login, bind-peer, or allow-peer' >&2
    exit 2
    ;;
esac

[[ $project =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || {
  echo 'GCP_PROJECT must be an explicit canonical project ID.' >&2
  exit 2
}
cinder_load_development_target "$target"
cinder_validate_development_target || {
  echo 'The target map does not describe a safe development instance.' >&2
  exit 1
}

gcloud_bin=${GCLOUD_BIN:-gcloud}
zone=${CINDER_GCP_ZONE:-us-central1-a}
required_account=${CINDER_GCP_ACCOUNT:-bedwards@paloaltonetworks.com}
active_account=$($gcloud_bin auth list --filter=status:ACTIVE --format='value(account)')
[[ $active_account == "$required_account" ]] || {
  echo "Active gcloud account must be $required_account." >&2
  exit 1
}

describe_instance() {
  $gcloud_bin compute instances describe "$CINDER_DEV_INSTANCE" \
    --project="$project" --zone="$zone" \
    --format='table(name,status,machineType.basename(),networkInterfaces[0].networkIP,labels.segment,labels.purpose)'
}

verify_managed_instance() {
  purpose=$($gcloud_bin compute instances describe "$CINDER_DEV_INSTANCE" \
    --project="$project" --zone="$zone" --format='value(labels.purpose)')
  segment=$($gcloud_bin compute instances describe "$CINDER_DEV_INSTANCE" \
    --project="$project" --zone="$zone" --format='value(labels.segment)')
  [[ $purpose == development-range && $segment == "$CINDER_DEV_TARGET" ]] || {
    echo 'The instance is not the managed development target.' >&2
    return 1
  }
}

wait_for_ready() {
  for attempt in $(seq 1 120); do
    if $gcloud_bin compute ssh "$CINDER_DEV_INSTANCE" \
        --project="$project" --zone="$zone" --tunnel-through-iap \
        --command="test -f '$CINDER_DEV_READY_MARKER'" >/dev/null 2>&1; then
      describe_instance
      return 0
    fi
    [[ $attempt != 120 ]] || {
      echo "Development VM did not publish $CINDER_DEV_READY_MARKER." >&2
      return 1
    }
    sleep 5
  done
}

ensure_no_service_account() {
  account=$($gcloud_bin compute instances describe "$CINDER_DEV_INSTANCE" \
    --project="$project" --zone="$zone" --format='value(serviceAccounts[0].email)')
  if [[ -n $account ]]; then
    status=$($gcloud_bin compute instances describe "$CINDER_DEV_INSTANCE" \
      --project="$project" --zone="$zone" --format='value(status)')
    if [[ $status == RUNNING ]]; then
      $gcloud_bin compute instances stop "$CINDER_DEV_INSTANCE" \
        --project="$project" --zone="$zone" --quiet
    fi
    $gcloud_bin compute instances set-service-account "$CINDER_DEV_INSTANCE" \
      --project="$project" --zone="$zone" --no-service-account --no-scopes
    if [[ $status == RUNNING ]]; then
      $gcloud_bin compute instances start "$CINDER_DEV_INSTANCE" \
        --project="$project" --zone="$zone" --quiet
    fi
  fi
  [[ -z $($gcloud_bin compute instances describe "$CINDER_DEV_INSTANCE" \
    --project="$project" --zone="$zone" --format='value(serviceAccounts[0].email)') ]] || {
    echo 'Development VM still has a service account.' >&2
    return 1
  }
}

ensure_boot_disk_capacity() {
  [[ $target == fieldlink ]] || return 0
  verify_managed_instance
  boot_disk=$($gcloud_bin compute instances describe "$CINDER_DEV_INSTANCE" \
    --project="$project" --zone="$zone" --format='value(disks[0].source.basename())')
  [[ $boot_disk == "$CINDER_DEV_INSTANCE" ]] || {
    echo 'The boot disk is not the expected development disk.' >&2
    return 1
  }
  disk_size=$($gcloud_bin compute disks describe "$boot_disk" \
    --project="$project" --zone="$zone" --format='value(sizeGb)')
  [[ $disk_size =~ ^[1-9][0-9]*$ ]] || return 1
  if ((disk_size < 100)); then
    $gcloud_bin compute disks resize "$boot_disk" \
      --project="$project" --zone="$zone" --size=100GB --quiet
  fi
}

provision() {
  if $gcloud_bin compute instances describe "$CINDER_DEV_INSTANCE" \
      --project="$project" --zone="$zone" >/dev/null 2>&1; then
    verify_managed_instance
    ensure_no_service_account
    ensure_boot_disk_capacity
    wait_for_ready
    return
  fi

  $gcloud_bin compute machine-images describe "$CINDER_DEV_MACHINE_IMAGE" \
    --project="$project" --format='value(status)' | grep -qx READY

  startup="$root/guest/$CINDER_DEV_TARGET-first-boot.sh"
  $gcloud_bin compute instances create "$CINDER_DEV_INSTANCE" \
    --project="$project" --zone="$zone" \
    --source-machine-image="projects/$project/global/machineImages/$CINDER_DEV_MACHINE_IMAGE" \
    --network-interface="network=$CINDER_DEV_NETWORK,subnet=$CINDER_DEV_SUBNET,private-network-ip=$CINDER_DEV_PRIVATE_IP,no-address" \
    --no-service-account --no-scopes \
    --tags="$CINDER_DEV_TAG,$CINDER_DEV_INSTANCE" \
    --labels="scenario=cinder-typhoon,segment=$CINDER_DEV_TARGET,purpose=development-range,managed-by=shifter-scenarios" \
    --metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE,serial-port-enable=FALSE \
    --metadata-from-file="startup-script=$startup"
  ensure_no_service_account
  ensure_boot_disk_capacity
  wait_for_ready
}

case $action in
  preserve)
    [[ $target == fieldlink ]] || {
      echo 'ARWC is already preserved in its qualified machine image.' >&2
      exit 2
    }
    if $gcloud_bin compute machine-images describe "$CINDER_DEV_MACHINE_IMAGE" \
        --project="$project" >/dev/null 2>&1; then
      echo "$CINDER_DEV_MACHINE_IMAGE already exists; it was not replaced."
      exit 0
    fi
    $gcloud_bin compute instances describe "$CINDER_DEV_SOURCE_INSTANCE" \
      --project="$project" --zone="$zone" --format='value(status)' | grep -qx RUNNING
    $gcloud_bin compute machine-images create "$CINDER_DEV_MACHINE_IMAGE" \
      --project="$project" \
      --source-instance="$CINDER_DEV_SOURCE_INSTANCE" \
      --source-instance-zone="$zone" \
      --description='Preserved FieldLink golden before native application replatforming'
    $gcloud_bin compute machine-images describe "$CINDER_DEV_MACHINE_IMAGE" \
      --project="$project" --format='table(name,status,creationTimestamp)'
    ;;
  provision)
    provision
    ;;
  describe)
    describe_instance
    ;;
  ssh)
    verify_managed_instance
    $gcloud_bin compute ssh "$CINDER_DEV_INSTANCE" \
      --project="$project" --zone="$zone" --tunnel-through-iap
    ;;
  run)
    [[ $# -gt 0 ]] || {
      echo 'run requires one remote command string.' >&2
      exit 2
    }
    verify_managed_instance
    $gcloud_bin compute ssh "$CINDER_DEV_INSTANCE" \
      --project="$project" --zone="$zone" --tunnel-through-iap \
      --command="$*"
    ;;
  sync)
    verify_managed_instance
    archive=$(mktemp "/tmp/cinder-$target-source.XXXXXX.tar.gz")
    if [[ $target == fieldlink ]]; then
      tar -C "$pack_root" -czf "$archive" \
        --exclude='*/.operator' --exclude='*/__pycache__' \
        .dockerignore build/development-ranges build/keplerops \
        assets/keplerops/opening \
        assets/keplerops/registry \
        assets/keplerops/staff \
        assets/keplerops/identity-api \
        assets/keplerops/native-packages \
        assets/keplerops/native-workplace \
        assets/narrative/documents/keplerops/company-history.md \
        assets/narrative/documents/keplerops/working-guide.md \
        assets/narrative/documents/keplerops/customer-relationships.md \
        assets/keplerops/build-operations \
        assets/keplerops/policy-compiler \
        assets/keplerops/connector-archive \
        assets/keplerops/release-lineage \
        docs/design/fieldlink-native-foundation.md \
        tests/test_fieldlink_native_foundation.py
    else
      [[ -d $scenario_root/build/arwc && -d $scenario_root/build/arwc-ot ]] || {
        echo 'CINDER_DEV_SCENARIO_ROOT does not contain the ARWC build trees.' >&2
        exit 2
      }
      tar -C "$pack_root" -czf "$archive" \
        --exclude='*/.operator' --exclude='*/__pycache__' \
        build/development-ranges \
        -C "$scenario_root" build/arwc build/arwc-ot
    fi
    remote_archive="/tmp/cinder-$target-source.tar.gz"
    $gcloud_bin compute scp "$archive" "$CINDER_DEV_INSTANCE:$remote_archive" \
      --project="$project" --zone="$zone" --tunnel-through-iap
    $gcloud_bin compute ssh "$CINDER_DEV_INSTANCE" \
      --project="$project" --zone="$zone" --tunnel-through-iap \
      --command="sudo install -d -m 0755 '$CINDER_DEV_REMOTE_ROOT' && sudo tar -xzf '$remote_archive' -C '$CINDER_DEV_REMOTE_ROOT' && rm -f '$remote_archive'"
    rm -f -- "$archive"
    archive=
    ;;
  bind-peer|allow-peer)
    [[ $target == fieldlink ]] || {
      echo 'The cross-range customer relay belongs to FieldLink.' >&2
      exit 2
    }
    verify_managed_instance
    python3 "$root/peer-access.py" "$project" "$zone"
    [[ $action != allow-peer ]] || exit 0
    $gcloud_bin compute ssh "$CINDER_DEV_INSTANCE" \
      --project="$project" --zone="$zone" --tunnel-through-iap \
      --command='sudo bash /opt/cinder-typhoon/build/development-ranges/guest/fieldlink-first-boot.sh'
    ;;
  desktop-login)
    [[ $target == fieldlink ]] || {
      echo 'ARWC desktop login is supplied by its existing workstation provisioner.' >&2
      exit 2
    }
    verify_managed_instance
    $gcloud_bin compute ssh "$CINDER_DEV_INSTANCE" \
      --project="$project" --zone="$zone" --tunnel-through-iap \
      --command='sudo python3 /opt/cinder-typhoon/build/development-ranges/guest/fieldlink-desktop-login.py'
    ;;
  reset)
    verify_managed_instance
    if [[ $target == fieldlink ]]; then
      $gcloud_bin compute ssh "$CINDER_DEV_INSTANCE" \
        --project="$project" --zone="$zone" --tunnel-through-iap \
      --command='sudo bash /opt/cinder-typhoon/build/development-ranges/guest/fieldlink-first-boot.sh && cd /opt/cinder-typhoon/build/keplerops && sudo bash ./restore-pristine.sh && sudo python3 ../development-ranges/guest/fieldlink-desktop-login.py'
    else
      [[ ${1-} == "$CINDER_DEV_INSTANCE" ]] || {
        echo "ARWC reset recreates the VM. Repeat with: reset arwc $project $CINDER_DEV_INSTANCE" >&2
        exit 2
      }
      $gcloud_bin compute instances delete "$CINDER_DEV_INSTANCE" \
        --project="$project" --zone="$zone" --quiet
      provision
    fi
    ;;
esac
