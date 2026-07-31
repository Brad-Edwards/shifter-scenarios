#!/bin/sh
set -eu
umask 077
mkdir -p /var/lib/keplerops-research/otel
mkdir -p /var/lib/keplerops-research/company-state
company_export=/var/lib/keplerops-research/company-state/operations.jsonl
python /opt/keplerops/company_telemetry_adapter.py prepare \
  --company-state /opt/keplerops/company-state.yaml \
  --export "$company_export"
/usr/local/bin/otelcol-contrib --config=/etc/keplerops/otel.yaml &
printf '%s\n' "$!" >/var/lib/keplerops-research/otel/collector.pid
for attempt in $(seq 1 30); do
  if python /opt/keplerops/company_telemetry_adapter.py seed \
    --company-state /opt/keplerops/company-state.yaml \
    --export "$company_export" >/dev/null 2>&1; then
    break
  fi
  [ "$attempt" -lt 30 ] || exit 1
  sleep 1
done
python /opt/keplerops/company_telemetry_adapter.py readback \
  --company-state /opt/keplerops/company-state.yaml \
  --export "$company_export" >/dev/null
python -m uvicorn app:app --host 0.0.0.0 --port 4319 --no-access-log --no-proxy-headers \
  --ssl-keyfile /run/tls/tls.key --ssl-certfile /run/tls/tls.crt \
  --ssl-ca-certs /run/tls/ca.crt --ssl-cert-reqs 2 &
exec python -m uvicorn app:app --host 0.0.0.0 --port 8443 --no-access-log --no-proxy-headers --ssl-keyfile /run/tls/tls.key --ssl-certfile /run/tls/tls.crt
