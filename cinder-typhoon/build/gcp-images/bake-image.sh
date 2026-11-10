#!/bin/bash
set -euo pipefail
umask 077

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
phase=${1-}
project=${2-}
image_suffix=${3-}

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

final_image="cinder-$phase-$image_suffix"
if ((${#final_image} > 63)); then
  echo "final image name exceeds the GCE 63-character limit" >&2
  exit 2
fi

if [[ -n $(git -C "$ROOT/.." status --porcelain --untracked-files=normal) ]]; then
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

"$ROOT/build/$phase/gcp/deploy.sh" "$project"

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

gcloud compute ssh "$bake_instance" --project "$project" --zone "$zone" \
  --tunnel-through-iap \
  --command "sudo /opt/cinder-typhoon/build/gcp-images/guest/prepare-image.sh '$phase'"
gcloud compute instances stop "$bake_instance" --project "$project" --zone "$zone" --quiet

source_commit=$(git -C "$ROOT/.." rev-parse HEAD)
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
