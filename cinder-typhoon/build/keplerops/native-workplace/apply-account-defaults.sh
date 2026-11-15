#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
docker compose -f compose.yaml --profile operator run --rm --no-deps fieldlink-identity-setup
