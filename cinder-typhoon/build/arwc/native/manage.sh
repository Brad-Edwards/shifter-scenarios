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
compose=(docker compose --env-file images.env -f compose.yaml -f corporate.compose.yaml)
action=${1:-up}
case "$action" in
  up)
    python3 prepare.py
    if [[ ! -f .operator/ca/config/ca.json ]]; then
      docker run --rm --user 0:0 --network none --entrypoint step \
        -v "$PWD/.operator/ca:/home/step" "$STEP_CA_IMAGE" \
        ca init --deployment-type standalone --name 'ARWC Certificate Authority' \
        --dns ca.arwc.test --address :9000 --provisioner infrastructure \
        --password-file /home/step/secrets/password >/dev/null 2>&1
    fi
    if [[ ! -f .operator/ca/tls/server.crt ]] ||
        ! openssl x509 -in .operator/ca/tls/server.crt -noout -checkhost documents.arwc.test >/dev/null ||
        ! openssl x509 -in .operator/ca/tls/server.crt -noout -checkend 86400 >/dev/null; then
      mkdir -p .operator/ca/tls
      docker run --rm --user 0:0 --network none --entrypoint step \
        -v "$PWD/.operator/ca:/home/step" "$STEP_CA_IMAGE" \
        certificate create edge.arwc.test /home/step/tls/server.crt /home/step/tls/server.key \
        --profile leaf --ca /home/step/certs/intermediate_ca.crt \
        --ca-key /home/step/secrets/intermediate_ca_key \
        --ca-password-file /home/step/secrets/password --not-after 8760h \
        --san edge.arwc.test --san erp.arwc.test --san identity.arwc.test \
        --san documents.arwc.test --san reports.arwc.test --san engineering.arwc.test \
        --no-password --insecure --force >/dev/null
      cat .operator/ca/certs/intermediate_ca.crt >> .operator/ca/tls/server.crt
    fi
    chown -R 1000:1000 .operator/ca
    chmod 0755 .operator/ca/tls
    chown -R root:root .operator/ca/tls
    "${compose[@]}" build dns kerberos
    "${compose[@]}" up -d
    bash desktop-access.sh
    ;;
  status)
    "${compose[@]}" ps
    ;;
  seed)
    "${compose[@]}" exec -T corporate-db psql -U corporate -d planning \
      --set ON_ERROR_STOP=1 < planning.sql
    "${compose[@]}" --profile seed run --rm seed-erp
    ;;
  reset)
    [[ ${2-} == cinder-arwc-native ]] || {
      echo 'Reset requires the exact project name: reset cinder-arwc-native' >&2
      exit 2
    }
    "${compose[@]}" down --volumes
    bash "$0" up
    exec bash "$0" seed
    ;;
  *) echo 'Usage: manage.sh up|status|seed|reset cinder-arwc-native' >&2; exit 2 ;;
esac
