#!/bin/bash
set -euo pipefail

if [[ ${1-} != standalone ]]; then
  exec /entrypoint "$@"
fi

/entrypoint standalone &
airflow_pid=$!
trap 'kill "$airflow_pid" 2>/dev/null || true; wait "$airflow_pid" 2>/dev/null || true' EXIT TERM INT

for attempt in $(seq 1 90); do
  if airflow db check >/dev/null 2>&1; then
    break
  fi
  [[ $attempt -lt 90 ]] || exit 1
  sleep 2
done

for attempt in $(seq 1 90); do
  if airflow dags list --output plain 2>/dev/null \
    | grep -q '^company_state_orion_release'; then
    break
  fi
  [[ $attempt -lt 90 ]] || exit 1
  sleep 2
done

python /opt/keplerops/company_airflow_adapter.py seed \
  --company-state /opt/keplerops/company-state.yaml
python /opt/keplerops/company_airflow_adapter.py readback \
  --company-state /opt/keplerops/company-state.yaml

wait "$airflow_pid"
