#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 || $# -gt 6 ]]; then
  echo "usage: $0 PHASE OPERATION RESET_ID REMOTE_CANDIDATE [EXPECTED_TRANSITION] [cross-segment]" >&2
  exit 2
fi

phase=$1
operation=$2
reset_identity=$3
remote_candidate=$4
expected_transition=${5:-}
cross_segment=${6:-}

case "$phase" in
  training) instance=${CINDER_TRAINING_INSTANCE:-cinder-training-golden} ;;
  keplerops) instance=${CINDER_KEPLEROPS_INSTANCE:-cinder-keplerops-golden} ;;
  arwc) instance=${CINDER_ARWC_INSTANCE:-cinder-arwc-golden} ;;
  *) echo "unknown phase: $phase" >&2; exit 2 ;;
esac
[[ $operation =~ ^[a-z0-9-]+$ ]] || { echo "invalid operation" >&2; exit 2; }
[[ $reset_identity =~ ^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,159}$ ]] || {
  echo "invalid reset identity" >&2
  exit 2
}
[[ $remote_candidate =~ ^/[A-Za-z0-9._/+-]+$ ]] || { echo "invalid candidate path" >&2; exit 2; }
[[ -z $expected_transition || $expected_transition == diagnostic-execution || $expected_transition == package-activation ]] || {
  echo "invalid expected transition" >&2
  exit 2
}
[[ -z $cross_segment || $cross_segment == cross-segment ]] || {
  echo "sixth argument must be cross-segment" >&2
  exit 2
}

project=${CINDER_GCP_PROJECT:-prod-mgau4w}
zone=${CINDER_GCP_ZONE:-us-central1-a}
account=${CINDER_GCP_ACCOUNT:-bedwards@paloaltonetworks.com}
remote_root=${CINDER_REMOTE_ROOT:-/opt/cinder-typhoon}
remote_report=${CINDER_REMOTE_REPORT:-/var/tmp/cinder-known-solution-${phase}-${operation}.json}

extra=""
[[ -n $expected_transition ]] && extra="$extra --expected-transition '$expected_transition'"
[[ $cross_segment == cross-segment ]] && extra="$extra --cross-segment"

gcloud compute ssh "$instance" \
  --project "$project" \
  --zone "$zone" \
  --account "$account" \
  --tunnel-through-iap \
  --command "cd '$remote_root' && sudo python3 build/participant-surface/run.py --phase '$phase' && sudo python3 build/participant-runner/run.py --phase '$phase' --operation '$operation' --candidate '$remote_candidate' --reset-identity '$reset_identity' --report '$remote_report'$extra"
