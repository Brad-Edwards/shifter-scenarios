#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
operator=${KEPLEROPS_OPERATOR_DIR:-./.operator}
source_dir="$operator/native-platform/model-source"
mkdir -p "$source_dir"
if [[ ! -f $source_dir/.fieldlink-model-copied ]]; then
  docker cp cinder-keplerops-assistant:/opt/fieldkest-assistant/models/Qwen2.5-3B-Instruct/. "$source_dir/"
  touch "$source_dir/.fieldlink-model-copied"
fi
# Use only after the old assistant's public window is released. Its container
# and volumes remain available; do not load both model servers together.
docker compose stop k-assistant
docker compose up -d --no-deps --wait fieldlink-ollama
if ! docker compose exec -T fieldlink-ollama ollama show fieldlink-qwen >/dev/null 2>&1; then
  docker compose exec -T fieldlink-ollama ollama create fieldlink-qwen --quantize int4 --file /run/fieldlink/Modelfile
fi
echo 'Original Qwen model imported into native Ollama.'
