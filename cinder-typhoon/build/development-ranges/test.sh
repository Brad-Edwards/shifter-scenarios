#!/usr/bin/env bash
set -euo pipefail

root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH='' cd -- "$root/../../.." && pwd)

bash -n "$root/manage.sh" "$root/targets.sh" "$root/guest/fieldlink-first-boot.sh" \
  "$root/guest/arwc-first-boot.sh"

if [[ $(hostname) != cinder-fieldlink-dev ]] \
    && python3 "$root/guest/fieldlink-desktop-login.py" 2>/dev/null; then
  echo 'development desktop login accepted an unrelated host' >&2
  exit 1
fi

# shellcheck source=targets.sh disable=SC1091
source "$root/targets.sh"
cinder_load_development_target fieldlink
cinder_validate_development_target
[[ $CINDER_DEV_INSTANCE == cinder-fieldlink-dev ]]
[[ $CINDER_DEV_PRIVATE_IP == 10.77.49.9 ]]
cinder_load_development_target arwc
cinder_validate_development_target
[[ $CINDER_DEV_INSTANCE == cinder-arwc-dev ]]
[[ $CINDER_DEV_PRIVATE_IP == 10.77.59.11 ]]
CINDER_DEV_PRIVATE_IP=10.77.59.2
if cinder_validate_development_target; then
  echo 'golden-address mutation survived' >&2
  exit 1
fi

if cinder_load_development_target unknown 2>/dev/null; then
  echo 'unknown target was accepted' >&2
  exit 1
fi
if "$root/manage.sh" describe fieldlink not_valid 2>/dev/null; then
  echo 'invalid project was accepted' >&2
  exit 1
fi

mutant=$(mktemp /tmp/cinder-development-targets.XXXXXX)
trap 'rm -f -- "$mutant"' EXIT
sed 's/CINDER_DEV_INSTANCE=cinder-fieldlink-dev/CINDER_DEV_INSTANCE=cinder-keplerops-golden/' \
  "$root/targets.sh" >"$mutant"
# shellcheck disable=SC1090,SC1091
source "$mutant"
cinder_load_development_target fieldlink
if cinder_validate_development_target; then
  echo 'golden-target mutation survived' >&2
  exit 1
fi

cmp "$repo/.agents/skills/cinder-development-ranges/SKILL.md" \
  "$repo/.claude/skills/cinder-development-ranges/SKILL.md"
echo 'Development-range target and safety checks passed.'
