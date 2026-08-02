#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT
# shellcheck source=../seeding/config.env
source "${ROOT}/seeding/config.env"

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
readonly DIRECTORY_DIR=/opt/stalwart/etc/directory
readonly DIRECTORY_SECRET=${DIRECTORY_DIR}/corp-ldap-bind.secret
readonly DIRECTORY_PAYLOAD=${ROOT}/seeding/payloads/stalwart-principals.json
readonly DIRECTORY_TRUST=${ROOT}/state/identity/truststores
readonly DC01=${KEPLEROPS_DC01_ADDRESS:-192.168.78.10}
readonly DC02=${KEPLEROPS_DC02_ADDRESS:-192.168.78.11}
readonly SSH_KEY=${KEPLEROPS_V2_SSH_KEY:-/root/.ssh/keplerops-v2}
readonly SSH=(ssh -i "${SSH_KEY}" -o BatchMode=yes -o ConnectTimeout=5 \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

for command in docker jq openssl ssh; do
  command -v "${command}" >/dev/null 2>&1 || {
    printf 'required command is unavailable: %s\n' "${command}" >&2
    exit 2
  }
done
[[ -r ${SSH_KEY} ]] || { printf 'SSH key is unreadable: %s\n' "${SSH_KEY}" >&2; exit 2; }
[[ -r ${DIRECTORY_PAYLOAD} ]] || {
  printf 'Stalwart directory payload is unreadable: %s\n' "${DIRECTORY_PAYLOAD}" >&2
  exit 2
}

directory_password() {
  local record=$1
  local variable password
  password="$(jq -r '.password // empty' <<<"${record}")"
  if [[ -z ${password} ]]; then
    variable="$(jq -r '.password_env // empty' <<<"${record}")"
    [[ -n ${variable} ]] || return 0
    password="${!variable:-}"
    [[ -n ${password} ]] || {
      printf 'directory password variable is empty: %s\n' "${variable}" >&2
      exit 2
    }
  fi
  printf '%s' "${password}"
}

reconcile_directory_principal() {
  local record=$1
  local source name description primary aliases ou password remote_command
  source="$(jq -er '.source' <<<"${record}")"
  name="$(jq -er '.name' <<<"${record}")"
  description="$(jq -r '.description // .name' <<<"${record}")"
  primary="$(jq -r '.emails[0] // empty' <<<"${record}")"
  aliases="$(jq -r '[.emails[1:][]?] | join("|")' <<<"${record}")"
  ou="$(jq -r '.ou // "People"' <<<"${record}")"
  password="$(directory_password "${record}")"

  printf -v remote_command \
    'sudo bash -s -- %q %q %q %q %q %q %q' \
    "${source}" "${name}" "${description}" "${primary}" "${aliases}" "${ou}" "${password}"
  "${SSH[@]}" "kepler@${DC01}" "${remote_command}" <<'REMOTE'
set -Eeuo pipefail

source_type=$1
username=$2
description=$3
primary_mail=$4
aliases=$5
ou=$6
password=$7

if [[ ${source_type} == corp-employee ]]; then
  samba-tool user show "${username}" >/dev/null 2>&1 || {
    printf 'required employee is absent from CORP: %s\n' "${username}" >&2
    exit 3
  }
else
  samba-tool ou add "OU=${ou}" >/dev/null 2>&1 || true
  if ! samba-tool user show "${username}" >/dev/null 2>&1; then
    create_args=(user create "${username}" "${password}" \
      "--userou=OU=${ou}" "--description=${description}")
    [[ -z ${primary_mail} ]] || create_args+=("--mail-address=${primary_mail}")
    samba-tool "${create_args[@]}" >/dev/null
  elif ! samba-tool user show "${username}" | grep -Fqi ",OU=${ou},DC="; then
    samba-tool user move "${username}" "OU=${ou}" >/dev/null
  fi
  samba-tool user setpassword "${username}" --newpassword="${password}" >/dev/null
  samba-tool user setexpiry "${username}" --noexpiry >/dev/null
  for privileged_group in \
    'Domain Admins' 'Enterprise Admins' 'Schema Admins' \
    'Group Policy Creator Owners' 'Account Operators' 'Server Operators' \
    'Backup Operators' 'Print Operators'; do
    samba-tool group removemembers "${privileged_group}" "${username}" >/dev/null 2>&1 || true
  done
fi

python3 - "${username}" "${description}" "${primary_mail}" "${aliases}" <<'PY'
import sys

import ldb
from samba.auth import system_session
from samba.param import LoadParm
from samba.samdb import SamDB

username, description, primary_mail, aliases = sys.argv[1:]
lp = LoadParm()
lp.load("/etc/samba/smb.conf")
database = SamDB(session_info=system_session(), lp=lp)
records = database.search(
    base=database.domain_dn(),
    expression=f"(sAMAccountName={ldb.binary_encode(username)})",
    attrs=["description", "mail", "otherMailbox"],
)
if len(records) != 1:
    raise SystemExit(f"expected one directory record for {username}, found {len(records)}")

message = ldb.Message()
message.dn = records[0].dn
message["description"] = ldb.MessageElement(
    description, ldb.FLAG_MOD_REPLACE, "description"
)
if primary_mail:
    message["mail"] = ldb.MessageElement(
        primary_mail, ldb.FLAG_MOD_REPLACE, "mail"
    )
alias_values = [value for value in aliases.split("|") if value]
if alias_values:
    message["otherMailbox"] = ldb.MessageElement(
        alias_values, ldb.FLAG_MOD_REPLACE, "otherMailbox"
    )
elif "otherMailbox" in records[0]:
    message["otherMailbox"] = ldb.MessageElement(
        [], ldb.FLAG_MOD_DELETE, "otherMailbox"
    )
database.modify(message)
PY

if [[ ${source_type} == corp-disabled ]]; then
  samba-tool user disable "${username}" >/dev/null
elif [[ ${source_type} != corp-employee ]]; then
  samba-tool user enable "${username}" >/dev/null
fi
REMOTE
}

if [[ ${1:-} != directory-config-only ]]; then
  while IFS= read -r record; do
    reconcile_directory_principal "${record}"
  done < <(jq -c '.[] | select((.source // "") | startswith("corp-"))' \
    "${DIRECTORY_PAYLOAD}")
fi

# Samba issues a private CA per DC. The guest reconciler exports those roots;
# install both into the running Stalwart image so LDAPS verifies normally.
directory_ca_changed=false
for dc in dc01 dc02; do
  ca_file="${DIRECTORY_TRUST}/${dc}-ca.pem"
  [[ -r ${ca_file} ]] || {
    printf 'directory CA is unavailable: %s\n' "${ca_file}" >&2
    exit 2
  }
  openssl x509 -in "${ca_file}" -noout >/dev/null
  expected_sha=$(sha256sum "${ca_file}" | awk '{print $1}')
  installed_sha=$(docker exec "${CONTAINER}" sha256sum \
    "/usr/local/share/ca-certificates/keplerops-${dc}.crt" 2>/dev/null |
    awk '{print $1}')
  [[ ${installed_sha} == "${expected_sha}" ]] || directory_ca_changed=true
  docker cp "${ca_file}" \
    "${CONTAINER}:/usr/local/share/ca-certificates/keplerops-${dc}.crt"
done
docker exec "${CONTAINER}" update-ca-certificates >/dev/null
docker exec "${CONTAINER}" sh -c \
  "grep -Fq '${DC01} dc01.corp.keplerops.lab' /etc/hosts || printf '%s\\n' '${DC01} dc01.corp.keplerops.lab dc01' >>/etc/hosts"
docker exec "${CONTAINER}" sh -c \
  "grep -Fq '${DC02} dc02.corp.keplerops.lab' /etc/hosts || printf '%s\\n' '${DC02} dc02.corp.keplerops.lab dc02' >>/etc/hosts"

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
config_owner=$(docker exec "$CONTAINER" stat -c '%u:%g' /opt/stalwart/etc/config.toml)

ldap_bind_secret="$(jq -er \
  '.[] | select(.name == "svc-stalwart-ldap") | .password' \
  "${DIRECTORY_PAYLOAD}")"
printf '%s' "${ldap_bind_secret}" >"${workdir}/corp-ldap-bind.secret"
docker exec "$CONTAINER" mkdir -p "$DIRECTORY_DIR"
docker cp "$workdir/corp-ldap-bind.secret" "$CONTAINER:$DIRECTORY_SECRET"
docker exec "$CONTAINER" chown "$config_owner" "$DIRECTORY_SECRET"
docker exec "$CONTAINER" chmod 0600 "$DIRECTORY_SECRET"

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
awk '
  /^\[directory\."corp-ldap"([.][^]]+)?\]$/ { skipping=1; next }
  skipping && /^\[/ { skipping=0 }
  skipping { next }
  $0 == "[storage]" { storage=1; print; next }
  storage && /^\[/ { storage=0 }
  storage && /^directory = / { print "directory = \"corp-ldap\""; next }
  { print }
' "$workdir/without-mail-certificate.toml" >"$workdir/updated.toml"
cat >>"$workdir/updated.toml" <<EOF

[certificate."keplerops-mail"]
cert = "%{file:${TLS_CERT}}%"
private-key = "%{file:${TLS_KEY}}%"
default = true

[directory."corp-ldap"]
type = "ldap"
url = "ldaps://dc01.corp.keplerops.lab:636"
base-dn = "DC=CORP,DC=KEPLEROPS,DC=LAB"
timeout = "10s"

[directory."corp-ldap".bind]
dn = "CN=svc-stalwart-ldap,OU=Service Accounts,DC=CORP,DC=KEPLEROPS,DC=LAB"
secret = "%{file:${DIRECTORY_SECRET}}%"

[directory."corp-ldap".bind.auth]
method = "lookup"

[directory."corp-ldap".filter]
name = "(&(objectClass=user)(mail=*)(!(objectClass=computer))(!(userAccountControl:1.2.840.113556.1.4.803:=2))(|(sAMAccountName=?)(mail=?)(otherMailbox=?)))"
email = "(&(objectClass=user)(mail=*)(!(objectClass=computer))(!(userAccountControl:1.2.840.113556.1.4.803:=2))(|(mail=?)(otherMailbox=?)))"

[directory."corp-ldap".attributes]
name = "sAMAccountName"
description = ["displayName", "description"]
secret-changed = "pwdLastSet"
groups = "memberOf"
email = "mail"
email-alias = "otherMailbox"
class = "objectClass"

[directory."corp-ldap".tls]
allow-invalid-certs = false

[directory."corp-ldap".pool]
max-connections = 20
timeout.create = "10s"
timeout.wait = "10s"
EOF

configuration_changed=false
if ! cmp -s "$workdir/source.toml" "$workdir/updated.toml"; then
  docker cp "$workdir/updated.toml" "$CONTAINER:/opt/stalwart/etc/config.toml"
  configuration_changed=true
fi

if [[ $configuration_changed == true || $certificate_valid != true || $directory_ca_changed == true ]]; then
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

# Docker regenerates /etc/hosts during a restart. Compose carries these records
# for normal convergence; repeat them here so this targeted reconciler is also
# sufficient on an already-running template.
docker exec "${CONTAINER}" sh -c \
  "grep -Fq '${DC01} dc01.corp.keplerops.lab' /etc/hosts || printf '%s\\n' '${DC01} dc01.corp.keplerops.lab dc01' >>/etc/hosts"
docker exec "${CONTAINER}" sh -c \
  "grep -Fq '${DC02} dc02.corp.keplerops.lab' /etc/hosts || printf '%s\\n' '${DC02} dc02.corp.keplerops.lab dc02' >>/etc/hosts"

echo "Stalwart administrator, verified LDAPS directory, and mail TLS certificate reconciled"
