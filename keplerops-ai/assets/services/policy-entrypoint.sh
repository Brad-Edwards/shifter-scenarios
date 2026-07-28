#!/bin/sh
set -eu
/usr/local/bin/opa run --server --addr=0.0.0.0:8181 /etc/keplerops/guardrails.rego &
for attempt in $(seq 1 30); do
  if python /opt/keplerops/company_opa_adapter.py seed \
    --company-state /opt/keplerops/company-state.yaml >/dev/null 2>&1; then
    break
  fi
  [ "$attempt" -lt 30 ] || exit 1
  sleep 1
done
python /opt/keplerops/company_opa_adapter.py readback \
  --company-state /opt/keplerops/company-state.yaml >/dev/null
exec python -m uvicorn app:app --host 0.0.0.0 --port 8443 --no-access-log --no-proxy-headers --ssl-keyfile /run/tls/tls.key --ssl-certfile /run/tls/tls.crt
