#!/bin/bash
set -euo pipefail
umask 077
[[ $(hostname) == cinder-arwc-dev ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
cache=$PWD/.operator/retained-tools
if [[ -s $cache/SHA256SUMS ]] && (cd "$cache/files" && sha256sum --check --quiet ../SHA256SUMS); then
  exit 0
fi
stage=$(mktemp -d "$PWD/.operator/retained-tools.XXXXXX")
created=()
cleanup() { for container in "${created[@]}"; do docker rm "$container" >/dev/null; done; }
trap cleanup EXIT
mkdir -m 0755 "$stage/files"
declare -A containers
while read -r image source destination; do
  if [[ -z ${containers[$image]:-} ]]; then
    containers[$image]=$(docker create --pull never --network none --entrypoint /bin/true "$image")
    created+=("${containers[$image]}")
  fi
  mkdir -p "$stage/files/$(dirname -- "$destination")"
  docker cp "${containers[$image]}:$source" "$stage/files/$destination"
  chmod 0644 "$stage/files/$destination"
done <<'TOOLS'
cinder-arwc/a-engineering:hand-build /opt/process-service/artifacts/utility/utility engineering/utility
cinder-arwc/a-engineering:hand-build /opt/process-service/artifacts/replay-crr-r19 engineering/replay-crr-r19
cinder-arwc/a-engineering:hand-build /opt/process-service/artifacts/integrity/rot128-verifier engineering/rot128-verifier
cinder-arwc/a-engineering:hand-build /opt/process-service/artifacts/ReviewHelper.dll engineering/ReviewHelper.dll
cinder-arwc/a-engineering:hand-build /opt/process-service/artifacts/sealed-viewer engineering/sealed-viewer
cinder-arwc/a-engineering:hand-build /opt/process-service/artifacts/diag-crr-mixed-19 engineering/diag-crr-mixed-19
cinder-arwc/a-diagnostics:hand-build /opt/diagnostic-services/artifacts/dvl-worker-r5 diagnostics/dvl-worker-r5
cinder-arwc/a-diagnostics:hand-build /opt/diagnostic-services/artifacts/selector24 diagnostics/selector24
cinder-arwc/a-diagnostics:hand-build /opt/diagnostic-services/artifacts/dsign-crr-r3 diagnostics/dsign-crr-r3
cinder-arwc/a-diagnostics:hand-build /opt/diagnostic-services/artifacts/estimator23 diagnostics/estimator23
cinder-arwc/a-instruments:hand-build /opt/process-service/artifacts/IMG-FIT-204-R6.bin instruments/IMG-FIT-204-R6.bin
cinder-arwc/a-archive:hand-build /opt/retained-archive/collector-crr collection/collector-crr
TOOLS
find "$stage/files" -type d -exec chmod 0755 {} +
(cd "$stage/files" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > ../SHA256SUMS)
chmod 0644 "$stage/SHA256SUMS"
[[ ! -e $cache ]]
mv "$stage" "$cache"
echo 'Captured twelve unchanged retained engineering tools; no source, answers, tests or keys included.'
