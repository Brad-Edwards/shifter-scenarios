#!/bin/bash
set -euo pipefail
umask 077

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
phase=${1-}
project=${2-}
image_suffix=${3-}
ot_source=${4-}
ot_ref=${5-}
ot_bake=0
release_archive=""

[[ $project =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || {
  echo "usage: bake-image.sh PHASE GCP_PROJECT IMAGE_SUFFIX" >&2
  exit 2
}
[[ $image_suffix =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]] || {
  echo "IMAGE_SUFFIX must be a lowercase GCE name component" >&2
  exit 2
}

case "$phase" in
  training)
    instance=cinder-training-golden
    subnet=cinder-training-carrier
    tag=cinder-training-carrier
    machine_type=e2-standard-2
    ;;
  keplerops)
    instance=cinder-keplerops-golden
    subnet=cinder-keplerops-carrier
    tag=cinder-keplerops-carrier
    machine_type=e2-standard-4
    ;;
  arwc)
    instance=cinder-arwc-golden
    subnet=cinder-arwc-carrier
    tag=cinder-arwc-carrier
    machine_type=e2-standard-4
    ;;
  *)
    echo "PHASE must be training, keplerops, or arwc" >&2
    exit 2
    ;;
esac

source_commit=$(git -C "$ROOT/.." rev-parse HEAD)
if [[ -n $ot_source || -n $ot_ref ]]; then
  [[ $phase == arwc && $project == prod-mgau4w && $ot_source == cinder-arwc-ot-compat-363 && -n $ot_ref ]] || {
    echo 'OT mode requires arwc, prod-mgau4w, the approved development VM, and a committed source ref.' >&2
    exit 2
  }
  source_commit=$(git -C "$ROOT/.." rev-parse --verify --end-of-options "$ot_ref^{commit}")
  for path in image/runtime-inventory.json hmi/views.json historian/contract.json dispatch/contract.json workstation/contract.json integration/contract.json; do
    git -C "$ROOT/.." cat-file -e "$source_commit:cinder-typhoon/build/arwc-ot/$path"
  done
  instance=$ot_source
  ot_bake=1
fi

final_image="cinder-$phase-$image_suffix"
if ((${#final_image} > 63)); then
  echo "final image name exceeds the GCE 63-character limit" >&2
  exit 2
fi

if (( ! ot_bake )) && [[ -n $(git -C "$ROOT/.." status --porcelain --untracked-files=normal) ]]; then
  echo "refusing to bake from an uncommitted worktree" >&2
  exit 1
fi

zone=us-central1-a
stamp=$(date -u +%Y%m%d%H%M%S)
stage_image="cinder-$phase-stage-$stamp"
bake_instance="cinder-$phase-bake-$stamp"
operator_dir="$ROOT/build/gcp-images/.operator"
mkdir -p "$operator_dir"
chmod 0700 "$operator_dir"

stage_created=0
bake_created=0
golden_stopped=0
cleanup() {
  set +e
  [[ -z $release_archive ]] || rm -f -- "$release_archive"
  if ((golden_stopped)); then
    gcloud compute instances start "$instance" --project "$project" --zone "$zone" --quiet >/dev/null
  fi
  if ((bake_created)); then
    gcloud compute instances delete "$bake_instance" --project "$project" --zone "$zone" --quiet >/dev/null
  fi
  if ((stage_created)); then
    gcloud compute images delete "$stage_image" --project "$project" --quiet >/dev/null
  fi
}
trap cleanup EXIT

if gcloud compute images describe "$final_image" --project "$project" >/dev/null 2>&1; then
  echo "final image already exists; image names are immutable" >&2
  exit 1
fi

if ((ot_bake)); then
  release_archive=$(mktemp /tmp/cinder-arwc-ot-release.XXXXXX.tar.gz)
  git -C "$ROOT/.." archive --format=tar.gz --output="$release_archive" "$source_commit" cinder-typhoon
else
  "$ROOT/build/$phase/gcp/deploy.sh" "$project"
fi

gcloud compute instances stop "$instance" --project "$project" --zone "$zone" --quiet
golden_stopped=1
gcloud compute images create "$stage_image" \
  --project "$project" \
  --source-disk "$instance" \
  --source-disk-zone "$zone" \
  --storage-location us \
  --labels scenario=cinder-typhoon,segment="$phase",purpose=image-stage
stage_created=1
gcloud compute instances start "$instance" --project "$project" --zone "$zone" --quiet
golden_stopped=0

gcloud compute instances create "$bake_instance" \
  --project "$project" \
  --zone "$zone" \
  --machine-type "$machine_type" \
  --image "$stage_image" \
  --image-project "$project" \
  --subnet "$subnet" \
  --no-address \
  --no-service-account \
  --no-scopes \
  --tags "$tag" \
  --metadata enable-oslogin=TRUE,block-project-ssh-keys=TRUE,serial-port-enable=FALSE
bake_created=1

for attempt in $(seq 1 120); do
  if gcloud compute ssh "$bake_instance" --project "$project" --zone "$zone" \
      --tunnel-through-iap --command true >/dev/null 2>&1; then
    break
  fi
  if [[ $attempt -eq 120 ]]; then
    echo "temporary bake guest did not become reachable" >&2
    exit 1
  fi
  sleep 5
done

if ((ot_bake)); then
  gcloud compute scp "$release_archive" "$bake_instance:/tmp/cinder-arwc-ot-release.tar.gz" \
    --project "$project" --zone "$zone" --tunnel-through-iap
  gcloud compute ssh "$bake_instance" --project "$project" --zone "$zone" --tunnel-through-iap \
    --command 'sudo tar -xzf /tmp/cinder-arwc-ot-release.tar.gz -C /opt && sudo bash /opt/cinder-typhoon/build/arwc-ot/image/prepare-image.sh'
else
  gcloud compute ssh "$bake_instance" --project "$project" --zone "$zone" \
    --tunnel-through-iap \
    --command "sudo /opt/cinder-typhoon/build/gcp-images/guest/prepare-image.sh '$phase'"
fi
gcloud compute instances stop "$bake_instance" --project "$project" --zone "$zone" --quiet

gcloud compute images create "$final_image" \
  --project "$project" \
  --source-disk "$bake_instance" \
  --source-disk-zone "$zone" \
  --storage-location us \
  --description "Cinder Typhoon $phase; source commit $source_commit" \
  --labels scenario=cinder-typhoon,segment="$phase",purpose=bigrae-range-image

if gcloud compute images get-iam-policy "$final_image" --project "$project" \
    --flatten='bindings[].members' \
    --filter='bindings.members:(allUsers OR allAuthenticatedUsers)' \
    --format='value(bindings.members)' | grep -q .; then
  echo "final image has a public IAM member" >&2
  exit 1
fi

gcloud compute images describe "$final_image" --project "$project" --format=json \
  >"$operator_dir/$final_image.json"
gcloud compute images describe "$final_image" --project "$project" \
  --format='table(name,id,status,selfLink)'
