#!/usr/bin/env bash
set -euo pipefail
# Download the product's own local embedding model before the isolated service
# receives documents. The temporary process has no company files or secrets.
image=mintplexlabs/anythingllm:1.19.0@sha256:daf5a6ae9d363ed578e7d41e2d0668c7eaa604bd90b0ff27435f893b0906833e
docker run --rm --network bridge --user 1000:1000 --workdir /app/server \
  --env STORAGE_DIR=/app/server/storage --env DISABLE_TELEMETRY=true \
  --mount type=volume,source=cinder-keplerops-native-assistant-data,target=/app/server/storage \
  --entrypoint node "$image" -e \
  'const { NativeEmbedder } = require("./utils/EmbeddingEngines/native"); new NativeEmbedder().embedderClient().then(() => process.exit(0)).catch(() => { console.error("Native local embedding model setup failed"); process.exit(1); });'
