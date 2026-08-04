#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly KEY=/root/.ssh/keplerops-v2
readonly SSH=(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
readonly SCP=(scp -i "$KEY" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
readonly GUEST_ASSETS="$ROOT/guests"
readonly RABBIT_API=http://10.61.50.12:15672/api
readonly RABBIT_ADMIN_USER=kepler
readonly RABBIT_ADMIN_PASSWORD=KeplerV2-Training-Rabbit
readonly REVIEW_RABBIT_PASSWORD=KeplerV2-Worker-Review01-Rabbit
readonly INTEGRATION_RABBIT_PASSWORD=KeplerV2-Worker-Integration01-Rabbit
readonly CHECK_RABBIT_PASSWORD=KeplerV2-Worker-Verification-Rabbit

if [[ ${EUID} -ne 0 ]]; then
  echo "reconcile-guests.sh must run as root" >&2
  exit 2
fi

configure_directory_tls() {
  local state_dir="${ROOT}/state/identity/directory-tls"
  local ca_key="${state_dir}/ca.key" ca_cert="${state_dir}/ca.pem"
  local record name address work remote_cert remote_ca ext

  install -d -m 0700 "${state_dir}"
  if [[ ! -s ${ca_key} || ! -s ${ca_cert} ]]; then
    openssl req -x509 -new -newkey rsa:3072 -nodes -sha256 -days 3650 \
      -subj '/O=KeplerOps AI Systems/CN=KeplerOps Directory TLS CA' \
      -addext 'basicConstraints=critical,CA:TRUE' \
      -addext 'keyUsage=critical,keyCertSign,cRLSign' \
      -keyout "${ca_key}.next" -out "${ca_cert}.next" >/dev/null 2>&1
    install -m 0600 "${ca_key}.next" "${ca_key}"
    install -m 0644 "${ca_cert}.next" "${ca_cert}"
    rm -f "${ca_key}.next" "${ca_cert}.next"
  fi
  openssl verify -CAfile "${ca_cert}" "${ca_cert}" >/dev/null

  for record in dc01:192.168.78.10 dc02:192.168.78.11; do
    name=${record%%:*}
    address=${record#*:}
    work=$(mktemp -d)
    remote_cert="${work}/cert.pem"
    remote_ca="${work}/ca.pem"
    "${SSH[@]}" "kepler@${address}" \
      'sudo cat /var/lib/samba/private/tls/cert.pem' >"${remote_cert}"
    "${SSH[@]}" "kepler@${address}" \
      'sudo cat /var/lib/samba/private/tls/ca.pem' >"${remote_ca}"
    if cmp -s "${ca_cert}" "${remote_ca}" && \
      openssl verify -CAfile "${ca_cert}" "${remote_cert}" >/dev/null 2>&1 && \
      openssl x509 -in "${remote_cert}" -noout -checkend 2592000 >/dev/null && \
      openssl x509 -in "${remote_cert}" -noout -ext subjectAltName 2>/dev/null |
        grep -Fq "DNS:${name}.corp.keplerops.lab"; then
      rm -rf "${work}"
      continue
    fi

    openssl req -new -newkey rsa:3072 -nodes -sha256 \
      -subj "/O=KeplerOps AI Systems/CN=${name}.corp.keplerops.lab" \
      -keyout "${work}/key.pem" -out "${work}/request.csr" >/dev/null 2>&1
    ext="${work}/extensions.cnf"
    cat >"${ext}" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:${name}.corp.keplerops.lab,DNS:${name},IP:${address}
EOF
    openssl x509 -req -in "${work}/request.csr" \
      -CA "${ca_cert}" -CAkey "${ca_key}" -CAcreateserial \
      -days 825 -sha256 -extfile "${ext}" -out "${work}/cert.pem" >/dev/null 2>&1
    openssl verify -CAfile "${ca_cert}" "${work}/cert.pem" >/dev/null
    "${SCP[@]}" "${work}/cert.pem" "${work}/key.pem" "${ca_cert}" \
      "kepler@${address}:/tmp/" >/dev/null
    "${SSH[@]}" "kepler@${address}" sudo bash -s <<'REMOTE'
set -euo pipefail
install -m 0644 /tmp/cert.pem /var/lib/samba/private/tls/cert.pem
install -m 0600 /tmp/key.pem /var/lib/samba/private/tls/key.pem
install -m 0644 /tmp/ca.pem /var/lib/samba/private/tls/ca.pem
rm -f /tmp/cert.pem /tmp/key.pem /tmp/ca.pem
systemctl restart samba-ad-dc
for _ in $(seq 1 60); do
  timeout 1 bash -c '</dev/tcp/127.0.0.1/636' 2>/dev/null && exit 0
  sleep 1
done
exit 1
REMOTE
    rm -rf "${work}"
  done

  install -d -m 0755 "${ROOT}/state/identity/truststores"
  install -m 0644 "${ca_cert}" "${ROOT}/state/identity/truststores/dc01-ca.pem"
  install -m 0644 "${ca_cert}" "${ROOT}/state/identity/truststores/dc02-ca.pem"
}

if [[ ${1:-} == directory-tls-only ]]; then
  configure_directory_tls
  exit 0
fi

rabbit_api() {
  local method=$1 path=$2 body=${3:-}
  if [[ -n $body ]]; then
    curl -fsS --retry 12 --retry-delay 2 \
      -u "$RABBIT_ADMIN_USER:$RABBIT_ADMIN_PASSWORD" \
      -H 'Content-Type: application/json' -X "$method" \
      "$RABBIT_API$path" --data "$body" >/dev/null
  else
    curl -fsS --retry 12 --retry-delay 2 \
      -u "$RABBIT_ADMIN_USER:$RABBIT_ADMIN_PASSWORD" \
      -X "$method" "$RABBIT_API$path" >/dev/null
  fi
}

configure_review_queues() {
  rabbit_api PUT /queues/keplerops/orion.review.review01 \
    '{"durable":true,"auto_delete":false,"arguments":{}}'
  rabbit_api PUT /queues/keplerops/orion.review.integration01 \
    '{"durable":true,"auto_delete":false,"arguments":{}}'
  rabbit_api PUT /queues/keplerops/orion.review.results \
    '{"durable":true,"auto_delete":false,"arguments":{}}'

  rabbit_api PUT /users/svc-review01 \
    "{\"password\":\"$REVIEW_RABBIT_PASSWORD\",\"tags\":\"\"}"
  rabbit_api PUT /permissions/keplerops/svc-review01 \
    '{"configure":"^orion\\.review\\.review01$","write":"^(amq\\.default|orion\\.review\\.results(\\.[A-Za-z0-9][A-Za-z0-9._:-]{2,127})?)$","read":"^orion\\.review\\.review01$"}'

  rabbit_api PUT /users/svc-integration01 \
    "{\"password\":\"$INTEGRATION_RABBIT_PASSWORD\",\"tags\":\"\"}"
  rabbit_api PUT /permissions/keplerops/svc-integration01 \
    '{"configure":"^orion\\.review\\.integration01$","write":"^(amq\\.default|orion\\.review\\.results(\\.[A-Za-z0-9][A-Za-z0-9._:-]{2,127})?)$","read":"^orion\\.review\\.integration01$"}'

  rabbit_api PUT /users/svc-review-verification \
    "{\"password\":\"$CHECK_RABBIT_PASSWORD\",\"tags\":\"management\"}"
  rabbit_api PUT /permissions/keplerops/svc-review-verification \
    '{"configure":"^orion\\.review\\.(review01|integration01|results(\\.[A-Za-z0-9][A-Za-z0-9._:-]{2,127})?)$","write":"^amq\\.default$","read":"^orion\\.review\\.(review01|integration01|results(\\.[A-Za-z0-9][A-Za-z0-9._:-]{2,127})?)$"}'
}

install_review_worker() {
  local address=$1 worker_name=$2 queue=$3 rabbit_user=$4 rabbit_password=$5
  local workhub_user=$6 workhub_password=$7

  "${SCP[@]}" "$GUEST_ASSETS/review-worker.py" \
    "kepler@$address:/tmp/review-worker.py" >/dev/null
  "${SCP[@]}" "$GUEST_ASSETS/orion-review-worker.service" \
    "kepler@$address:/tmp/orion-review-worker.service" >/dev/null
  "${SSH[@]}" "kepler@$address" sudo bash -s <<'REMOTE'
set -euo pipefail
if ! python3 -c 'import pika, requests' >/dev/null 2>&1 ||
  ! command -v pdftotext >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get -o Acquire::ForceIPv4=true update -q
  apt-get -o Acquire::ForceIPv4=true install -y poppler-utils python3-pika python3-requests
fi
id -u orion-review >/dev/null 2>&1 ||
  useradd --system --home /var/lib/keplerops/review-worker \
    --shell /usr/sbin/nologin orion-review
install -d -m 0750 -o orion-review -g orion-review /var/lib/keplerops/review-worker
install -d -m 0755 /usr/local/lib/keplerops /etc/keplerops
install -m 0755 /tmp/review-worker.py /usr/local/lib/keplerops/review-worker.py
install -m 0644 /tmp/orion-review-worker.service /etc/systemd/system/orion-review-worker.service
rm -f /tmp/review-worker.py /tmp/orion-review-worker.service
REMOTE

  cat <<EOF | "${SSH[@]}" "kepler@$address" \
    'cat >/tmp/orion-review-worker.env && sudo install -m 0640 -o root -g orion-review /tmp/orion-review-worker.env /etc/keplerops/orion-review-worker.env && rm -f /tmp/orion-review-worker.env'
REVIEW_WORKER_NAME="$worker_name"
RABBITMQ_URL=amqp://$rabbit_user:$rabbit_password@192.168.78.1:15673/keplerops
RABBITMQ_QUEUE=$queue
RABBITMQ_RESULT_QUEUE=orion.review.results
ORION_AGENT_URL=http://192.168.78.1:13081/v1/chat
ORION_AGENT_API_KEY=KAI-Orion-Agent-Runtime-8f4c1a7d29e6b053
ORION_ACTOR=workhub-service
ORION_ASSISTANT_RELEASE_ID=sha256:$(printf unresolved-assistant-release | sha256sum | awk '{print $1}')
ORION_ASSISTANT_MODEL_DIGEST=sha256:$(printf unresolved-assistant-model | sha256sum | awk '{print $1}')
OTLP_HTTP_URL=http://10.61.80.10:4318
WORKHUB_URL=http://192.168.78.1:13000
WORKHUB_HOST=workhub.keplerops.lab
WORKHUB_USER=$workhub_user
WORKHUB_PASSWORD=$workhub_password
WORKHUB_PROJECT=orion
EOF

  "${SSH[@]}" "kepler@$address" sudo bash -s <<'REMOTE'
set -euo pipefail
systemd-analyze verify /etc/systemd/system/orion-review-worker.service
set -a
. /etc/keplerops/orion-review-worker.env
set +a
sudo -u orion-review --preserve-env \
  /usr/local/lib/keplerops/review-worker.py self-test >/dev/null
systemctl daemon-reload
systemctl enable --now orion-review-worker.service >/dev/null
systemctl restart orion-review-worker.service
systemctl is-active --quiet orion-review-worker.service
REMOTE
}

"${SSH[@]}" kepler@192.168.78.10 sudo bash -s <<'REMOTE'
set -euo pipefail
systemctl disable --now systemd-resolved >/dev/null 2>&1 || true
rm -f /etc/resolv.conf
printf 'search corp.keplerops.lab\nnameserver 127.0.0.1\nnameserver 192.168.78.11\n' >/etc/resolv.conf
sed -i -E '/[[:space:]]dc0[12](\.corp\.keplerops\.lab)?([[:space:]]|$)/d' /etc/hosts
printf '192.168.78.10 dc01.corp.keplerops.lab dc01\n192.168.78.11 dc02.corp.keplerops.lab dc02\n' >>/etc/hosts
if ! grep -Eq '^[[:space:]]*dns forwarder[[:space:]]*=[[:space:]]*192\.168\.78\.1[[:space:]]*$' /etc/samba/smb.conf; then
  awk '
    /^\[global\]$/ {
      print
      print "\tdns forwarder = 192.168.78.1"
      next
    }
    /^[[:space:]]*t?dns forwarder[[:space:]]*=/ { next }
    { print }
  ' /etc/samba/smb.conf >/etc/samba/smb.conf.reconciled
  install -m 0644 /etc/samba/smb.conf.reconciled /etc/samba/smb.conf
  rm -f /etc/samba/smb.conf.reconciled
  systemctl restart samba-ad-dc
fi
samba_dnsupdate --use-samba-tool

samba-tool group add Engineering >/dev/null 2>&1 || true
samba-tool group add AI-Research >/dev/null 2>&1 || true
samba-tool group add Release-Engineering >/dev/null 2>&1 || true
samba-tool group add Communications >/dev/null 2>&1 || true
samba-tool group add Support >/dev/null 2>&1 || true
samba-tool user create comms.publisher 'KeplerV2-Training-Comms' \
  --given-name=Samira --surname=Okafor >/dev/null 2>&1 || true
samba-tool group addmembers Communications comms.publisher >/dev/null 2>&1 || true

testparm -s /etc/samba/smb.conf >/dev/null
samba-tool domain info 127.0.0.1 >/dev/null
REMOTE

"${SSH[@]}" kepler@192.168.78.11 sudo bash -s <<'REMOTE'
set -euo pipefail
systemctl disable --now systemd-resolved >/dev/null 2>&1 || true
rm -f /etc/resolv.conf
printf 'search corp.keplerops.lab\nnameserver 127.0.0.1\nnameserver 192.168.78.10\n' >/etc/resolv.conf
sed -i -E '/[[:space:]]dc0[12](\.corp\.keplerops\.lab)?([[:space:]]|$)/d' /etc/hosts
printf '192.168.78.10 dc01.corp.keplerops.lab dc01\n192.168.78.11 dc02.corp.keplerops.lab dc02\n' >>/etc/hosts
if ! grep -Eq '^[[:space:]]*dns forwarder[[:space:]]*=[[:space:]]*192\.168\.78\.1[[:space:]]*$' /etc/samba/smb.conf; then
  awk '
    /^\[global\]$/ {
      print
      print "\tdns forwarder = 192.168.78.1"
      next
    }
    /^[[:space:]]*t?dns forwarder[[:space:]]*=/ { next }
    { print }
  ' /etc/samba/smb.conf >/etc/samba/smb.conf.reconciled
  install -m 0644 /etc/samba/smb.conf.reconciled /etc/samba/smb.conf
  rm -f /etc/samba/smb.conf.reconciled
  systemctl restart samba-ad-dc
fi
samba_dnsupdate --use-samba-tool
testparm -s /etc/samba/smb.conf >/dev/null
samba-tool domain info 127.0.0.1 >/dev/null
REMOTE

configure_directory_tls

"$ROOT/scripts/reconcile-directory-roles.sh"

"${SSH[@]}" kepler@192.168.78.10 sudo bash -s <<'REMOTE'
set -euo pipefail
for naming_context in \
  'DC=corp,DC=keplerops,DC=lab' \
  'CN=Configuration,DC=corp,DC=keplerops,DC=lab' \
  'CN=Schema,CN=Configuration,DC=corp,DC=keplerops,DC=lab' \
  'DC=DomainDnsZones,DC=corp,DC=keplerops,DC=lab' \
  'DC=ForestDnsZones,DC=corp,DC=keplerops,DC=lab'; do
  timeout 30 samba-tool drs replicate \
    dc01.corp.keplerops.lab dc02.corp.keplerops.lab "$naming_context" --sync-forced >/dev/null
  timeout 30 samba-tool drs replicate \
    dc02.corp.keplerops.lab dc01.corp.keplerops.lab "$naming_context" --sync-forced >/dev/null
done
REMOTE

trust_dir="$ROOT/state/identity/truststores"
install -d -m 0755 "$trust_dir"
for dc in dc01:192.168.78.10 dc02:192.168.78.11; do
  name=${dc%%:*}
  address=${dc#*:}
  temporary=$(mktemp)
  "${SSH[@]}" "kepler@${address}" \
    'sudo cat /var/lib/samba/private/tls/ca.pem' >"$temporary"
  openssl x509 -in "$temporary" -noout >/dev/null
  install -m 0644 "$temporary" "$trust_dir/${name}-ca.pem"
  rm -f "$temporary"
done

configure_review_queues
install_review_worker \
  192.168.78.20 'Orion Evaluation Review' orion.review.review01 \
  svc-review01 "$REVIEW_RABBIT_PASSWORD" svc.review01 KAI-Review01-WorkHub-c72b918e
install_review_worker \
  192.168.78.21 'Orion Integration Review' orion.review.integration01 \
  svc-integration01 "$INTEGRATION_RABBIT_PASSWORD" svc.integration01 KAI-Integration01-WorkHub-a4653d2f

install -d -m 0700 "$ROOT/state/guests"
cat >"$ROOT/state/guests/review-verification.env" <<EOF
RABBITMQ_MANAGEMENT_URL=$RABBIT_API
RABBITMQ_USER=svc-review-verification
RABBITMQ_PASSWORD=$CHECK_RABBIT_PASSWORD
WORKHUB_URL=http://192.168.78.1:13000
WORKHUB_HOST=workhub.keplerops.lab
REVIEW_WORKHUB_USER=svc.review01
REVIEW_WORKHUB_PASSWORD=KAI-Review01-WorkHub-c72b918e
INTEGRATION_WORKHUB_USER=svc.integration01
INTEGRATION_WORKHUB_PASSWORD=KAI-Integration01-WorkHub-a4653d2f
EOF
chmod 0600 "$ROOT/state/guests/review-verification.env"

echo "campaign-v2 guest configuration and review workers reconciled"
