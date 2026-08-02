#!/usr/bin/env bash
set -Eeuo pipefail

readonly CONTAINER=kep-v2-stalwart
readonly CADDY_CONTAINER=kep-v2-caddy
readonly ADMIN_USER=range-admin
# This is a literal SHA-crypt hash, not a shell expression.
# shellcheck disable=SC2016
readonly ADMIN_SECRET_HASH='$6$keplerops$03o.soEaGTag6lmbqkXBqPyYP.yoXaeYpEA1s3WaOQfwbdlmFvzwYD.AZ5Lw4Eqco4E5SLJr9BaG2Leejt6CX.'
readonly MAIL_HOST=mail.keplerops.lab
readonly TLS_DIR=/opt/stalwart/etc/tls
readonly TLS_CERT=${TLS_DIR}/mail.crt
readonly TLS_KEY=${TLS_DIR}/mail.key

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

deadline=$((SECONDS + 120))
until docker exec "$CONTAINER" test -f /opt/stalwart/etc/config.toml 2>/dev/null; do
  if ((SECONDS >= deadline)); then
    echo "Stalwart did not initialize its configuration" >&2
    exit 1
  fi
  sleep 2
done

docker cp "$CONTAINER:/opt/stalwart/etc/config.toml" "$workdir/source.toml"
cp "$workdir/source.toml" "$workdir/admin.toml"

current_user=$(awk '
  /^\[authentication\.fallback-admin\]$/ { found=1; next }
  found && /^user = / { gsub(/^user = "|"$/, ""); print; exit }
' "$workdir/source.toml")
current_secret=$(awk '
  /^\[authentication\.fallback-admin\]$/ { found=1; next }
  found && /^secret = / { gsub(/^secret = "|"$/, ""); print; exit }
' "$workdir/source.toml")

if [[ $current_user != "$ADMIN_USER" || $current_secret != "$ADMIN_SECRET_HASH" ]]; then
  awk -v admin_user="$ADMIN_USER" -v admin_secret="$ADMIN_SECRET_HASH" '
    /^\[authentication\.fallback-admin\]$/ { section=1; print; next }
    section && /^user = / { print "user = \"" admin_user "\""; next }
    section && /^secret = / {
      print "secret = \"" admin_secret "\""
      section=0
      next
    }
    { print }
  ' "$workdir/source.toml" >"$workdir/admin.toml"
fi

# Keep the leaf certificate beside Stalwart's durable configuration, but derive
# it from the range CA so a newly materialized range never carries a fixed key.
docker cp "$CADDY_CONTAINER:/data/caddy/pki/authorities/local/root.crt" \
  "$workdir/root.crt"
docker cp "$CADDY_CONTAINER:/data/caddy/pki/authorities/local/intermediate.crt" \
  "$workdir/intermediate.crt"
docker cp "$CADDY_CONTAINER:/data/caddy/pki/authorities/local/intermediate.key" \
  "$workdir/intermediate.key"

certificate_valid=false
if docker cp "$CONTAINER:$TLS_CERT" "$workdir/current.crt" >/dev/null 2>&1 && \
   docker cp "$CONTAINER:$TLS_KEY" "$workdir/current.key" >/dev/null 2>&1; then
  if openssl x509 -in "$workdir/current.crt" -noout -checkend 604800 >/dev/null 2>&1 && \
     openssl x509 -in "$workdir/current.crt" -noout -checkhost "$MAIL_HOST" >/dev/null 2>&1 && \
     openssl verify -CAfile "$workdir/root.crt" -untrusted "$workdir/intermediate.crt" \
       "$workdir/current.crt" >/dev/null 2>&1 && \
     [[ $(openssl x509 -in "$workdir/current.crt" -pubkey -noout | sha256sum) == \
        $(openssl pkey -in "$workdir/current.key" -pubout 2>/dev/null | sha256sum) ]]; then
    certificate_valid=true
  fi
fi

if [[ $certificate_valid != true ]]; then
  openssl req -new -newkey rsa:2048 -nodes \
    -subj "/CN=${MAIL_HOST}" \
    -keyout "$workdir/mail.key" -out "$workdir/mail.csr" >/dev/null 2>&1
  cat >"$workdir/mail.ext" <<EOF
subjectAltName=DNS:${MAIL_HOST}
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
EOF
  openssl x509 -req -in "$workdir/mail.csr" \
    -CA "$workdir/intermediate.crt" -CAkey "$workdir/intermediate.key" \
    -CAcreateserial -days 365 -sha256 -extfile "$workdir/mail.ext" \
    -out "$workdir/mail-leaf.crt" >/dev/null 2>&1
  cat "$workdir/mail-leaf.crt" "$workdir/intermediate.crt" >"$workdir/mail.crt"

  docker exec "$CONTAINER" mkdir -p "$TLS_DIR"
  docker cp "$workdir/mail.crt" "$CONTAINER:$TLS_CERT"
  docker cp "$workdir/mail.key" "$CONTAINER:$TLS_KEY"
  config_owner=$(docker exec "$CONTAINER" stat -c '%u:%g' /opt/stalwart/etc/config.toml)
  docker exec "$CONTAINER" chown "$config_owner" "$TLS_CERT" "$TLS_KEY"
  docker exec "$CONTAINER" chmod 0644 "$TLS_CERT"
  docker exec "$CONTAINER" chmod 0600 "$TLS_KEY"
fi

# Stalwart 0.13 selects certificates by SNI and uses the declared default when
# a mail client omits SNI. Replacing this one owned section keeps convergence
# deterministic without disturbing product-managed configuration.
awk '
  skipping && /^\[/ { skipping=0 }
  !skipping && $0 == "[certificate.\"keplerops-mail\"]" { skipping=1; next }
  !skipping { print }
' "$workdir/admin.toml" >"$workdir/without-mail-certificate.toml"
cat "$workdir/without-mail-certificate.toml" >"$workdir/updated.toml"
cat >>"$workdir/updated.toml" <<EOF

[certificate."keplerops-mail"]
cert = "%{file:${TLS_CERT}}%"
private-key = "%{file:${TLS_KEY}}%"
default = true
EOF

configuration_changed=false
if ! cmp -s "$workdir/source.toml" "$workdir/updated.toml"; then
  docker cp "$workdir/updated.toml" "$CONTAINER:/opt/stalwart/etc/config.toml"
  configuration_changed=true
fi

if [[ $configuration_changed == true || $certificate_valid != true ]]; then
  docker restart "$CONTAINER" >/dev/null
  deadline=$((SECONDS + 120))
  until timeout 2 bash -c 'exec 3<>/dev/tcp/10.61.10.20/25' 2>/dev/null; do
    if ((SECONDS >= deadline)); then
      docker logs --tail 100 "$CONTAINER" >&2
      echo "Stalwart did not become ready after TLS reconciliation" >&2
      exit 1
    fi
    sleep 2
  done
fi

echo "Stalwart administrator and range-CA TLS certificate reconciled"
