#!/usr/bin/env bash

set -Eeuo pipefail

readonly DEVPI_URL=http://10.61.40.30:3141/publisher/stable/
readonly VERDACCIO_URL=http://10.61.40.31:4873
readonly REGISTRY=registry.keplerops.lab
readonly REGISTRY_CERT_DIR=/data/registry-certs
readonly IMAGE_REPOSITORY="${REGISTRY}/orion-build/orion-release-metadata"

for variable in DEVPI_USER DEVPI_PASSWORD VERDACCIO_USER VERDACCIO_PASSWORD \
  HARBOR_USER HARBOR_PASSWORD GITHUB_SHA; do
  [[ -n ${!variable:-} ]] || {
    printf 'missing CI variable: %s\n' "${variable}" >&2
    exit 1
  }
done

python3 -m build --wheel
if ! curl -fsS \
    'http://10.61.40.30:3141/publisher/stable/+simple/keplerops-orion-release/' | \
    grep -q 'keplerops_orion_release-0.1.0-py3-none-any.whl'; then
  python3 -m twine upload \
    --repository-url "${DEVPI_URL}" \
    --username "${DEVPI_USER}" \
    --password "${DEVPI_PASSWORD}" \
    dist/*.whl
fi

npm test
npm_auth="$(printf '%s:%s' "${VERDACCIO_USER}" "${VERDACCIO_PASSWORD}" | base64 -w0)"
printf '//10.61.40.31:4873/:_auth=%s\nalways-auth=true\n' "${npm_auth}" >.npmrc
if ! npm view '@keplerops/orion-build-metadata@0.1.0' \
    --registry "${VERDACCIO_URL}" version >/dev/null 2>&1; then
  npm publish --registry "${VERDACCIO_URL}"
fi

short_revision="${GITHUB_SHA:0:12}"
image_archive="$(mktemp --suffix=.tar)"
docker_config="$(mktemp -d)"
trap 'rm -rf "${docker_config}"; rm -f "${image_archive}"' EXIT
export DOCKER_CONFIG="${docker_config}"
docker build \
  --provenance=false \
  --build-arg "ORION_BUILD_REVISION=${GITHUB_SHA}" \
  --tag "${IMAGE_REPOSITORY}:${short_revision}" \
  --tag "${IMAGE_REPOSITORY}:clean-latest" \
  service
docker save --output "${image_archive}" "${IMAGE_REPOSITORY}:${short_revision}"
printf '%s' "${HARBOR_PASSWORD}" | \
  SSL_CERT_FILE="${REGISTRY_CERT_DIR}/ca.crt" \
  crane auth login "${REGISTRY}" \
    --username "${HARBOR_USER}" \
    --password-stdin
SSL_CERT_FILE="${REGISTRY_CERT_DIR}/ca.crt" \
  crane push "${image_archive}" "${IMAGE_REPOSITORY}:${short_revision}"
SSL_CERT_FILE="${REGISTRY_CERT_DIR}/ca.crt" \
  crane tag "${IMAGE_REPOSITORY}:${short_revision}" clean-latest

digest="$(SSL_CERT_FILE="${REGISTRY_CERT_DIR}/ca.crt" \
  crane digest "${IMAGE_REPOSITORY}:${short_revision}")"
printf 'ORION_CI_RESULT revision=%s python=keplerops-orion-release==0.1.0 node=@keplerops/orion-build-metadata@0.1.0 image=%s\n' \
  "${GITHUB_SHA}" "${IMAGE_REPOSITORY}@${digest}"
