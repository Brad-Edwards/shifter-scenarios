#!/usr/bin/env bash
set -euo pipefail

pdns() {
  docker exec kep-v2-pdns-auth pdnsutil "$@"
}

for zone in keplerops.lab cinder.lab; do
  pdns create-zone "$zone" ns1."$zone" 2>/dev/null || true
  pdns replace-rrset "$zone" ns1 A 60 10.61.10.10
done

for name in @ www id git workhub files support assistant preview intake status \
  advisories grafana jaeger pypi npm registry notebooks labels airflow mlflow \
  pipelines objects lake vectors argocd models orion-agent orion-mcp risk-model; do
  pdns replace-rrset keplerops.lab "$name" A 60 10.61.10.2
done
pdns replace-rrset keplerops.lab mail A 60 10.61.10.20
pdns replace-rrset keplerops.lab @ MX 60 '10 mail.keplerops.lab.'
pdns replace-rrset keplerops.lab @ TXT 60 '"v=spf1 mx -all"'

for name in @ mail git objects notebook relay model; do
  pdns replace-rrset cinder.lab "$name" A 60 10.61.90.2
done

pdns check-zone keplerops.lab
pdns check-zone cinder.lab
docker exec kep-v2-pdns-recursor rec_control wipe-cache keplerops.lab cinder.lab >/dev/null
echo "campaign-v2 public and Cinder DNS seeded"
