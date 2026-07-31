#!/bin/sh
set -eu

exec python3 /opt/keplerops/platform-context/reset.py \
  --state-root "${PLATFORM_CONTEXT_STATE_ROOT:-/var/lib/keplerops-platform-context}"
