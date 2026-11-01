#!/usr/bin/env bash
set -euo pipefail
umask 077

input=${1:-/tmp/cinder-ct511-input}
work=/var/tmp/cinder-ct511-acceptance
platform_mount=/workspace/repo/shifter
uv_image=ghcr.io/astral-sh/uv@sha256:3137a0b606f65a74ee0245f43dae219b09e8af98fc37fef20841cbceef35a646
node_image=node@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0

for path in platform.tar event-content.json golden_acceptance.py CinderDeliveryGolden.test.tsx; do
  [[ -f "$input/$path" ]] || { echo "missing acceptance input: $path" >&2; exit 1; }
done

sudo rm -rf -- "$work"
sudo install -d -m 0700 "$work/platform" "$work/proof"
sudo tar -xf "$input/platform.tar" -C "$work/platform"
sudo install -m 0600 "$input/event-content.json" "$work/proof/event-content.json"
sudo install -m 0600 "$input/golden_acceptance.py" \
  "$work/platform/shifter/shifter_platform/tests/ctf/test_cinder_delivery_golden.py"
sudo install -m 0600 "$input/CinderDeliveryGolden.test.tsx" \
  "$work/platform/shifter/shifter_platform/frontend/src/features/ctf/CinderDeliveryGolden.test.tsx"

sudo docker pull "$uv_image" >/dev/null
sudo docker run --rm --entrypoint uv \
  --volume "$work/platform/shifter:$platform_mount" \
  --workdir "$platform_mount/shifter_platform" \
  "$uv_image" sync --frozen --group dev >/dev/null

sudo docker run --rm --entrypoint uv \
  --env CINDER_EVENT_BUNDLE=/proof/event-content.json \
  --env TESTING=1 \
  --env TEST_DB_BACKEND=sqlite \
  --volume "$work/platform/shifter:$platform_mount" \
  --volume "$work/proof:/proof:ro" \
  --workdir "$platform_mount/shifter_platform" \
  "$uv_image" run pytest -o addopts= -q tests/ctf/test_cinder_delivery_golden.py

sudo docker pull "$node_image" >/dev/null
sudo docker run --rm --entrypoint npm \
  --volume "$work/platform/shifter/shifter_platform/frontend:/app" \
  --workdir /app \
  "$node_image" ci --ignore-scripts --no-audit --no-fund >/dev/null
sudo docker run --rm --entrypoint npm \
  --env CINDER_EVENT_BUNDLE=/proof/event-content.json \
  --volume "$work/platform/shifter/shifter_platform/frontend:/app" \
  --volume "$work/proof:/proof:ro" \
  --workdir /app \
  "$node_image" exec -- vitest run src/features/ctf/CinderDeliveryGolden.test.tsx

echo '{"backend_import_api_scoring":"passed","frontend_240_card_render":"passed"}'
