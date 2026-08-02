#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:?usage: reset.sh <operation-id>}"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"

die() { printf '[campaign-m06-reset] ERROR: %s\n' "$*" >&2; exit 1; }
flag_for() { jq -er --arg id "$1" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json"; }

accepted_in() {
  local container=$1 root=$2 flag=$3
  docker exec "$container" sh -ec 'grep -RFl -- "$1" "$2" 2>/dev/null | head -n1' sh "$flag" "$root"
}

clean_intake_attempts() {
  docker exec -i kep-v2-partner-intake python - <<'PY'
import json, shutil
from pathlib import Path
root=Path('/var/lib/partner-intake')
kept=set()
for path in (root/'reviews').glob('*/*.json'):
    value=json.loads(path.read_text())
    kept.update(str(value[key]) for key in ('intake_id','baseline_intake_id') if value.get(key))
for directory in (root/'intakes').glob('*'):
    if directory.name not in kept: shutil.rmtree(directory)
for path in (root/'fixtures').glob('*.json'):
    if 'flag' not in json.loads(path.read_text()): path.unlink()
PY
}

clean_bridge_attempts() {
  docker exec kep-v2-cinder-host-bridge sh -ec '
    test ! -s /var/lib/cinder-bridge/command-corpus.json || exit 0
    find /var/lib/cinder-bridge -maxdepth 1 -type f -name "job-*.json" -delete
  '
  docker exec kep-v2-cinder-developer-assistant sh -ec \
    'find /var/lib/cinder-developer -maxdepth 1 -type f -name "*.json" -delete'
}

clean_experiment_attempts() {
  local kind=$1
  docker exec kep-v2-cinder-experiments sh -ec \
    'test ! -d "$1" || find "$1" -maxdepth 1 -type f -name "*.json" ! -exec grep -qF "FLAG{" {} \; -delete' \
    sh "/var/lib/cinder-experiments/$kind"
}

clean_media_attempts() {
  docker exec -i kep-v2-cinder-openvoice python - <<'PY'
import json, shutil
from pathlib import Path
records=Path('/records'); work=Path('/work/media')
accepted={p.stem.removeprefix('registry-') for p in records.glob('registry-*.json')}
for path in records.glob('*.json'):
    if not path.name.startswith('registry-') and path.stem not in accepted: path.unlink()
for directory in work.glob('*'):
    if directory.name not in accepted: shutil.rmtree(directory)
PY
}

clean_jupyter_attempt() {
  if docker exec kep-v2-cinder-jupyter sh -ec 'find /srv/jupyterhub/state/reattachments -type f -name "*.json" -print -quit 2>/dev/null | grep -q .'; then
    return
  fi
  ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes "$K3S01_SSH_TARGET" \
    sudo k3s kubectl -n cinder delete pod -l hub.jupyter.org/username=cinder-field-operator --ignore-not-found >/dev/null
}

clean_knative_attempts() {
  local listing service
  listing="$(ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes "$K3S01_SSH_TARGET" sudo find /var/lib/cinder-publisher/deployments -type f -name '*.json' -print 2>/dev/null || true)"
  while IFS= read -r path; do
    [[ -n $path ]] || continue
    service="$(ssh -n -i "$K3S01_SSH_KEY" -o BatchMode=yes "$K3S01_SSH_TARGET" sudo jq -r .service "$path")"
    ssh -n -i "${TEMPLATE_ROOT}/state/cinder-publisher/id_ed25519" -o BatchMode=yes \
      -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=${TEMPLATE_ROOT}/state/cinder-publisher/known_hosts" \
      cinder-publisher@192.168.78.30 "delete $service" >/dev/null
  done <<<"$listing"
}

release_hardware_reservation() {
  local archive=${M06_HARDWARE_EVIDENCE_ARCHIVE:-} reservation
  if [[ -z $archive || ! -s $archive ]]; then
    printf 'no raw evidence archive was supplied, so no external reservation token is available to release; accepted evidence is untouched\n'
    return
  fi
  reservation="$(tar -xOf "$archive" manifest.json | jq -er '.reservation | select(type=="string" and length>=8)')" || \
    die 'raw evidence manifest has no exact reservation token'
  docker exec --user kasm-user --env HOME=/home/kasm-user --env LG_COORDINATOR=labgrid-coordinator:20408 \
    --env LG_TOKEN="$reservation" keplerops-participant-workstation-runtime \
    labgrid-client --place + release >/dev/null 2>&1 || true
  docker exec --user kasm-user --env HOME=/home/kasm-user --env LG_COORDINATOR=labgrid-coordinator:20408 \
    keplerops-participant-workstation-runtime labgrid-client cancel-reservation "$reservation" >/dev/null 2>&1 || true
  printf 'released or confirmed absent the exact external reservation; raw evidence and accepted calibration remain immutable\n'
}

main() {
  jq -e --arg id "$OPERATION" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: $OPERATION"
  local flag container root
  flag="$(flag_for "$OPERATION")"
  case "$OPERATION" in
    kep-m06-g|kep-m06-h|kep-m06-i) printf '%s is immutable public source state; nothing was removed\n' "$OPERATION"; return ;;
    kep-m06-a|kep-m06-e|kep-m06-f|kep-m06-s) container=kep-v2-partner-intake; root=/var/lib/partner-intake ;;
    kep-m06-b) container=kep-v2-cinder-host-bridge; root=/var/lib/cinder-bridge ;;
    kep-m06-c|kep-m06-d|kep-m06-r) container=kep-v2-cinder-experiments; root=/var/lib/cinder-experiments ;;
    kep-m06-j) container=kep-v2-edge-observer; root=/var/lib/edge-observer ;;
    kep-m06-k|kep-m06-o|kep-m06-q|kep-m06-v) container=kep-v2-cinder-release-registry; root=/var/lib/cinder-release-registry ;;
    kep-m06-l) container=kep-v2-cinder-jupyter; root=/srv/jupyterhub/state ;;
    kep-m06-m) release_hardware_reservation; return ;;
    kep-m06-n) container=kep-v2-cinder-registrar; root=/var/lib/cinder-registrar ;;
    kep-m06-p) printf '%s usage audit is append-only; retry with a new OpenCode request\n' "$OPERATION"; return ;;
    kep-m06-t) container=kep-v2-cinder-openvoice; root=/records ;;
    kep-m06-u) container=none; root=none ;;
  esac
  if [[ $container != none ]] && [[ -n $(accepted_in "$container" "$root" "$flag") ]]; then
    printf '%s accepted native checkpoint is immutable; no state was removed\n' "$OPERATION"
    return
  fi
  if [[ $OPERATION == kep-m06-u ]] && ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes "$K3S01_SSH_TARGET" \
      "sudo grep -RFl -- '$flag' /var/lib/cinder-publisher/lifecycles 2>/dev/null | head -n1" | grep -q .; then
    printf '%s accepted native checkpoint is immutable; no state was removed\n' "$OPERATION"
    return
  fi
  case "$OPERATION" in
    kep-m06-a|kep-m06-e|kep-m06-f|kep-m06-s) clean_intake_attempts ;;
    kep-m06-b) clean_bridge_attempts ;;
    kep-m06-c) clean_experiment_attempts preview-audit-export ;;
    kep-m06-d) clean_experiment_attempts preview-audit-export ;;
    kep-m06-r) clean_experiment_attempts whitebox-evaluation ;;
    kep-m06-l) clean_jupyter_attempt ;;
    kep-m06-t) clean_media_attempts ;;
    kep-m06-u) clean_knative_attempts ;;
    kep-m06-n)
      curl -fsS -H 'Authorization: Bearer Cinder-Field-Operator-Registrar-4c8e2a7f' http://10.61.90.34:8080/v1/accounts | \
        jq -r '.[].account_id' | while read -r account_id; do
          curl -fsS -X DELETE -H 'Authorization: Bearer Cinder-Field-Operator-Registrar-4c8e2a7f' \
            "http://10.61.90.34:8080/v1/accounts/${account_id}" >/dev/null
        done
      ;;
    *) : ;; # rejected native requests are transactional and leave no mutable record
  esac
  printf 'cleared only disposable %s attempt state; ancestors and accepted records were preserved\n' "$OPERATION"
}

main "$@"
