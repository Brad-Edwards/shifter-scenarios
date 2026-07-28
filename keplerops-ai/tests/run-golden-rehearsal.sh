#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec uv run --with 'raes==2.0.0' --with 'pyyaml>=6,<7' --with 'playwright>=1.55,<2' \
  python "$ROOT/live_rehearsal.py" "$@"
