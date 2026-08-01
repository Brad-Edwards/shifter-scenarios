#!/usr/bin/env bash

set -Eeuo pipefail

readonly ROOT="${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly IDENTITY_ENV="${BUSINESS_RELEASE_ENV:-${ROOT}/state/business-release.env}"
readonly SSH=(ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

[[ ${EUID} -eq 0 ]] || {
  echo 'activate-business-model-identities.sh must run as root on the template host' >&2
  exit 2
}
for command in curl docker install jq mktemp sha256sum ssh; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 2
  }
done
[[ -r ${K3S01_SSH_KEY} ]] || {
  printf 'k3s01 SSH key is unreadable: %s\n' "${K3S01_SSH_KEY}" >&2
  exit 2
}

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT

# Verify both immutable bundles before accepting any identity from them.
"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  'sudo sh -c '\''cd "$(readlink -f /var/lib/keplerops-platform/current-release)" && sha256sum -c SHA256SUMS >/dev/null && cosign verify-blob --insecure-ignore-tlog --key cosign.pub --bundle release.sigstore.json release.intoto.json >/dev/null && cat release.json'\''' \
  >"${workdir}/release.json"
"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  'sudo sh -c '\''cd "$(readlink -f /var/lib/keplerops-platform/current-assistant-release)" && sha256sum -c SHA256SUMS >/dev/null && cosign verify-blob --insecure-ignore-tlog --key cosign.pub --bundle assistant-runtime.sigstore.json assistant-runtime.intoto.json >/dev/null && cat assistant-runtime.json'\''' \
  >"${workdir}/assistant.json"

release_id="$(jq -er '.release_id' "${workdir}/release.json")"
release_model="$(jq -er '.model.onnx_digest' "${workdir}/release.json")"
release_image="$(jq -er '.serving_image.image_digest' "${workdir}/release.json")"
assistant_id="$(jq -er '.release_id' "${workdir}/assistant.json")"
assistant_model="$(jq -er '.model_identity.digest' "${workdir}/assistant.json")"
assistant_image="$(jq -er '.serving_images.digest' "${workdir}/assistant.json")"
policy_digest="sha256:$(sha256sum "${ROOT}/business/policy/business.rego" | awk '{print $1}')"

for value in \
  "${release_id}" "${release_model}" "${release_image}" \
  "${assistant_id}" "${assistant_model}" "${assistant_image}" "${policy_digest}"; do
  [[ ${value} =~ ^sha256:[a-f0-9]{64}$ ]] || {
    printf 'invalid active model identity digest: %s\n' "${value}" >&2
    exit 3
  }
done

install -d -m 0750 "$(dirname "${IDENTITY_ENV}")"
docker exec kep-v2-caddy cat /data/caddy/pki/authorities/local/root.crt \
  >"${workdir}/caddy-root.crt"
install -m 0644 "${workdir}/caddy-root.crt" "${ROOT}/state/caddy-root.crt"
cat >"${workdir}/business-release.env" <<EOF
ORION_RELEASE_RISK_RELEASE_ID=${release_id}
ORION_RELEASE_RISK_MODEL_DIGEST=${release_model}
ORION_RELEASE_RISK_IMAGE_DIGEST=${release_image}
ORION_ASSISTANT_RELEASE_ID=${assistant_id}
ORION_ASSISTANT_MODEL_DIGEST=${assistant_model}
ORION_ASSISTANT_IMAGE_DIGEST=${assistant_image}
ORION_ACTIVE_POLICY_DIGEST=${policy_digest}
EOF
install -m 0640 "${workdir}/business-release.env" "${IDENTITY_ENV}.next"
mv -f "${IDENTITY_ENV}.next" "${IDENTITY_ENV}"

cd "${ROOT}"
docker compose \
  --env-file component-lock.env \
  -f compose.foundation.yaml \
  -f compose.enterprise.yaml \
  up -d --build --force-recreate --no-deps business-opa business-adapter

for _ in $(seq 1 60); do
  if curl -fsS http://10.61.70.25:8080/health/ready >/dev/null 2>&1; then
    printf 'business model identities activated: release-risk=%s assistant=%s policy=%s\n' \
      "${release_id}" "${assistant_id}" "${policy_digest}"
    exit 0
  fi
  sleep 2
done
echo 'business adapter did not become ready after identity activation' >&2
exit 4
