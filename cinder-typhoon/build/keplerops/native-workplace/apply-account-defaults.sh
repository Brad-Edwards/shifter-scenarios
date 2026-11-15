#!/usr/bin/env bash
set -euo pipefail
docker exec -i --user 1000:1000 cinder-keplerops-keycloak sh -eu <<'KEYCLOAK'
umask 077
configuration=$(mktemp /tmp/fieldlink-account-admin.XXXXXX)
trap 'rm -f -- "$configuration"' EXIT
printf '%s\n' "$KC_BOOTSTRAP_ADMIN_PASSWORD" | /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://127.0.0.1:8080 --realm master \
  --user "$KC_BOOTSTRAP_ADMIN_USERNAME" --config "$configuration" >/dev/null 2>&1
/opt/keycloak/bin/kcadm.sh add-roles -r keplerops --uusername rowan.ito \
  --rolename default-roles-keplerops --config "$configuration"
KEYCLOAK
echo 'Native account self-service defaults applied.'
