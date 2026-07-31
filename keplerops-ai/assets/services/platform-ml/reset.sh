#!/bin/sh
set -eu

exec python3 /opt/keplerops/platform-ml/reset.py \
  --state-root "${PLATFORM_ML_STATE_ROOT:-/var/lib/keplerops-platform-ml}"
