#!/bin/bash
# Manual build on the approved VM; do not restart active OT component QA.
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || exit 1
cd /opt/arwc-ot-compat/it/cinder-typhoon/build/arwc
mkdir -p .operator
chmod 0700 .operator
# Build one service at a time. Preserve the qualified IT Dockerfiles and state.
sudo env COMPOSE_PARALLEL_LIMIT=1 docker compose -f compose.yaml build \
  >.operator/integration-image-build.log 2>&1
echo 'Existing IT service image build finished. No services were restarted.'
