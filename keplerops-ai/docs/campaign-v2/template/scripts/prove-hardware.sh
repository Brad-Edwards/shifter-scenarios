#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly PROOF_MARKER=${CAMPAIGN_HARDWARE_READINESS_MARKER:-/run/shifter/keplerops-v2-hardware.ready}
readonly PROOF_ID=${CAMPAIGN_APPLY_ID:-$(cat /proc/sys/kernel/random/uuid)}

if [[ ${EUID} -ne 0 ]]; then
  echo "prove-hardware.sh must run as root" >&2
  exit 2
fi
if [[ -z ${KEPLEROPS_HARDWARE_GATE14_PLACE:-} ]]; then
  echo "set KEPLEROPS_HARDWARE_GATE14_PLACE to one declared active real bench" >&2
  exit 2
fi

rm -f "$PROOF_MARKER"
"$ROOT/scripts/start-hardware.sh"
"$ROOT/baseline/hardware-place.sh"
"$ROOT/baseline/hardware-participant.sh"

install -d -m 0755 "$(dirname "$PROOF_MARKER")"
umask 077
printf '%s\t%s\t%s\toperator-place+participant-reservation\n' \
  "$(cat /proc/sys/kernel/random/boot_id)" "$PROOF_ID" \
  "$KEPLEROPS_HARDWARE_GATE14_PLACE" >"$PROOF_MARKER"

echo "campaign physical lane passed real-place evidence and participant reservation gates"
