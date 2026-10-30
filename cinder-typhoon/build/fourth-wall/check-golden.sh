#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 training|keplerops|arwc" >&2
  exit 2
fi

phase=$1
case "$phase" in
  training) instance=${CINDER_TRAINING_INSTANCE:-cinder-training-golden} ;;
  keplerops) instance=${CINDER_KEPLEROPS_INSTANCE:-cinder-keplerops-golden} ;;
  arwc) instance=${CINDER_ARWC_INSTANCE:-cinder-arwc-golden} ;;
  *) echo "unknown phase: $phase" >&2; exit 2 ;;
esac

project=${CINDER_GCP_PROJECT:-prod-mgau4w}
zone=${CINDER_GCP_ZONE:-us-central1-a}
account=${CINDER_GCP_ACCOUNT:-bedwards@paloaltonetworks.com}
remote_root=${CINDER_REMOTE_ROOT:-/opt/cinder-typhoon}

gcloud compute ssh "$instance" \
  --project "$project" \
  --zone "$zone" \
  --account "$account" \
  --tunnel-through-iap \
  --command "cd '$remote_root' && sudo python3 build/fourth-wall/run.py --phase '$phase' --require-clean --output '/var/tmp/cinder-fourth-wall-$phase.json'"
