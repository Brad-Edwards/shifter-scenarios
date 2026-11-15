#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
operator=${KEPLEROPS_OPERATOR_DIR:-./.operator}
source_dir="$operator/native-platform/model-source"
converted="$operator/native-platform/model-converted"
mkdir -p "$source_dir" "$converted"
if [[ ! -f $source_dir/.fieldlink-model-copied ]]; then
  original=$(docker create --network none --entrypoint /bin/true cinder-keplerops/k-assistant:hand-build)
  trap 'docker rm "$original" >/dev/null' EXIT
  docker cp "$original:/opt/fieldkest-assistant/models/Qwen2.5-3B-Instruct/." "$source_dir/"
  docker rm "$original" >/dev/null
  trap - EXIT
  touch "$source_dir/.fieldlink-model-copied"
fi
# This release imports GGUF for the retained Qwen2 architecture. Both conversion
# steps use unmodified upstream tools and the exact preserved original weights.
converter=ghcr.io/ggml-org/llama.cpp@sha256:5bee33d877070ee246edb2f3442bcea4942d01d602f1abf479183c49a0f2ba7c
source_dir=$(realpath "$source_dir")
converted=$(realpath "$converted")
if docker container inspect cinder-keplerops-assistant >/dev/null 2>&1; then
  docker stop cinder-keplerops-assistant >/dev/null
fi
if [[ ! -f $converted/fieldlink-qwen-q4_k_m.gguf ]]; then
  docker run --rm --network none --cpus 2 --memory 4g \
    --mount "type=bind,source=$source_dir,target=/input,readonly" \
    --mount "type=bind,source=$converted,target=/output" \
    --entrypoint python3 "$converter" /app/convert_hf_to_gguf.py /input \
    --outfile /output/fieldlink-qwen-f16.gguf --outtype f16
  docker run --rm --network none --cpus 2 --memory 4g \
    --mount "type=bind,source=$converted,target=/output" \
    --entrypoint /app/llama-quantize "$converter" \
    /output/fieldlink-qwen-f16.gguf /output/fieldlink-qwen-q4_k_m.gguf.part Q4_K_M 2
  mv "$converted/fieldlink-qwen-q4_k_m.gguf.part" "$converted/fieldlink-qwen-q4_k_m.gguf"
  rm -- "$converted/fieldlink-qwen-f16.gguf"
fi
docker compose up -d --no-deps --wait fieldlink-ollama
if ! docker compose exec -T fieldlink-ollama ollama show fieldlink-qwen >/dev/null 2>&1; then
  docker compose exec -T fieldlink-ollama ollama create fieldlink-qwen --file /run/fieldlink/Modelfile
fi
echo 'Original Qwen model imported into native Ollama.'
