#!/bin/bash
# POLARIS bake-range bootstrap
# Installs Docker + docker-compose, pulls the polaris build tarball from S3,
# edits docker-compose.yml to publish Kali's 22 + 3389 to the EC2 host,
# then `docker compose up -d` so the whole range comes online.
set -euo pipefail
exec > >(tee /var/log/polaris-bootstrap.log) 2>&1

echo "=== polaris bootstrap starting $(date -u +%FT%TZ) ==="

export DEBIAN_FRONTEND=noninteractive

# Give apt a moment to finish any on-boot unattended-upgrades work
# before we try to hold the dpkg lock.
for i in 1 2 3 4 5; do
  if ! fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; then
    break
  fi
  echo "dpkg lock held, waiting..."
  sleep 5
done

apt-get update
apt-get install -y \
    docker.io \
    jq \
    unzip \
    curl \
    openssh-client

systemctl enable --now docker

# Ubuntu 24.04 no longer publishes the awscli apt package. Install the
# reviewed AWS CLI v2 distribution needed to fetch the range-local artifact.
curl -fsSL \
    https://awscli.amazonaws.com/awscli-exe-linux-x86_64-2.27.49.zip \
    -o /tmp/awscliv2.zip
printf '%s  %s\n' \
    '93842f724f8b76fbee05ac6a403dad603043b04eecfe3526f2035494718eb87b' \
    /tmp/awscliv2.zip | sha256sum -c -
unzip -q /tmp/awscliv2.zip -d /tmp/awscliv2
/tmp/awscliv2/aws/install
rm -rf /tmp/awscliv2 /tmp/awscliv2.zip

# docker-compose-plugin is not in Ubuntu 22.04 apt. Install the v2 binary
# from docker's github release directly so `docker compose` works.
mkdir -p /usr/libexec/docker/cli-plugins
curl -fsSL \
    https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 \
    -o /usr/libexec/docker/cli-plugins/docker-compose
printf '%s  %s\n' \
    '383ce6698cd5d5bbf958d2c8489ed75094e34a77d340404d9f32c4ae9e12baf0' \
    /usr/libexec/docker/cli-plugins/docker-compose | sha256sum -c -
chmod +x /usr/libexec/docker/cli-plugins/docker-compose

# The shifter-ubuntu base AMI ships with a bunch of pre-installed and
# pre-started services (ssh on 22, xrdp on 3389, apache2 on 80, smbd/nmbd
# on 139/445, vsftpd on 21, mysql on 3306). Those compete with the polaris
# containers for host ports — particularly Kali's sshd (22) and xrdp (3389)
# that we publish to the host for participant SSH/RDP.
# Disable + mask all of them before docker compose up so first boot is
# clean. Operator access to the VM is via SSM Session Manager, not host ssh.
for svc in ssh ssh.socket xrdp xrdp-sesman apache2 smbd nmbd mysql vsftpd; do
    systemctl disable --now "$svc" 2>/dev/null || true
    systemctl mask "$svc" 2>/dev/null || true
done

# Wait for IMDS to return the instance-profile credentials before we
# call any aws cli command. First-boot user_data can race ahead of the
# attachment propagation and hit "Unable to locate credentials" (seen
# on polaris range 1 during the 3-range bring-up test). `aws sts
# get-caller-identity` is the canonical probe and takes ~1s once the
# role is ready.
for attempt in $(seq 1 30); do
  if aws sts get-caller-identity >/dev/null 2>&1; then
    echo "IMDS credentials available (attempt $attempt)"
    break
  fi
  echo "waiting for IMDS instance-profile credentials... (attempt $attempt/30)"
  sleep 4
done

# Pull the polaris build tarball via the instance profile.
mkdir -p /opt/polaris
cd /opt/polaris
aws s3 cp "${tarball_s3_uri}" polaris-build.tar.gz
install -m 0600 /dev/null /etc/polaris-range.conf
printf '%s\n' \
  'BUILD_TARBALL_S3_URI=${tarball_s3_uri}' \
  > /etc/polaris-range.conf
tar xzf polaris-build.tar.gz

# The pack archive expands directly to /opt/polaris/polaris so build contexts
# outside build/ remain adjacent to the compose definition.
if [[ ! -d /opt/polaris/polaris/build ]]; then
  echo "Polaris build artifact is missing /opt/polaris/polaris/build" >&2
  exit 1
fi
cd /opt/polaris/polaris/build

# The splice credential is scenario content, but must be unique per range.
# Generate it during provisioning, stage only its private half on A14, and
# authorize only its public half on A9.
splice_key_dir=$(mktemp -d)
chmod 700 "$splice_key_dir"
ssh-keygen -t ed25519 -N "" -C "polaris-splice" \
  -f "$splice_key_dir/splice_relay" -q
splice_private_b64=$(base64 -w0 < "$splice_key_dir/splice_relay")
splice_public=$(cat "$splice_key_dir/splice_relay.pub")

# Publish the Kali container's sshd (22) and xrdp (3389) on the EC2 host
# so the participant entry surface can reach them,
# pass the operator SSH pubkey as a KALI_AUTHORIZED_KEY env var so the
# a14 entrypoint can inject it into /home/kali/.ssh/authorized_keys on
# every container start, and pass the range-specific A2 DC IP into the
# dns container so its boreas.local zone resolves dc01 to the DC inside
# this range's /28 (not range 0's). We use a placeholder + python replace
# pass so the pubkey can contain any shell-meaningful characters without
# breaking the YAML (terraform already rendered ${kali_authorized_key}
# inline at plan time).
cat > docker-compose.override.yml <<'COMPOSE_EOF'
services:
  a14-kali:
    ports:
      - "22:22"
      - "3389:3389"
    environment:
      KALI_AUTHORIZED_KEY: "__KALI_AUTHORIZED_KEY_PLACEHOLDER__"
      KALI_SPLICE_PRIVATE_KEY_B64: "__KALI_SPLICE_PRIVATE_KEY_PLACEHOLDER__"
  a9-splice:
    environment:
      A9_AUTHORIZED_KEY: "__A9_AUTHORIZED_KEY_PLACEHOLDER__"
  dns:
    environment:
      DC01_IP: "__DC01_IP_PLACEHOLDER__"
COMPOSE_EOF

export POLARIS_SPLICE_PRIVATE_B64="$splice_private_b64"
export POLARIS_SPLICE_PUBLIC="$splice_public"
python3 - <<'PY'
import os

key = """${kali_authorized_key}"""
dc01_ip = """${a2_private_ip}"""
splice_private = os.environ["POLARIS_SPLICE_PRIVATE_B64"]
splice_public = os.environ["POLARIS_SPLICE_PUBLIC"]
with open("docker-compose.override.yml") as f:
    content = f.read()
content = content.replace("__KALI_AUTHORIZED_KEY_PLACEHOLDER__", key)
content = content.replace("__KALI_SPLICE_PRIVATE_KEY_PLACEHOLDER__", splice_private)
content = content.replace("__A9_AUTHORIZED_KEY_PLACEHOLDER__", splice_public)
content = content.replace("__DC01_IP_PLACEHOLDER__", dc01_ip)
with open("docker-compose.override.yml", "w") as f:
    f.write(content)
PY
unset POLARIS_SPLICE_PRIVATE_B64 POLARIS_SPLICE_PUBLIC
shred -u "$splice_key_dir/splice_relay" "$splice_key_dir/splice_relay.pub" \
  2>/dev/null || rm -f "$splice_key_dir/splice_relay" "$splice_key_dir/splice_relay.pub"
rmdir "$splice_key_dir"

# Build + start the stack.
docker compose build
docker compose up -d

# A14 starts outside splice-link. The watcher attaches it only after the
# participant triggers A5's thermal-runaway state.
splice_network=$(docker network ls --format '{{.Name}}' \
  | grep -E '(^|_)splice-link$' | head -n1 || true)
if [[ -n "$splice_network" ]]; then
  docker network disconnect "$splice_network" a14-kali 2>/dev/null || true
fi

cat > /usr/local/bin/polaris-splice-watcher.sh <<'WATCHER_EOF'
#!/usr/bin/env bash
set -euo pipefail
A5_CONTAINER="$${A5_CONTAINER:-a5-scada}"
KALI_CONTAINER="$${KALI_CONTAINER:-a14-kali}"
SPLICE_NETWORK="$${SPLICE_NETWORK:-build_splice-link}"
SPLICE_IP="$${SPLICE_IP:-172.20.60.140}"
while true; do
  body=$(docker exec "$A5_CONTAINER" python3 -c \
    'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/api/status", timeout=5).read().decode())' \
    2>/dev/null || true)
  if [[ "$body" == *'"runaway_complete": true'* ]] \
      || [[ "$body" == *'"runaway_complete":true'* ]]; then
    if ! docker inspect "$KALI_CONTAINER" \
      --format '{{json .NetworkSettings.Networks}}' 2>/dev/null \
      | grep -q "\"$SPLICE_NETWORK\""; then
      docker network connect --ip "$SPLICE_IP" "$SPLICE_NETWORK" "$KALI_CONTAINER" \
        || true
    fi
  fi
  sleep 10
done
WATCHER_EOF
chmod 0755 /usr/local/bin/polaris-splice-watcher.sh
cat > /etc/systemd/system/polaris-splice-watcher.service <<'UNIT_EOF'
[Unit]
Description=Polaris participant splice watcher
After=docker.service
Requires=docker.service

[Service]
Type=simple
ExecStart=/usr/local/bin/polaris-splice-watcher.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT_EOF
systemctl daemon-reload
systemctl enable --now polaris-splice-watcher.service

# Wait for A14 Kali to be reachable.
for i in $(seq 1 60); do
  if docker compose ps a14-kali | grep -q "Up"; then
    echo "=== a14-kali up ==="
    break
  fi
  sleep 2
done

docker compose ps | tee /var/log/polaris-compose-ps.log

echo "=== polaris bootstrap complete $(date -u +%FT%TZ) ==="
