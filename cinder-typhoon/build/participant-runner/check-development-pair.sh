#!/usr/bin/env bash
set -euo pipefail

stage=initialization
report_failure() {
  local status=$?
  rm -f -- "$verification_archive"
  if ((status != 0)); then
    echo "FAIL: paired development check stopped during $stage" >&2
  fi
  exit "$status"
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 {delivery-package|delivery-diagnostic} [RUN_LABEL]" >&2
  exit 2
fi

operation=$1
label=${2:-$(date -u +%Y%m%dT%H%M%SZ)}
case "$operation" in
  delivery-package) transition=package-activation ;;
  delivery-diagnostic) transition=diagnostic-execution ;;
  *) echo "unsupported paired operation: $operation" >&2; exit 2 ;;
esac
[[ $label =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || {
  echo "invalid run label" >&2
  exit 2
}

project=${CINDER_GCP_PROJECT:-prod-mgau4w}
zone=${CINDER_GCP_ZONE:-us-central1-a}
kepler_instance=${CINDER_KEPLEROPS_INSTANCE:-cinder-keplerops-golden}
arwc_instance=${CINDER_ARWC_INSTANCE:-cinder-arwc-golden}
remote_root=${CINDER_REMOTE_ROOT:-/opt/cinder-typhoon}
kepler_report="$remote_root/build/keplerops/.operator/known-solution-$label.json"
pack_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
verification_archive=$(mktemp /tmp/cinder-verification.XXXXXX.tar.gz)
trap report_failure EXIT

remote() {
  local instance=$1
  local command=$2
  gcloud compute ssh "$instance" \
    --project "$project" \
    --zone "$zone" \
    --tunnel-through-iap \
    --command "$command"
}

# Keep the two goldens on the same issue-scoped source, then build those sources
# before resetting either stack. This prevents a verification run from silently
# reusing a cached participant or service image from an earlier revision.
stage=verification-source-sync
tar -C "$pack_root" -czf "$verification_archive" \
  --exclude='*/__pycache__' \
  build/input-provenance \
  build/participant-runner \
  build/participant-surface \
  build/training/runtime \
  build/training/tests/test_known_solution_live.py \
  build/keplerops/images \
  build/keplerops/runtime \
  build/keplerops/tests/test_known_solution_live.py \
  build/arwc/runtime \
  build/arwc/tests/test_known_solution_live.py

for instance in "$kepler_instance" "$arwc_instance"; do
  remote_archive="/tmp/cinder-verification-$label.tar.gz"
  gcloud compute scp "$verification_archive" "$instance:$remote_archive" \
    --project "$project" \
    --zone "$zone" \
    --tunnel-through-iap >/dev/null
  remote "$instance" \
    "sudo tar -xzf '$remote_archive' -C '$remote_root' && sudo rm -f -- '$remote_archive'" >/dev/null
done

# Docker is invoked only inside the two GCP goldens. This launcher never runs
# the scenario stack on the operator workstation.
stage=keplerops-build
remote "$kepler_instance" \
  "cd '$remote_root/build/keplerops' && sudo docker compose -f compose.yaml --profile build-only build >/var/tmp/cinder-build-keplerops-$label.log 2>&1"

stage=arwc-reset
remote "$arwc_instance" \
  "cd '$remote_root/build/arwc' && sudo bash ./restore-pristine.sh >/var/tmp/cinder-reset-arwc-$label.log 2>&1"
stage=keplerops-reset
remote "$kepler_instance" \
  "cd '$remote_root/build/keplerops' && sudo bash ./restore-pristine.sh >/var/tmp/cinder-reset-keplerops-$label.log 2>&1"

stage=keplerops-provenance
remote "$kepler_instance" \
  "cd '$remote_root' && sudo python3 build/input-provenance/provenance.py --require-complete --output /var/tmp/cinder-input-provenance-keplerops-$label.json >/dev/null"
stage=keplerops-participant-surface
remote "$kepler_instance" \
  "cd '$remote_root' && sudo python3 build/participant-surface/run.py --phase keplerops >/var/tmp/cinder-participant-surface-keplerops-$label.log 2>&1"
stage=keplerops-acceptance
remote "$kepler_instance" \
  "set -eu; cd '$remote_root'; reset_identity=\$(sudo docker inspect --format={{.Id}} cinder-keplerops-k-dev); sudo python3 build/participant-runner/run.py --phase keplerops --operation '$operation' --development --cross-segment --reset-identity \"\$reset_identity\" --report '$kepler_report' >/var/tmp/cinder-acceptance-keplerops-$label.log 2>&1"

stage=arwc-transition
remote "$arwc_instance" \
  "sudo docker exec -i --user fieldlink cinder-arwc-connector python3 - '$transition' < '$remote_root/build/participant-runner/verify-arwc-transition.py' >/var/tmp/cinder-transition-arwc-$label.log 2>&1"

stage=complete
echo "PASS: $operation and earned ARWC transition; label=$label"
