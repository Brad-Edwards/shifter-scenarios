#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
OPERATOR_DIR=${KEPLEROPS_OPERATOR_DIR:-"$ROOT/.operator"}
CA="$OPERATOR_DIR/native-workplace/ca"
image=$(docker compose -f "$ROOT/compose.yaml" config --images | awk '/^smallstep\/step-ca:/ {print; exit}')
[[ -n "$image" ]] || { echo 'Native CA image is not configured.' >&2; exit 1; }
if ! docker image inspect "$image" >/dev/null 2>&1; then docker pull "$image"; fi
if [[ ! -f "$CA/config/ca.json" ]]; then
  docker run --pull never --rm --user 0:0 --network none --entrypoint step \
    -v "$CA:/home/step" "$image" \
    ca init --deployment-type standalone --name 'FieldKest Enrollment CA' \
    --dns ca.keplerops.test --dns cert.keplerops.test --address :9000 \
    --provisioner infrastructure --password-file /home/step/secrets/password >/dev/null 2>&1
fi
certificate_current() {
  [[ -f "$CA/tls/server.crt" ]] || return 1
  openssl x509 -in "$CA/tls/server.crt" -noout -checkend 86400 >/dev/null || return 1
  for name in ca.keplerops.test cert.keplerops.test; do
    openssl verify -verify_hostname "$name" -CAfile "$CA/certs/root_ca.crt" \
      -untrusted "$CA/certs/intermediate_ca.crt" "$CA/tls/server.crt" >/dev/null 2>&1 || return 1
  done
}
if ! certificate_current; then
  mkdir -p "$CA/tls"
  docker run --pull never --rm --user 0:0 --network none --entrypoint step \
    -v "$CA:/home/step" "$image" \
    certificate create ca.keplerops.test /home/step/tls/server.crt /home/step/tls/server.key \
    --profile leaf --ca /home/step/certs/intermediate_ca.crt \
    --ca-key /home/step/secrets/intermediate_ca_key \
    --ca-password-file /home/step/secrets/password --not-after 8760h \
    --san ca.keplerops.test --san cert.keplerops.test \
    --no-password --insecure --force >/dev/null
  cat "$CA/certs/intermediate_ca.crt" >> "$CA/tls/server.crt"
fi
python3 "$ROOT/native-workplace/prepare.py" --operator-dir "$OPERATOR_DIR" --ca-config
chown -R 1000:1000 "$CA"
# PostgreSQL and CA application data reset through their named volumes. The CA
# keys and initial account inputs remain private operator material.
docker volume create --label com.docker.compose.project=cinder-keplerops \
  --label com.docker.compose.volume=native-ca-data cinder-keplerops-native-ca-data >/dev/null
docker run --pull never --rm --user 0:0 --network none --entrypoint sh \
  -v cinder-keplerops-native-ca-data:/home/step/db "$image" \
  -c 'chown 1000:1000 /home/step/db'
chown -R root:root "$CA/tls"
chmod 0755 "$CA/tls"
chmod 0644 "$CA/certs/root_ca.crt" "$CA/tls/server.crt"
chmod 0600 "$CA/tls/server.key"
# K19.2 mTLS: foundation-edge verifies the enrollment client certificate. The
# enrollment leaf certs are signed by the intermediate CA, so the nginx
# client-CA file must contain the intermediate and the root. Build that bundle.
cat "$CA/certs/intermediate_ca.crt" "$CA/certs/root_ca.crt" > "$CA/certs/enrollment_client_ca.crt"
chmod 0644 "$CA/certs/enrollment_client_ca.crt"
