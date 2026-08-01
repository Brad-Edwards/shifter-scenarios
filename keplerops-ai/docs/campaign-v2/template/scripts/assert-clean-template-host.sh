#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly METADATA_URL=http://metadata.google.internal/computeMetadata/v1
readonly CONFIRMATION=campaign-v2-clean-template-worker-replacement

fail() {
  printf 'worker replacement refused: %s\n' "$*" >&2
  exit 2
}

[[ $EUID -eq 0 ]] || fail 'root is required'
[[ ${KEPLEROPS_TEMPLATE_REPLACEMENT_CONFIRM:-} == "$CONFIRMATION" ]] ||
  fail "set KEPLEROPS_TEMPLATE_REPLACEMENT_CONFIRM=${CONFIRMATION} explicitly"

generation_file="$ROOT/state/workstation/reset-generation"
[[ -f $generation_file ]] || fail "missing template generation marker: $generation_file"
[[ $(<"$generation_file") == campaign-v2-template ]] ||
  fail 'workstation generation is not campaign-v2-template'

for marker in \
  "$ROOT/state/participant" \
  "$ROOT/state/range-id" \
  /run/keplerops/participant \
  /run/keplerops/range-id \
  /run/shifter/participant \
  /run/shifter/range-id; do
  [[ ! -e $marker ]] || fail "participant/range marker exists: $marker"
done

metadata() {
  curl -fsS --connect-timeout 2 --max-time 5 \
    -H 'Metadata-Flavor: Google' "$METADATA_URL/$1"
}

campaign=$(metadata instance/attributes/campaign) ||
  fail 'GCE campaign metadata is unavailable'
[[ $campaign == v2 ]] || fail 'GCE campaign metadata is not v2'

instance_name=$(metadata instance/name) || fail 'GCE instance name is unavailable'
[[ $instance_name =~ ^kep-v2-template(-[a-z0-9]+)*$ ]] ||
  fail "GCE instance is not a campaign-v2 template host: $instance_name"

attribute_names=$(metadata instance/attributes/) ||
  fail 'GCE instance-attribute inventory is unavailable'
for forbidden in range-id request-id participant participant-id ctf-event-id shifter-range-id; do
  if grep -Fxq "$forbidden" <<<"$attribute_names"; then
    fail "GCE participant/range metadata is present: $forbidden"
  fi
done

printf 'clean campaign-v2 template host admitted: %s\n' "$instance_name"
