#!/usr/bin/env bash

set -Eeuo pipefail

readonly ROOT="${KEPLEROPS_V2_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
readonly PYTHON="${VISION_PYTHON:-python3}"
readonly SOURCE="${ROOT}/platform/vision"
readonly IMAGE_SOURCE="${ROOT}/platform/images/orion-vision"
readonly COMMITTED_ARTIFACTS="${IMAGE_SOURCE}/artifacts"

for command in cmp sha256sum; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 2
  }
done
"${PYTHON}" -c 'import fastapi, httpx, numpy, onnx, onnxruntime, PIL, torch' || {
  printf 'vision baseline requires the pinned training and runtime dependencies\n' >&2
  exit 2
}

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT

"${PYTHON}" "${SOURCE}/generate_dataset.py" \
  --output "${workdir}/data" --replace >/dev/null
cmp "${SOURCE}/data/dataset-manifest.json" \
  "${workdir}/data/dataset-manifest.json"

while IFS= read -r relative; do
  cmp "${SOURCE}/data/${relative}" "${workdir}/data/${relative}"
done < <(
  "${PYTHON}" - "${SOURCE}/data/dataset-manifest.json" <<'PY'
import json
import sys
for item in json.load(open(sys.argv[1]))["images"]:
    print(item["path"])
PY
)

"${PYTHON}" "${SOURCE}/train_export.py" \
  --data-dir "${workdir}/data" --output-dir "${workdir}/artifacts" >/dev/null

for artifact in \
  heldout-evaluation-report.json \
  class-map.json \
  model-metadata.json \
  orion-vision-prototype.onnx \
  preprocessing.json \
  reference-inference.json; do
  cmp "${COMMITTED_ARTIFACTS}/${artifact}" "${workdir}/artifacts/${artifact}"
done

"${PYTHON}" "${SOURCE}/verify.py" \
  --app "${IMAGE_SOURCE}/app.py" \
  --artifacts "${COMMITTED_ARTIFACTS}" \
  --data "${SOURCE}/data"

printf 'Orion Vision clean baseline passed: model=%s data=%s\n' \
  "$(sha256sum "${COMMITTED_ARTIFACTS}/orion-vision-prototype.onnx" | cut -d' ' -f1)" \
  "$(sha256sum "${SOURCE}/data/dataset-manifest.json" | cut -d' ' -f1)"
