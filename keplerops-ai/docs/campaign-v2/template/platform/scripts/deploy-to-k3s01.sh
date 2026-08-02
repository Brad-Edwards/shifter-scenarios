#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../versions.env
source "$ROOT/versions.env"
K3S01_SSH_TARGET=${K3S01_SSH_TARGET:-kepler@192.168.78.30}
K3S01_SSH_KEY=${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}
STEP_CA_CONTAINER=${STEP_CA_CONTAINER:-kep-v2-step-ca}
SSH=(ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

for command in curl docker openssl ssh tar; do
  command -v "$command" >/dev/null || {
    echo "Required command is unavailable: $command" >&2
    exit 2
  }
done
[[ -r $K3S01_SSH_KEY ]] || {
  echo "k3s01 SSH key is unreadable: $K3S01_SSH_KEY" >&2
  exit 3
}

"${SSH[@]}" "$K3S01_SSH_TARGET" \
  "sudo test -s /etc/rancher/k3s/k3s.yaml && sudo k3s kubectl get node k3s01" >/dev/null

docker build --pull \
  -t "$ORION_AGENT_IMAGE" "$ROOT/images/orion-agent"
docker build --pull \
  -t "$ORION_VISION_IMAGE" "$ROOT/images/orion-vision"

for image in "$ORION_AGENT_IMAGE" "$ORION_VISION_IMAGE"; do
  docker save "$image" | \
    "${SSH[@]}" "$K3S01_SSH_TARGET" "sudo k3s ctr images import -" >/dev/null
done

"${SSH[@]}" "$K3S01_SSH_TARGET" \
  "sudo install -d -m 0755 /opt/keplerops-platform /etc/keplerops/pki"
tar -C "$ROOT" -cf - . | \
  "${SSH[@]}" "$K3S01_SSH_TARGET" \
    "sudo tar -C /opt/keplerops-platform -xf - && sudo chmod +x /opt/keplerops-platform/scripts/*.sh"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
state_root="$ROOT/../state"
install -d -m 0700 "$state_root"

ensure_edge_identity() {
  local identity_file=$1 range_id key key_id
  if [[ ! -s $identity_file ]]; then
    umask 077
    range_id="range-$(cat /proc/sys/kernel/random/uuid)"
    key="$(openssl rand -hex 32)"
    key_id="m06-$(printf %s "$key" | sha256sum | cut -c1-16)"
    printf 'CINDER_RANGE_ID=%s\nCINDER_RANGE_ASSERTION_KEY=%s\nCINDER_RANGE_ASSERTION_KEY_ID=%s\n' \
      "$range_id" "$key" "$key_id" >"$identity_file"
  fi
  range_id="$(sed -n 's/^CINDER_RANGE_ID=//p' "$identity_file")"
  key="$(sed -n 's/^CINDER_RANGE_ASSERTION_KEY=//p' "$identity_file")"
  key_id="$(sed -n 's/^CINDER_RANGE_ASSERTION_KEY_ID=//p' "$identity_file")"
  if [[ -z $key_id && $key =~ ^[0-9a-f]{64}$ ]]; then
    key_id="m06-$(printf %s "$key" | sha256sum | cut -c1-16)"
    printf 'CINDER_RANGE_ASSERTION_KEY_ID=%s\n' "$key_id" >>"$identity_file"
  fi
  [[ $range_id =~ ^range-[0-9a-f-]{36}$ && $key =~ ^[0-9a-f]{64}$ && \
     $key_id =~ ^m06-[0-9a-f]{16}$ ]] || {
    printf 'model-edge identity is malformed: %s\n' "$identity_file" >&2
    exit 4
  }
  chmod 0600 "$identity_file"
}

cinder_identity="$state_root/cinder-model-identity.env"
partner_identity="$state_root/partner-model-identity.env"
ensure_edge_identity "$cinder_identity"
ensure_edge_identity "$partner_identity"

identity_value() {
  sed -n "s/^$2=//p" "$1"
}

cinder_range_id="$(identity_value "$cinder_identity" CINDER_RANGE_ID)"
cinder_key="$(identity_value "$cinder_identity" CINDER_RANGE_ASSERTION_KEY)"
cinder_key_id="$(identity_value "$cinder_identity" CINDER_RANGE_ASSERTION_KEY_ID)"
partner_range_id="$(identity_value "$partner_identity" CINDER_RANGE_ID)"
partner_key="$(identity_value "$partner_identity" CINDER_RANGE_ASSERTION_KEY)"
partner_key_id="$(identity_value "$partner_identity" CINDER_RANGE_ASSERTION_KEY_ID)"
edge_key_registry="$(jq -cn \
  --arg c_id "$cinder_key_id" --arg c_key "$cinder_key" --arg c_range "$cinder_range_id" \
  --arg p_id "$partner_key_id" --arg p_key "$partner_key" --arg p_range "$partner_range_id" '
  {
    ($c_id): {key:$c_key, range_id:$c_range,
      subjects:["cinder-field-operator","cinder-field-operator-service"],
      credential_classes:["operator","service"]},
    ($p_id): {key:$p_key, range_id:$p_range,
      subjects:["keplerops-partner-intake","keplerops-partner-intake-service"],
      credential_classes:["operator","service"]}
  }')"

internal_key_file="$state_root/vertex-internal-api-key"
internal_range_file="$state_root/vertex-internal-range-id"
if [[ ! -s $internal_key_file ]]; then
  umask 077
  printf 'sk-%s\n' "$(openssl rand -hex 32)" >"$internal_key_file"
fi
if [[ ! -s $internal_range_file ]]; then
  umask 077
  printf 'range-%s\n' "$(cat /proc/sys/kernel/random/uuid)" >"$internal_range_file"
fi
internal_proxy_key="$(<"$internal_key_file")"
internal_range_id="$(<"$internal_range_file")"
[[ $internal_proxy_key =~ ^sk-[0-9a-f]{64}$ && $internal_range_id =~ ^range-[0-9a-f-]{36}$ ]] || {
  echo 'internal Vertex proxy identity is malformed' >&2
  exit 4
}
chmod 0600 "$internal_key_file" "$internal_range_file"
vertex_service_account=${VERTEX_SERVICE_ACCOUNT:-$(curl -fsS -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email)}
[[ $vertex_service_account == *@*.gserviceaccount.com ]] || {
  echo 'an explicit Vertex workload service account is required' >&2
  exit 4
}
vertex_project=${VERTEX_PROJECT:-$(curl -fsS -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/project/project-id)}
[[ $vertex_project =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || {
  echo 'an explicit valid Vertex project ID is required' >&2
  exit 4
}
if docker container inspect "$STEP_CA_CONTAINER" >/dev/null 2>&1; then
  docker cp "$STEP_CA_CONTAINER:/home/step/certs/root_ca.crt" "$tmp/step-root-ca.crt"
  step_path=$(docker exec "$STEP_CA_CONTAINER" sh -c 'command -v step')
  docker cp "$STEP_CA_CONTAINER:$step_path" "$tmp/step"
  tar -C "$tmp" -cf - step-root-ca.crt step | \
    "${SSH[@]}" "$K3S01_SSH_TARGET" \
      "sudo tar -C /etc/keplerops/pki -xf - && sudo chmod 0644 /etc/keplerops/pki/step-root-ca.crt && sudo chmod 0755 /etc/keplerops/pki/step"
  printf '%s' "${STEP_CA_PROVISIONER_PASSWORD:-KeplerV2-Training-StepCA}" | \
    "${SSH[@]}" "$K3S01_SSH_TARGET" \
      "sudo sh -c 'umask 077; cat > /etc/keplerops/pki/step-provisioner-password'"
elif [[ ${SKIP_SIGNING:-0} != 1 ]]; then
  echo "Foundation step-ca container $STEP_CA_CONTAINER is unavailable" >&2
  exit 4
fi

{
  [[ -n ${ORION_ASSISTANT_BASE_URL:-} ]] && printf 'ORION_ASSISTANT_BASE_URL=%q\n' "$ORION_ASSISTANT_BASE_URL"
  printf 'ORION_ASSISTANT_API_KEY=%q\n' "${ORION_ASSISTANT_API_KEY:-$internal_proxy_key}"
  [[ -n ${ORION_ASSISTANT_UPSTREAM_MODEL:-} ]] && printf 'ORION_ASSISTANT_UPSTREAM_MODEL=%q\n' "$ORION_ASSISTANT_UPSTREAM_MODEL"
  [[ -n ${ORION_AGENT_API_KEY:-} ]] && printf 'ORION_AGENT_API_KEY=%q\n' "$ORION_AGENT_API_KEY"
  printf 'VERTEX_PROJECT=%q\n' "$vertex_project"
  printf 'VERTEX_SERVICE_ACCOUNT=%q\n' "$vertex_service_account"
  printf 'VERTEX_EDGE_KEY_REGISTRY_JSON=%q\n' "$edge_key_registry"
  printf 'VERTEX_INTERNAL_RANGE_ID=%q\n' "$internal_range_id"
  [[ ${SKIP_SIGNING:-0} == 1 ]] && printf 'SKIP_SIGNING=1\n'
} >"$tmp/platform-install.env"
cat "$tmp/platform-install.env" | \
  "${SSH[@]}" "$K3S01_SSH_TARGET" \
    "sudo sh -c 'umask 077; cat > /etc/keplerops/platform-install.env'"

"${SSH[@]}" "$K3S01_SSH_TARGET" \
  "sudo bash -c 'set -a; source /etc/keplerops/platform-install.env; set +a; exec /opt/keplerops-platform/scripts/install-platform.sh'"

"${SSH[@]}" "$K3S01_SSH_TARGET" \
  "sudo /opt/keplerops-platform/scripts/readiness.sh --core"

echo "Core platform is ready for post-m07 release materialization. Argo CD: http://192.168.78.30:30080"
