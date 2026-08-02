#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ROOT
readonly READINESS_MARKER="${CAMPAIGN_READINESS_MARKER:-/run/shifter/keplerops-v2-campaign.ready}"
readonly HARDWARE_READINESS_MARKER="${CAMPAIGN_HARDWARE_READINESS_MARKER:-/run/shifter/keplerops-v2-hardware.ready}"
operation=${1:-}
CAMPAIGN_APPLY_ID=${CAMPAIGN_APPLY_ID:-}

readonly -a SHARED_SERVICES=(
  airflow-api
  airflow-scheduler
  airflow-dag-processor
  airflow-triggerer
  airflow-worker
  cinder-forgejo
  cinder-forgejo-runner
)

compose_campaign() {
  local -a args=(
    docker compose --project-directory "${ROOT}/.."
    --env-file "${ROOT}/../component-lock.env"
    --env-file "${ROOT}/../engineering/component-lock.additions.env"
    -f "${ROOT}/../compose.foundation.yaml"
    -f "${ROOT}/../compose.enterprise.yaml"
    -f "${ROOT}/../compose.engineering.yaml"
    -f "${ROOT}/../compose.cinder.yaml"
  )
  local overlay
  while IFS= read -r overlay; do
    args+=(-f "${overlay}")
  done < <(find "${ROOT}/modules" -mindepth 2 -maxdepth 2 \
    -name compose.overlay.yaml -type f -print | sort)
  args+=(-f "${ROOT}/compose.overlay.yaml")
  "${args[@]}" "$@"
}

wait_for_integrated_airflow() {
  local status
  for _ in $(seq 1 90); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
      kep-v2-airflow-api 2>/dev/null || true)"
    [[ ${status} == healthy ]] && break
    [[ ${status} == unhealthy || ${status} == exited || ${status} == dead ]] && {
      printf 'integrated Airflow API entered %s state\n' "${status}" >&2
      return 1
    }
    sleep 2
  done
  [[ ${status} == healthy ]] || {
    printf 'integrated Airflow API did not become healthy\n' >&2
    return 1
  }

  local path
  for path in \
    /opt/airflow/dags/orion_partner_sources.py \
    /opt/airflow/dags/orion_integrity_campaign.py \
    /opt/airflow/dags/orion_extraction_research.py \
    /opt/airflow/dags/orion_release_operations.py \
    /opt/airflow/dags/orion_production_jobs.py \
    /opt/airflow/config/release_operations.py \
    /opt/airflow/config/production_jobs.py; do
    docker exec kep-v2-airflow-api test -r "${path}" || {
      printf 'integrated Airflow path is unavailable: %s\n' "${path}" >&2
      return 1
    }
  done
}

converge_shared_services() {
  local build=${1:-no-build}
  if [[ ${build} == no-build ]] && \
      ! docker image inspect keplerops/airflow:campaign-v2 >/dev/null 2>&1; then
    build=build
  fi
  local -a options=(up -d --no-deps)
  if [[ ${build} == build ]]; then
    options+=(--build)
  else
    options+=(--no-build)
  fi
  compose_campaign "${options[@]}" "${SHARED_SERVICES[@]}" >/dev/null
  wait_for_integrated_airflow
  compose_campaign exec -T airflow-scheduler airflow dags reserialize >/dev/null

  {
    cat "${ROOT}/../config/caddy/Caddyfile"
    find "${ROOT}/modules" -path '*/runtime/Caddyfile.fragment' \
      -type f -print0 | sort -z | xargs -0 -r cat
  } | docker exec -i kep-v2-caddy sh -eu -c \
    'cat >/tmp/Caddyfile.campaign-v2'
  docker exec kep-v2-caddy caddy validate \
    --config /tmp/Caddyfile.campaign-v2 --adapter caddyfile >/dev/null
  docker exec kep-v2-caddy caddy reload \
    --config /tmp/Caddyfile.campaign-v2 --adapter caddyfile >/dev/null
}

require_fresh_hardware_proof() {
  local boot_id proof_id place gates
  [[ -r ${HARDWARE_READINESS_MARKER} ]] || {
    printf 'campaign hardware readiness proof is unavailable\n' >&2
    return 1
  }
  IFS=$'\t' read -r boot_id proof_id place gates <"${HARDWARE_READINESS_MARKER}"
  [[ ${boot_id} == "$(cat /proc/sys/kernel/random/boot_id)" ]] || {
    printf 'campaign hardware readiness proof is from another boot\n' >&2
    return 1
  }
  [[ ${proof_id} == "${CAMPAIGN_APPLY_ID}" ]] || {
    printf 'campaign hardware readiness proof is stale or belongs to another apply\n' >&2
    return 1
  }
  [[ ${place} == "${KEPLEROPS_HARDWARE_GATE14_PLACE:-}" ]] || {
    printf 'campaign hardware readiness proof names an unexpected place\n' >&2
    return 1
  }
  [[ ${gates} == operator-place+participant-reservation ]] || {
    printf 'campaign hardware readiness proof is incomplete\n' >&2
    return 1
  }
}

if [[ -z ${operation} ]]; then
  CAMPAIGN_APPLY_ID=${CAMPAIGN_APPLY_ID:-$(cat /proc/sys/kernel/random/uuid)}
  export CAMPAIGN_APPLY_ID
  rm -f "${READINESS_MARKER}" "${HARDWARE_READINESS_MARKER}"
  "${ROOT}/validate.sh" --static
fi

mapfile -t modules < <(find "${ROOT}/modules" -mindepth 1 -maxdepth 1 \
  -type d -name 'm??' -print | sort)
[[ ${#modules[@]} -eq 10 ]] || {
  printf 'expected ten campaign modules, found %d\n' "${#modules[@]}" >&2
  exit 2
}

operation_found=false
for module in "${modules[@]}"; do
  [[ -x ${module}/apply.sh ]] || {
    printf 'module apply script is unavailable: %s\n' "${module}/apply.sh" >&2
    exit 2
  }
  if [[ -n ${operation} ]]; then
    jq -e --arg id "${operation}" '.[] | select(.id == $id)' \
      "${module}/operations.json" >/dev/null || continue
    "${module}/apply.sh" "${operation}"
    operation_found=true
    break
  fi
  "${module}/apply.sh"
done

[[ -z ${operation} || ${operation_found} == true ]] || {
  printf 'unknown campaign operation: %s\n' "${operation}" >&2
  exit 2
}

if [[ -z ${operation} ]]; then
  converge_shared_services build
  require_fresh_hardware_proof
else
  converge_shared_services no-build
  exit 0
fi

install -d -m 0755 "$(dirname "${READINESS_MARKER}")"
printf '%s campaign-v2\n' "$(cat /proc/sys/kernel/random/boot_id)" \
  >"${READINESS_MARKER}"
printf 'KeplerOps campaign-v2 participant state is ready\n'
