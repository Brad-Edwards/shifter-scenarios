#!/bin/bash
# Stage, verify, build and start the Polaris Compose stack for the polaris-vm
# image bake. Runs after host-setup.sh has installed Docker.
#
# Fail-closed: a checksum mismatch, a missing compose file, an invalid compose
# config, a failed build/pull, a missing image, or failure to create and start
# every declared service fails the build, so a non-promotable polaris-vm image
# is never captured.
#
# Inputs:
#   /tmp/build-v1.tar.gz                 reviewed stack archive (Packer upload)
#   /tmp/polaris-splice-credential.py    reviewed splice helper (Packer upload)
#   POLARIS_STACK_SHA256                 required archive digest
#   POLARIS_STACK_START_TIMEOUT_SECONDS  bounded service-start wait (default 300)
set -euo pipefail

HOST_MGMT_SSH_PORT="${HOST_MGMT_SSH_PORT:-2222}"
POLARIS_STACK_TARBALL="/tmp/build-v1.tar.gz"
POLARIS_STACK_SHA256="${POLARIS_STACK_SHA256:-}"
POLARIS_STACK_START_TIMEOUT_SECONDS="${POLARIS_STACK_START_TIMEOUT_SECONDS:-300}"
# The archive keeps its polaris/ prefix, so the stack lands at
# /opt/polaris/scenario-dev/polaris/build: the directory the runtime adapter's
# range bootstrap runs Compose from. polaris/flags and contract_source.py land in
# the parent, where a0-website's `context: ..` expects them.
POLARIS_PARENT="/opt/polaris/scenario-dev"
COMPOSE_DIR="${POLARIS_PARENT}/polaris/build"
POLARIS_LIBEXEC_DIR="/opt/polaris/libexec"
POLARIS_SPLICE_HELPER_SOURCE="/tmp/polaris-splice-credential.py"
POLARIS_SPLICE_HELPER="${POLARIS_LIBEXEC_DIR}/polaris-splice-credential.py"
# Shifter delivers Claude Code here at range realization; Compose bind-mounts it.
SHIFTER_DELIVERY_DIR="/opt/shifter/bin"

fail_stack() {
  echo "polaris stage-stack: ERROR $*" >&2
  exit 1
}

[[ "${POLARIS_STACK_START_TIMEOUT_SECONDS}" =~ ^[0-9]+$ ]] \
  || fail_stack "POLARIS_STACK_START_TIMEOUT_SECONDS must be a non-negative integer."
[[ "${POLARIS_STACK_SHA256}" =~ ^[0-9a-f]{64}$ ]] || fail_stack "POLARIS_STACK_SHA256 is required."

install -d -m 0755 "${POLARIS_LIBEXEC_DIR}" "${SHIFTER_DELIVERY_DIR}"
install -m 0755 "${POLARIS_SPLICE_HELPER_SOURCE}" "${POLARIS_SPLICE_HELPER}"
rm -f "${POLARIS_SPLICE_HELPER_SOURCE}"

# Verify the archive digest before it is unpacked or built.
echo "${POLARIS_STACK_SHA256}  ${POLARIS_STACK_TARBALL}" | sha256sum -c - \
  || fail_stack "compose-stack archive sha256 mismatch."
[[ ! -e "${POLARIS_PARENT}" ]] || fail_stack "${POLARIS_PARENT} already exists on the builder."
install -d -m 0755 "${POLARIS_PARENT}"
tar xzf "${POLARIS_STACK_TARBALL}" -C "${POLARIS_PARENT}"
rm -f "${POLARIS_STACK_TARBALL}"
[[ -f "${COMPOSE_DIR}/docker-compose.yml" ]] || fail_stack "no docker-compose.yml at ${COMPOSE_DIR}."

echo "polaris stage-stack: validating and building compose stack in ${COMPOSE_DIR}"
cd "${COMPOSE_DIR}"

# Supply throwaway bake-only values and the reviewed entrypoint wrapper as a
# separate Compose layer. Range bootstrap later replaces these with per-range
# values in docker-compose.override.yml.
#
# The dns service's entrypoint hard-requires DC01_IP (it substitutes the
# __DC01_IP__ placeholder in the boreas.local zone file) and exits non-zero
# without it; that value is only known per range. A throwaway placeholder lets
# the full stack reach running for capture; range bootstrap recreates dns with
# the real per-range DC01_IP.
DC01_IP_BAKE_PLACEHOLDER="172.20.10.11"
SPLICE_KEY_DIR="$(mktemp -d)"
chmod 0700 "${SPLICE_KEY_DIR}"
ssh-keygen -q -t ed25519 -N "" -f "${SPLICE_KEY_DIR}/splice_relay"
SPLICE_PRIVATE_KEY_B64="$(base64 -w0 < "${SPLICE_KEY_DIR}/splice_relay")"
SPLICE_PUBLIC_KEY="$(cat "${SPLICE_KEY_DIR}/splice_relay.pub")"
shred -u "${SPLICE_KEY_DIR}/splice_relay" "${SPLICE_KEY_DIR}/splice_relay.pub" 2>/dev/null \
  || rm -f "${SPLICE_KEY_DIR}/splice_relay" "${SPLICE_KEY_DIR}/splice_relay.pub"
rmdir "${SPLICE_KEY_DIR}"
cat > docker-compose.splice-credential.yml <<COMPOSE_EOF
services:
  dns:
    environment:
      DC01_IP: "${DC01_IP_BAKE_PLACEHOLDER}"
  a9-splice:
    environment:
      A9_AUTHORIZED_KEY: "${SPLICE_PUBLIC_KEY}"
  a14-kali:
    environment:
      KALI_SPLICE_PRIVATE_KEY_B64: "${SPLICE_PRIVATE_KEY_B64}"
    volumes:
      - ${POLARIS_SPLICE_HELPER}:/usr/local/libexec/polaris-splice-credential.py:ro
    entrypoint:
      - /usr/local/libexec/polaris-splice-credential.py
      - entrypoint
COMPOSE_EOF
export COMPOSE_FILE="docker-compose.yml:gcp-preconfigured-host.override.yml:docker-compose.splice-credential.yml"
# An invalid compose file, a failed build, or a failed pull is not a promotable
# image. --ignore-buildable skips images this stack builds locally, so a pull
# failure is a real registry error.
docker compose config >/dev/null
compose_json="$(docker compose config --format json)"
if ! jq -e '
  (.services | type == "object") and
  ([.services | to_entries[] | select(
    (.value.privileged // false) or
    ((.value.network_mode // "") == "host") or
    ((.value.pid // "") == "host") or
    ((.value.ipc // "") == "host") or
    ([.value.cap_add[]?] | any(. == "ALL" or . == "NET_ADMIN" or . == "SYS_ADMIN")) or
    ([.value.volumes[]? | select(type == "object" and .type == "bind") | .source] |
      any(. == "/" or . == "/run" or . == "/var/run" or startswith("/etc/") or
          startswith("/proc/") or startswith("/sys/") or startswith("/root/") or
          startswith("/home/packer/") or startswith("/var/lib/docker/")))
  )] | length == 0)
' <<<"${compose_json}" >/dev/null; then
  fail_stack "compose stack requests a privileged/host namespace, dangerous capability, or sensitive host bind."
fi
if ! jq -e '
  all(.services | to_entries[];
    (.value.build != null) or
    ((.value.image // "") | test("@sha256:[0-9a-f]{64}$")))
' <<<"${compose_json}" >/dev/null; then
  fail_stack "every pulled compose image must use an immutable sha256 digest."
fi
docker compose build
docker compose pull --ignore-buildable

# Every image the stack references must be present after build and pull.
missing_images=""
while IFS= read -r img; do
  [[ -z "${img}" ]] && continue
  if ! docker image inspect "${img}" >/dev/null 2>&1; then
    missing_images="${missing_images} ${img}"
  fi
done < <(docker compose config --images)
[[ -z "${missing_images}" ]] || fail_stack "compose images missing after build/pull:${missing_images}"

# Block host and container traffic to the GCE metadata server before any stack
# workload runs. The builder has no service account, but metadata still exposes
# instance attributes. Privileged and host-namespace services were rejected
# above, so a stack image cannot remove or bypass these rules.
METADATA_IP="169.254.169.254/32"
iptables -I OUTPUT 1 -d "${METADATA_IP}" -j DROP
iptables -I DOCKER-USER 1 -d "${METADATA_IP}" -j DROP
iptables -C OUTPUT -d "${METADATA_IP}" -j DROP >/dev/null 2>&1 \
  || fail_stack "host metadata isolation rule was not installed."
iptables -C DOCKER-USER -d "${METADATA_IP}" -j DROP >/dev/null 2>&1 \
  || fail_stack "container metadata isolation rule was not installed."

# Create and start every declared container before capture. `restart:
# unless-stopped` can only restore containers that already exist.
echo "polaris stage-stack: creating full compose stack before image capture"
docker compose up -d
mapfile -t services < <(docker compose config --services)
[[ "${#services[@]}" -gt 0 ]] || fail_stack "compose declares no services."
deadline=$(( SECONDS + POLARIS_STACK_START_TIMEOUT_SECONDS ))
while :; do
  notready=""
  for svc in "${services[@]}"; do
    state="$(docker compose ps -a --format '{{.Service}} {{.State}}' \
      | awk -v s="${svc}" '$1==s {print $2; f=1} END{if(!f) print "absent"}')"
    [[ "${state}" == "running" ]] || notready="${notready} ${svc}(${state})"
  done
  [[ -z "${notready}" ]] && break
  if (( SECONDS >= deadline )); then
    for entry in ${notready}; do
      svc="${entry%%(*}"
      echo "polaris stage-stack: --- last logs for not-running service '${svc}' ---" >&2
      docker compose logs --tail=50 --no-color "${svc}" >&2 2>&1 || true
    done
    fail_stack "compose services not running before image capture:${notready}"
  fi
  echo "polaris stage-stack: waiting for services to reach running:${notready}"
  sleep 15
done

"${POLARIS_SPLICE_HELPER}" host-check --container a14-kali
for recreation in 1 2; do
  docker compose up -d --force-recreate a14-kali
  "${POLARIS_SPLICE_HELPER}" host-check --container a14-kali
  echo "polaris stage-stack: a14-kali splice credential recreation ${recreation}/2 verified"
done

# The participant image links the delivered client; no client is baked.
docker exec a14-kali test -L /usr/local/bin/claude || fail_stack "a14-kali lacks the delivered-client link."
if docker exec a14-kali test -e /opt/shifter/bin/claude; then
  fail_stack "a Claude Code binary is present at bake time."
fi

echo "polaris stage-stack: complete (mgmt sshd port ${HOST_MGMT_SSH_PORT}, ${#services[@]} services created and running)"
