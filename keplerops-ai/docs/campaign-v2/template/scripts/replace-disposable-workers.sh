#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly KEY=${KEPLEROPS_V2_SSH_KEY:-/root/.ssh/keplerops-v2}
readonly WAIT_SECONDS=${WORKER_REPLACEMENT_WAIT_SECONDS:-1800}
if (($#)); then
  GUESTS=("$@")
else
  GUESTS=(review01 integration01)
fi
readonly GUESTS
for guest in "${GUESTS[@]}"; do
  [[ $guest == review01 || $guest == integration01 ]] || {
    printf 'unsupported disposable worker: %s\n' "$guest" >&2
    exit 2
  }
done
readonly SSH=(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

[[ $EUID -eq 0 ]] || { echo 'replace-disposable-workers.sh must run as root' >&2; exit 2; }
for command in cloud-localds flock jq ssh virsh; do
  command -v "$command" >/dev/null || {
    printf 'missing required command: %s\n' "$command" >&2
    exit 2
  }
done

"$ROOT/scripts/assert-clean-template-host.sh"
install -d -m 0750 "$ROOT/state/worker-replacement"
exec 9>"$ROOT/state/worker-replacement/replace.lock"
flock -n 9 || { echo 'another disposable-worker replacement is active' >&2; exit 3; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
nonce=$(date -u +%Y%m%dT%H%M%SZ)-$$

guest_address() {
  case $1 in
    review01) printf '192.168.78.20' ;;
    integration01) printf '192.168.78.21' ;;
    *) return 2 ;;
  esac
}

for guest in "${GUESTS[@]}"; do
  virsh dominfo "$guest" >/dev/null
  virsh domuuid "$guest" >"$work/$guest.old.uuid"
  address=$(guest_address "$guest")
  "${SSH[@]}" "kepler@$address" 'cat /etc/machine-id' >"$work/$guest.old.machine-id"
  "${SSH[@]}" "kepler@$address" \
    "printf '%s\\n' '$nonce' | sudo tee /var/tmp/keplerops-disposable-attempt-state >/dev/null"
done

RECREATE_GUESTS="$(IFS=,; printf '%s' "${GUESTS[*]}")" "$ROOT/scripts/provision-guests.sh"

deadline=$((SECONDS + WAIT_SECONDS))
for guest in "${GUESTS[@]}"; do
  address=$(guest_address "$guest")
  while :; do
    current_uuid=$(virsh domuuid "$guest" 2>/dev/null || true)
    old_uuid=$(<"$work/$guest.old.uuid")
    if [[ -n $current_uuid && $current_uuid != "$old_uuid" ]] &&
      timeout 30 "${SSH[@]}" "kepler@$address" \
        'cloud-init status --wait >/dev/null 2>&1 && test ! -e /var/tmp/keplerops-disposable-attempt-state' \
        >/dev/null 2>&1; then
      break
    fi
    ((SECONDS < deadline)) || {
      printf '%s did not rebuild within %s seconds\n' "$guest" "$WAIT_SECONDS" >&2
      exit 4
    }
    sleep 10
  done

  "${SSH[@]}" "kepler@$address" 'cat /etc/machine-id' >"$work/$guest.new.machine-id"
  cmp -s "$work/$guest.old.machine-id" "$work/$guest.new.machine-id" && {
    printf '%s retained its machine ID after replacement\n' "$guest" >&2
    exit 4
  }
  "${SSH[@]}" "kepler@$address" \
    'realm list | grep -qi corp.keplerops.lab; getent passwd "reviewer@corp.keplerops.lab" >/dev/null'
done

"$ROOT/scripts/reconcile-guests.sh"
"$ROOT/scripts/check-guests.sh"

result='{}'
for guest in "${GUESTS[@]}"; do
  result="$(jq --arg guest "$guest" --arg uuid "$(virsh domuuid "$guest")" --arg machine_id "$(<"$work/$guest.new.machine-id")" '.[$guest]={uuid:$uuid,machine_id:$machine_id}' <<<"$result")"
done
jq -S . <<<"$result"
