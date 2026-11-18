#!/usr/bin/env bash
set -euo pipefail
# Download the product's own local embedding model before the isolated service
# receives documents. The temporary process has no company files or secrets.
image=mintplexlabs/anythingllm:1.19.0@sha256:daf5a6ae9d363ed578e7d41e2d0668c7eaa604bd90b0ff27435f893b0906833e
# A range image carries the downloaded model outside the volume, because range
# hosts have no internet route. Seed it, then load it with no network.
cache=${KEPLEROPS_EMBEDDER_CACHE:-/opt/cinder-typhoon/cache/keplerops-embedder}
network=bridge
if [[ -d $cache/models ]]; then
  docker run --rm --network none --user 0:0 --entrypoint /bin/sh \
    --mount type=volume,source=cinder-keplerops-native-assistant-data,target=/storage \
    --mount "type=bind,source=$cache/models,target=/cache,readonly" "$image" \
    -c 'mkdir -p /storage/models && cp -a /cache/. /storage/models/ && chown -R 1000:1000 /storage/models'
  network=none
fi
docker run --rm --network "$network" --user 1000:1000 --workdir /app/server \
  --env STORAGE_DIR=/app/server/storage --env DISABLE_TELEMETRY=true \
  --mount type=volume,source=cinder-keplerops-native-assistant-data,target=/app/server/storage \
  --entrypoint node "$image" -e \
  'const { NativeEmbedder } = require("./utils/EmbeddingEngines/native"); new NativeEmbedder().embedderClient().then(() => process.exit(0)).catch(() => { console.error("Native local embedding model setup failed"); process.exit(1); });'
