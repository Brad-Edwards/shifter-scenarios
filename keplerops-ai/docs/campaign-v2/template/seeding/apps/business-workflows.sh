#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

main() {
  require_service business-adapter
  require_service business-opa

  local container state
  for container in kep-v2-minio kep-v2-lakefs kep-v2-qdrant; do
    state="$(docker inspect --format '{{.State.Status}}' "${container}" 2>/dev/null || true)"
    [[ ${state} == running ]] || die "required engineering container is not running: ${container}"
  done

  compose exec -T business-adapter python -m app.seed
  log "bounded business workflow state is ready"
}

main "$@"
