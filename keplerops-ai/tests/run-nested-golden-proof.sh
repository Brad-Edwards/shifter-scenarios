#!/usr/bin/env bash
set -euo pipefail
umask 077

TEST_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PACK_ROOT=$(CDPATH= cd -- "$TEST_ROOT/.." && pwd)

usage() {
  cat >&2 <<'EOF'
usage: run-nested-golden-proof.sh --project-id ID --range-instance ID \
  --participant ID --participant-source-cidr CIDR \
  [--region REGION] [--zone ZONE] [--skip-static-tests] [--walkthrough-only]
EOF
  exit 2
}

PROJECT_ID= RANGE_INSTANCE= PARTICIPANT= PARTICIPANT_SOURCE_CIDR=
REGION=europe-west4 ZONE=europe-west4-a SKIP_STATIC_TESTS=false
WALKTHROUGH_ONLY=false
while (($#)); do
  case "$1" in
    --project-id) PROJECT_ID=${2-}; shift 2 ;;
    --range-instance) RANGE_INSTANCE=${2-}; shift 2 ;;
    --participant) PARTICIPANT=${2-}; shift 2 ;;
    --participant-source-cidr) PARTICIPANT_SOURCE_CIDR=${2-}; shift 2 ;;
    --region) REGION=${2-}; shift 2 ;;
    --zone) ZONE=${2-}; shift 2 ;;
    --skip-static-tests) SKIP_STATIC_TESTS=true; shift ;;
    --walkthrough-only) WALKTHROUGH_ONLY=true; shift ;;
    *) usage ;;
  esac
done

[[ -n $PROJECT_ID && -n $RANGE_INSTANCE && -n $PARTICIPANT ]] || usage
[[ -n $PARTICIPANT_SOURCE_CIDR ]] || usage

COMMON=(
  --project-id "$PROJECT_ID"
  --range-instance "$RANGE_INSTANCE"
  --participant "$PARTICIPANT"
  --participant-source-cidr "$PARTICIPANT_SOURCE_CIDR"
  --region "$REGION"
  --zone "$ZONE"
  --use-existing-range
  --retain-until-phase-e
)
UV=(
  uv run
  --with 'raes==2.0.0'
  --with 'pyyaml>=6,<7'
  --with 'playwright>=1.55,<2'
  python
)

if [[ $SKIP_STATIC_TESTS == false ]]; then
  "$PACK_ROOT/build/test.sh"
fi

# The integrated core pass covers the original 60 realized challenges. Focused
# runners cover the 74 expansion challenges.
CORE_ARGS=()
MODULE_01_ARGS=()
MODULE_RESET_ARGS=()
if [[ $WALKTHROUGH_ONLY == true ]]; then
  CORE_ARGS+=(--walkthrough-only)
  MODULE_01_ARGS+=(--walkthrough-only)
  MODULE_RESET_ARGS+=(--prepared-module-reset)
fi
"$TEST_ROOT/run-golden-rehearsal.sh" "${COMMON[@]}" "${CORE_ARGS[@]}"
"${UV[@]}" "$TEST_ROOT/module_01_expansion_rehearsal.py" \
  "${COMMON[@]}" "${MODULE_01_ARGS[@]}"
for runner in \
  module_02_supply_rehearsal.py \
  module_02_package_rehearsal.py \
  module_02_spearphish_rehearsal.py; do
  "${UV[@]}" "$TEST_ROOT/$runner" "${COMMON[@]}"
done
for runner in \
  module_03_full_atlas_rehearsal.py \
  module_04_full_atlas_rehearsal.py \
  module_05_full_atlas_rehearsal.py \
  module_06_full_atlas_rehearsal.py \
  module_07_full_atlas_rehearsal.py \
  module_08_full_atlas_rehearsal.py \
  module_09_full_atlas_rehearsal.py; do
  "${UV[@]}" "$TEST_ROOT/$runner" "${COMMON[@]}" "${MODULE_RESET_ARGS[@]}"
done
"${UV[@]}" "$TEST_ROOT/module_10_full_atlas_rehearsal.py" \
  "${COMMON[@]}" --prepared-prerequisites

if [[ $WALKTHROUGH_ONLY == false ]]; then
  "$PACK_ROOT/build/reset.sh" \
    --range-instance "$RANGE_INSTANCE" --participant "$PARTICIPANT"
fi
"$PACK_ROOT/build/health-check.sh" \
  --range-instance "$RANGE_INSTANCE" --participant "$PARTICIPANT"

if [[ $WALKTHROUGH_ONLY == true ]]; then
  printf '%s\n' \
    "nested golden proof: PASS (134 unique realized challenges, participant walkthrough, health)"
else
  printf '%s\n' \
    "nested golden proof: PASS (134 unique realized challenges, canonical reset, health)"
fi
