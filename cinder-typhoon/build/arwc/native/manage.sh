#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $(hostname) == cinder-arwc-dev ]] || {
  echo 'This mutable deployment is restricted to cinder-arwc-dev.' >&2
  exit 1
}
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
# shellcheck disable=SC1091
source images.env
compose=(docker compose --env-file images.env -f compose.yaml -f corporate.compose.yaml -f dmz.compose.yaml)
hostnames=(edge.arwc.test erp.arwc.test identity.arwc.test documents.arwc.test reports.arwc.test engineering.arwc.test suppliers.arwc.test render.arwc.test read-data.arwc.test)
certificate_is_current() {
  [[ -f .operator/ca/tls/server.crt ]] || return 1
  openssl x509 -in .operator/ca/tls/server.crt -noout -checkend 86400 >/dev/null || return 1
  for hostname in "${hostnames[@]}"; do
    openssl verify -verify_hostname "$hostname" \
      -CAfile .operator/ca/certs/root_ca.crt -untrusted .operator/ca/certs/intermediate_ca.crt \
      .operator/ca/tls/server.crt >/dev/null 2>&1 || return 1
  done
}
action=${1:-up}
case "$action" in
  build)
    python3 prepare.py
    "${compose[@]}" pull --ignore-buildable
    "${compose[@]}" build dns kerberos workplace
    ;;
  up)
    python3 prepare.py
    if [[ ! -f .operator/ca/config/ca.json ]]; then
      docker run --pull never --rm --user 0:0 --network none --entrypoint step \
        -v "$PWD/.operator/ca:/home/step" "$STEP_CA_IMAGE" \
        ca init --deployment-type standalone --name 'ARWC Certificate Authority' \
        --dns ca.arwc.test --address :9000 --provisioner infrastructure \
        --password-file /home/step/secrets/password >/dev/null 2>&1
    fi
    if ! certificate_is_current; then
      mkdir -p .operator/ca/tls
      sans=()
      for hostname in "${hostnames[@]}"; do sans+=(--san "$hostname"); done
      docker run --pull never --rm --user 0:0 --network none --entrypoint step \
        -v "$PWD/.operator/ca:/home/step" "$STEP_CA_IMAGE" \
        certificate create edge.arwc.test /home/step/tls/server.crt /home/step/tls/server.key \
        --profile leaf --ca /home/step/certs/intermediate_ca.crt \
        --ca-key /home/step/secrets/intermediate_ca_key \
        --ca-password-file /home/step/secrets/password --not-after 8760h \
        "${sans[@]}" \
        --no-password --insecure --force >/dev/null
      cat .operator/ca/certs/intermediate_ca.crt >> .operator/ca/tls/server.crt
    fi
    chown -R 1000:1000 .operator/ca
    chmod 0755 .operator/ca/tls
    chown -R root:root .operator/ca/tls
    bash corporate-access.sh prepare
    "${compose[@]}" up --no-build --pull never --wait --wait-timeout 420
    "${compose[@]}" exec -T --user www-data nextcloud php occ background:cron
    bash desktop-access.sh
    bash corporate-access.sh trust
    ;;
  status)
    "${compose[@]}" ps
    ;;
  seed)
    "${compose[@]}" exec -T corporate-db psql -U corporate -d planning \
      --set ON_ERROR_STOP=1 < planning.sql
    "${compose[@]}" --profile seed run --rm seed-erp
    ;;
  seed-corporate-documents)
    python3 import-corporate-documents.py
    ;;
  seed-documents)
    "${compose[@]}" --profile seed run --rm seed-documents
    ;;
  seed-reports)
    "${compose[@]}" --profile seed run --rm seed-reports
    ;;
  seed-engineering)
    bash seed-engineering.sh
    ;;
  seed-dmz)
    "${compose[@]}" exec -T --user postgres corporate-db bash -s < init-corporate.sh
    "${compose[@]}" exec -T corporate-db psql -U corporate -d planning \
      --set ON_ERROR_STOP=1 < dmz-views.sql
    ;;
  seed-portal)
    "${compose[@]}" --profile seed run --rm seed-portal
    ;;
  seed-early-cards)
    "${compose[@]}" --profile seed run --rm seed-early-cards
    ;;
  seed-identity)
    "${compose[@]}" --profile seed run --rm seed-identity
    ;;
  reset)
    [[ ${2-} == cinder-arwc-native ]] || {
      echo 'Reset requires the exact project name: reset cinder-arwc-native' >&2
      exit 2
    }
    "${compose[@]}" down --volumes
    bash "$0" up
    bash "$0" seed
    bash "$0" seed-dmz
    bash "$0" seed-documents
    bash "$0" seed-reports
    bash "$0" seed-portal
    bash "$0" seed-early-cards
    bash "$0" seed-identity
    bash "$0" seed-engineering
    exec bash "$0" seed-corporate-documents
    ;;
  *) echo 'Usage: manage.sh build|up|status|seed|seed-documents|seed-corporate-documents|seed-reports|seed-engineering|seed-dmz|seed-portal|seed-early-cards|seed-identity|reset cinder-arwc-native' >&2; exit 2 ;;
esac
