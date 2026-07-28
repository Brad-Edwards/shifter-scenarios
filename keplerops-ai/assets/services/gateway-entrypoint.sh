#!/bin/sh
set -eu

MLFLOW_TRACKING_URI=$(
python - <<'PY'
from pathlib import Path
from urllib.parse import urlsplit

import yaml

config = yaml.safe_load(Path("/etc/keplerops/runtime.yaml").read_text(encoding="utf-8"))
value = config.get("registry_url") if isinstance(config, dict) else None
parsed = urlsplit(value) if isinstance(value, str) else None
if (
    parsed is None
    or parsed.scheme != "http"
    or parsed.hostname != "model-registry-01.keplerops.lab"
    or parsed.port != 9000
    or parsed.path not in {"", "/"}
    or parsed.query
    or parsed.fragment
    or parsed.username
    or parsed.password
):
    raise SystemExit("invalid SDL-projected model registry URL")
print(value)
PY
)
readonly MLFLOW_TRACKING_URI
export MLFLOW_TRACKING_URI
MLFLOW_REGISTRY_URI=$MLFLOW_TRACKING_URI
readonly MLFLOW_REGISTRY_URI
export MLFLOW_REGISTRY_URI

run_agent_worker() {
  while true; do
    set +e
    python -m uvicorn agent_worker:app --host 127.0.0.1 --port 8450 --no-access-log --no-proxy-headers
    status=$?
    set -e
    if [ "$status" -eq 75 ]; then
      continue
    fi
    sleep 1
  done
}

run_agent_action_worker() {
  while true; do
    python -m uvicorn agent_action_worker:app --host 127.0.0.1 --port 8451 --no-access-log --no-proxy-headers || true
    sleep 1
  done
}

run_agent_worker &
run_agent_action_worker &
python -m uvicorn app:app --host 127.0.0.1 --port 8443 --no-access-log --no-proxy-headers &
exec /usr/local/bin/envoy -c /etc/keplerops/envoy.yaml --log-level warn
