#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 1 ]]; then
  echo "usage: $0 [RUN_LABEL]" >&2
  exit 2
fi

label=${1:-$(date -u +%Y%m%dT%H%M%SZ)}
[[ $label =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || {
  echo "invalid run label" >&2
  exit 2
}

project=${CINDER_GCP_PROJECT:-prod-mgau4w}
zone=${CINDER_GCP_ZONE:-us-central1-a}
kepler_instance=${CINDER_KEPLEROPS_INSTANCE:-cinder-keplerops-golden}
arwc_instance=${CINDER_ARWC_INSTANCE:-cinder-arwc-golden}
remote_root=${CINDER_REMOTE_ROOT:-/opt/cinder-typhoon}
pack_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
test_archive=$(mktemp /tmp/cinder-keplerops-contracts.XXXXXX.tar.gz)
trap 'rm -f -- "$test_archive"' EXIT

remote() {
  local instance=$1
  local command=$2
  gcloud compute ssh "$instance" \
    --project "$project" \
    --zone "$zone" \
    --tunnel-through-iap \
    --command "$command"
}

tar -C "$pack_root" -czf "$test_archive" --exclude='*/__pycache__' build/keplerops/tests
gcloud compute scp "$test_archive" "$kepler_instance:/tmp/cinder-keplerops-contracts-$label.tar.gz" \
  --project "$project" --zone "$zone" --tunnel-through-iap >/dev/null
remote "$kepler_instance" \
  "sudo tar -xzf /tmp/cinder-keplerops-contracts-$label.tar.gz -C '$remote_root' && sudo rm -f -- /tmp/cinder-keplerops-contracts-$label.tar.gz" >/dev/null

remote "$arwc_instance" \
  "cd '$remote_root/build/arwc' && sudo bash ./restore-pristine.sh >/var/tmp/cinder-contract-reset-arwc-$label.log 2>&1"
remote "$kepler_instance" \
  "cd '$remote_root/build/keplerops' && sudo bash ./restore-pristine.sh >/var/tmp/cinder-contract-reset-keplerops-$label.log 2>&1"

remote "$kepler_instance" \
  "set -eu; cd '$remote_root/build/keplerops'; export CINDER_CROSS_SEGMENT=1; for test in test_opening_live.py test_registry_foundation_live.py test_k04_live.py test_k09_live.py test_k11_live.py test_k28_live.py test_declared_components_live.py test_platform_live.py test_delivery_live.py; do sudo -E python3 \"tests/\$test\"; done >/var/tmp/cinder-contracts-keplerops-$label.log 2>&1"

echo "PASS: KeplerOps service contracts on GCP; label=$label"
