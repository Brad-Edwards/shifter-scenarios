#!/bin/sh
set -eu

role="${1:-api}"
case "$role" in
  api)
    export PLATFORM_DEPLOYMENT_ROLE=api
    exec uvicorn api:app --host 0.0.0.0 --port 8490 --no-access-log
    ;;
  lifecycle-worker)
    export PLATFORM_DEPLOYMENT_ROLE=lifecycle-worker
    exec python3 lifecycle_worker.py
    ;;
  workspace)
    export PLATFORM_DEPLOYMENT_ROLE=workspace
    exec python3 workspace.py integrity-inventory
    ;;
  render-policy)
    shift
    exec python3 render_policy.py "$@"
    ;;
  reset)
    export PLATFORM_DEPLOYMENT_ROLE=reset
    exec python3 reset.py
    ;;
  *)
    echo "unsupported platform-deployment role: $role" >&2
    exit 64
    ;;
esac
