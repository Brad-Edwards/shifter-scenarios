#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT
readonly VERSION=1.0.0
readonly TAG="v${VERSION}"
readonly BUILD_DIR="${ROOT}/build"
readonly DIST_DIR="${ROOT}/dist"
readonly VERIFY_DIR="${ROOT}/verify-release"
readonly FORGEJO_URL="${FORGEJO_URL:-http://10.61.40.20:3000}"
readonly API_URL="${FORGEJO_URL}/api/v1"
readonly REPOSITORY=keplerops/orion-public
readonly SIGNER_HOST="${ORION_MANIFEST_SIGNER_HOST:-192.168.78.30}"
readonly SIGNER_USER="${ORION_MANIFEST_SIGNER_USER:-kepler}"
readonly ANDROID_KEY=/run/secrets/orion-android-release-key.pk8
readonly ANDROID_CERT=/run/secrets/orion-android-release-cert.pem
readonly SSH_KEY=/run/secrets/orion-manifest-signer
readonly KNOWN_HOSTS=/run/secrets/orion-manifest-signer-known-hosts
readonly MODEL_EVIDENCE="${BUILD_DIR}/orion-release-risk-evidence.json"

for variable in FORGEJO_CI_USER FORGEJO_CI_PASSWORD ORION_SOURCE_REVISION \
  ORION_WORKFLOW_REVISION; do
  [[ -n ${!variable:-} ]] || { printf 'missing release variable: %s\n' "${variable}" >&2; exit 2; }
done
for command in base64 cmp curl find jq openssl python3 sha256sum ssh stat; do
  command -v "${command}" >/dev/null || {
    printf 'missing release command: %s\n' "${command}" >&2
    exit 2
  }
done
for path in "${ANDROID_KEY}" "${ANDROID_CERT}" "${SSH_KEY}" "${KNOWN_HOSTS}"; do
  [[ -s ${path} ]] || { printf 'missing release credential: %s\n' "${path}" >&2; exit 2; }
done

api() {
  local method=$1
  local path=$2
  shift 2
  curl --silent --show-error --fail-with-body \
    --user "${FORGEJO_CI_USER}:${FORGEJO_CI_PASSWORD}" \
    --request "${method}" "$@" "${API_URL}${path}"
}

internal_forgejo_url() {
  local url=$1
  case "${url}" in
    http://*/*|https://*/*) printf '%s/%s\n' "${FORGEJO_URL}" "${url#*://*/}" ;;
    /*) printf '%s%s\n' "${FORGEJO_URL}" "${url}" ;;
    *) printf '%s/%s\n' "${FORGEJO_URL}" "${url}" ;;
  esac
}

ssh_signer() {
  ssh -i "${SSH_KEY}" -o BatchMode=yes \
    -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="${KNOWN_HOSTS}" \
    "${SIGNER_USER}@${SIGNER_HOST}" "$@"
}

rm -rf "${VERIFY_DIR}"
install -d "${VERIFY_DIR}"
export ORION_ANDROID_SIGNING_KEY="${ANDROID_KEY}"
export ORION_ANDROID_SIGNING_CERT="${ANDROID_CERT}"
python3 "${ROOT}/ci/prepare-client.py" \
  --root "${ROOT}" \
  --source-revision "${ORION_SOURCE_REVISION}" \
  --source-tag "${TAG}"
bash "${ROOT}/client/build.sh" "${BUILD_DIR}" "${DIST_DIR}" >/dev/null
ssh_signer model-evidence >"${MODEL_EVIDENCE}"
python3 "${ROOT}/ci/assemble-release.py" \
  --root "${ROOT}" \
  --build-dir "${BUILD_DIR}" \
  --dist-dir "${DIST_DIR}" \
  --source-revision "${ORION_SOURCE_REVISION}" \
  --workflow-revision "${ORION_WORKFLOW_REVISION}" \
  --android-cert "${ANDROID_CERT}" \
  --model-evidence "${MODEL_EVIDENCE}"

ssh_signer public-key >"${DIST_DIR}/cosign.pub"
ssh_signer sign-manifest \
  <"${DIST_DIR}/release-manifest.json" \
  >"${DIST_DIR}/release-manifest.sig"
base64 -d <"${DIST_DIR}/release-manifest.sig" >"${VERIFY_DIR}/manifest-signature.bin"
openssl dgst -sha256 -verify "${DIST_DIR}/cosign.pub" \
  -signature "${VERIFY_DIR}/manifest-signature.bin" \
  "${DIST_DIR}/release-manifest.json" >/dev/null

release_json="$(api GET "/repos/${REPOSITORY}/releases/tags/${TAG}" 2>/dev/null || true)"
if jq -e 'type == "object" and has("id")' <<<"${release_json}" >/dev/null 2>&1; then
  release_id="$(jq -er '.id' <<<"${release_json}")"
  manifest_url="$(jq -er '.assets[] | select(.name == "release-manifest.json") | .browser_download_url' \
    <<<"${release_json}")"
  manifest_url="$(internal_forgejo_url "${manifest_url}")"
  curl -fsS --user "${FORGEJO_CI_USER}:${FORGEJO_CI_PASSWORD}" \
    "${manifest_url}" -o "${VERIFY_DIR}/existing-release-manifest.json"
  cmp "${DIST_DIR}/release-manifest.json" "${VERIFY_DIR}/existing-release-manifest.json" || {
    printf 'release %s already exists for different bytes; increment the release version\n' "${TAG}" >&2
    exit 5
  }
else
  release_json="$(api POST "/repos/${REPOSITORY}/releases" \
    --header 'Content-Type: application/json' \
    --data "$(jq -cn \
      --arg tag "${TAG}" \
      --arg target "${ORION_SOURCE_REVISION}" \
      --arg name "Orion Release Risk Mobile ${VERSION}" \
      --rawfile body "${DIST_DIR}/RELEASE_NOTES.md" \
      '{tag_name:$tag,target_commitish:$target,name:$name,body:$body,draft:false,prerelease:false}')")"
  release_id="$(jq -er '.id' <<<"${release_json}")"
  while IFS= read -r path; do
    api POST "/repos/${REPOSITORY}/releases/${release_id}/assets?name=$(jq -rn --arg value "$(basename "${path}")" '$value|@uri')" \
      --header 'Content-Type: application/octet-stream' \
      --data-binary "@${path}" >/dev/null
  done < <(find "${DIST_DIR}" -mindepth 1 -maxdepth 1 -type f | sort)
  release_json="$(api GET "/repos/${REPOSITORY}/releases/${release_id}")"
fi

expected_assets="$(find "${DIST_DIR}" -mindepth 1 -maxdepth 1 -type f \
  -printf '%f\n' | sort)"
actual_assets="$(jq -r '.assets[].name' <<<"${release_json}" | sort)"
[[ ${actual_assets} == "${expected_assets}" ]] || {
  printf 'published release asset set is incomplete\n' >&2
  exit 6
}

while IFS=$'\t' read -r name url; do
  url="$(internal_forgejo_url "${url}")"
  curl -fsS --user "${FORGEJO_CI_USER}:${FORGEJO_CI_PASSWORD}" \
    "${url}" -o "${VERIFY_DIR}/${name}"
  cmp "${DIST_DIR}/${name}" "${VERIFY_DIR}/${name}"
done < <(jq -r '.assets[] | [.name,.browser_download_url] | @tsv' <<<"${release_json}")

while IFS=$'\t' read -r name expected size; do
  actual="$(sha256sum "${VERIFY_DIR}/${name}" | awk '{print $1}')"
  [[ ${actual} == "${expected}" ]] || { printf 'artifact digest mismatch: %s\n' "${name}" >&2; exit 7; }
  [[ $(stat -c %s "${VERIFY_DIR}/${name}") == "${size}" ]] || {
    printf 'artifact size mismatch: %s\n' "${name}" >&2
    exit 7
  }
done < <(jq -r '.artifacts[] | [.name,.sha256,.size] | @tsv' \
  "${VERIFY_DIR}/release-manifest.json")

base64 -d <"${VERIFY_DIR}/release-manifest.sig" >"${VERIFY_DIR}/release-signature.bin"
openssl dgst -sha256 -verify "${VERIFY_DIR}/cosign.pub" \
  -signature "${VERIFY_DIR}/release-signature.bin" \
  "${VERIFY_DIR}/release-manifest.json" >/dev/null
cert_digest="$(openssl x509 -in "${VERIFY_DIR}/orion-mobile-signing-cert.pem" \
  -outform DER | sha256sum | awk '{print $1}')"
[[ ${cert_digest} == "$(jq -er '.android_signing.certificate_sha256' \
  "${VERIFY_DIR}/release-manifest.json")" ]]
apk_verify="$("${ANDROID_HOME}/build-tools/35.0.0/apksigner" verify \
  --verbose --print-certs "${VERIFY_DIR}/orion-mobile-${VERSION}.apk")"
grep -q '^Verified using v2 scheme (APK Signature Scheme v2): true$' <<<"${apk_verify}"
grep -q '^Verified using v3 scheme (APK Signature Scheme v3): true$' <<<"${apk_verify}"
grep -qi "certificate SHA-256 digest: ${cert_digest}" <<<"${apk_verify}"
jq -e \
  --arg revision "${ORION_SOURCE_REVISION}" '
    .bomFormat == "CycloneDX"
    and .specVersion == "1.6"
    and any(.metadata.component.properties[];
      .name == "keplerops:source-revision" and .value == $revision)
    and (.components | length > 5)
    and all(.components[];
      .type == "file" and (.hashes | length == 1)
      and .hashes[0].alg == "SHA-256"
      and (.hashes[0].content | test("^[0-9a-f]{64}$")))
  ' "${VERIFY_DIR}/orion-mobile-${VERSION}.cdx.json" >/dev/null

printf 'Orion Release Risk Mobile %s published from %s and independently cross-checked\n' \
  "${VERSION}" "${ORION_SOURCE_REVISION}"
