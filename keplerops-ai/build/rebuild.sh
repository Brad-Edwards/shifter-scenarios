#!/usr/bin/env bash
set -euo pipefail
BUILD_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$BUILD_ROOT/cleanup.sh" "$@"
"$BUILD_ROOT/launch.sh" "$@"
