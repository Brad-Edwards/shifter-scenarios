#!/usr/bin/env bash
set -euo pipefail

BUILD_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PACK_ROOT=$(CDPATH= cd -- "$BUILD_ROOT/.." && pwd)

exec uv run --no-project \
  --with-requirements "$PACK_ROOT/validation/requirements-ci.txt" \
  python -m unittest discover \
    -s "$BUILD_ROOT/tests" \
    -t "$BUILD_ROOT"
