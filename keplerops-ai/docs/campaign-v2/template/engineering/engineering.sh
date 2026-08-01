#!/usr/bin/env bash
set -euo pipefail

ENGINEERING_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly ENGINEERING_DIR
TEMPLATE_DIR="$(cd -- "${ENGINEERING_DIR}/.." && pwd)"
readonly TEMPLATE_DIR
readonly LOCK_ADDITIONS="${ENGINEERING_DIR}/component-lock.additions.env"
readonly LOCK_PARENT="${TEMPLATE_DIR}/component-lock.env"
readonly COMPOSE_ENGINEERING="${TEMPLATE_DIR}/compose.engineering.yaml"
readonly COMPOSE_FOUNDATION="${TEMPLATE_DIR}/compose.foundation.yaml"
readonly HEALTH_ATTEMPTS="${ENGINEERING_HEALTH_ATTEMPTS:-90}"
readonly HEALTH_DELAY="${ENGINEERING_HEALTH_DELAY:-5}"

readonly -a FOUNDATION=(
  docker compose
  --env-file "${LOCK_PARENT}"
  -f "${COMPOSE_FOUNDATION}"
)
readonly -a COMPOSE=(
  docker compose
  --env-file "${LOCK_ADDITIONS}"
  --env-file "${LOCK_PARENT}"
  -f "${COMPOSE_FOUNDATION}"
  -f "${COMPOSE_ENGINEERING}"
)

log() {
  printf '[engineering] %s\n' "$*"
}

die() {
  printf '[engineering] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

wait_service() {
  local service=$1
  local container_id status health attempt

  for ((attempt = 1; attempt <= HEALTH_ATTEMPTS; attempt++)); do
    container_id=$("${COMPOSE[@]}" ps -q "${service}" 2>/dev/null || true)
    if [[ -n "${container_id}" ]]; then
      status=$(docker inspect --format '{{.State.Status}}' "${container_id}" 2>/dev/null || true)
      health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
        "${container_id}" 2>/dev/null || true)
      if [[ "${status}" == running && ("${health}" == healthy || "${health}" == none) ]]; then
        printf '[engineering] %-24s ready\n' "${service}"
        return 0
      fi
    fi
    sleep "${HEALTH_DELAY}"
  done

  "${COMPOSE[@]}" ps "${service}" >&2 || true
  die "service did not become ready: ${service}"
}

wait_url() {
  local name=$1
  local url=$2
  local attempt

  for ((attempt = 1; attempt <= HEALTH_ATTEMPTS; attempt++)); do
    if curl --fail --silent --show-error --location \
      --connect-timeout 3 --max-time 10 "${url}" >/dev/null 2>&1; then
      printf '[engineering] %-24s %s\n' "${name}" "${url}"
      return 0
    fi
    sleep "${HEALTH_DELAY}"
  done

  die "endpoint did not become ready: ${name} (${url})"
}

reconcile_postgres() {
  log 'reconciling application roles and databases'
  docker exec -i kep-v2-postgres \
    psql --set ON_ERROR_STOP=1 --username kepler --dbname postgres \
    <"${ENGINEERING_DIR}/postgres/reconcile.sql" >/dev/null
}

reconcile_products() {
  log 'reconciling package indexes, registry trust, object stores, and orchestration metadata'
  wait_service devpi
  wait_url 'Harbor API' 'http://10.61.40.32:8080/api/v2.0/health'
  wait_url 'Label Studio API' 'http://10.61.40.34:8080/health'
  wait_url 'MinIO API' 'http://10.61.50.60:9000/minio/health/live'
  wait_url 'lakeFS API' 'http://10.61.50.61:8000/api/v1/healthcheck'

  "${COMPOSE[@]}" run --rm --no-deps devpi-bootstrap
  "${COMPOSE[@]}" run --rm --no-deps minio-init
  "${COMPOSE[@]}" run --rm --no-deps lakefs-init
  "${COMPOSE[@]}" run --rm --no-deps airflow-init
  "${COMPOSE[@]}" run --rm --no-deps dvc dvc version >/dev/null
  "${ENGINEERING_DIR}/reconcile-label-studio.sh"
  "${ENGINEERING_DIR}/reconcile-ci.sh"
}

health() {
  local service
  local role_count database_count
  local -a services=(
    devpi verdaccio forgejo-runner
    harbor-db harbor-redis harbor-registry harbor-registryctl harbor-core
    harbor-jobservice harbor-portal harbor-nginx
    jupyterhub label-studio minio lakefs
    airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker
    mlflow tika grobid qdrant hayhooks
  )

  log 'checking containers'
  for service in "${services[@]}"; do
    wait_service "${service}"
  done

  log 'checking product APIs'
  wait_url 'devpi' 'http://10.61.40.30:3141/+status'
  wait_url 'Verdaccio' 'http://10.61.40.31:4873/-/ping'
  wait_url 'Harbor' 'http://10.61.40.32:8080/api/v2.0/health'
  wait_url 'JupyterHub' 'http://10.61.40.33:8000/hub/health'
  wait_url 'Label Studio' 'http://10.61.40.34:8080/health'
  wait_url 'MinIO API' 'http://10.61.50.60:9000/minio/health/live'
  wait_url 'MinIO console' 'http://10.61.50.60:9001/'
  wait_url 'lakeFS' 'http://10.61.50.61:8000/api/v1/healthcheck'
  wait_url 'Airflow' 'http://10.61.40.35:8080/api/v2/monitor/health'
  wait_url 'MLflow' 'http://10.61.40.36:5000/health'
  wait_url 'Tika' 'http://10.61.50.63:9998/tika'
  wait_url 'GROBID' 'http://10.61.50.64:8070/api/isalive'
  wait_url 'Qdrant' 'http://10.61.50.62:6333/readyz'
  wait_url 'Hayhooks' 'http://10.61.40.37:1416/docs'

  role_count=$(docker exec kep-v2-postgres psql --username kepler --dbname postgres --tuples-only --no-align \
    --command "SELECT count(*) FROM pg_roles WHERE rolname IN ('jupyterhub','labelstudio','lakefs','mlflow','airflow');")
  database_count=$(docker exec kep-v2-postgres psql --username kepler --dbname postgres --tuples-only --no-align \
    --command "SELECT count(*) FROM pg_database WHERE datname IN ('jupyterhub','labelstudio','lakefs','mlflow','airflow');")
  [[ "${role_count}" == 5 ]] || die "expected five engineering database roles; found ${role_count}"
  [[ "${database_count}" == 5 ]] || die "expected five engineering databases; found ${database_count}"

  docker exec kep-v2-redis redis-cli -a KeplerV2-Training-Redis ping 2>/dev/null | grep -qx PONG \
    || die 'shared Redis did not answer PING'
  docker exec kep-v2-rabbitmq rabbitmq-diagnostics -q ping >/dev/null \
    || die 'shared RabbitMQ did not answer diagnostics ping'

  log 'engineering/data plane is healthy'
}

start() {
  local -a pull_services=(
    verdaccio harbor-init harbor-db harbor-redis harbor-registry harbor-registryctl
    harbor-core harbor-jobservice harbor-portal harbor-nginx label-studio minio
    minio-init lakefs lakefs-init tika grobid qdrant
  )
  local -a build_services=(devpi forgejo-runner jupyterhub airflow-api mlflow hayhooks dvc)
  local -a runtime_services=(
    devpi-bootstrap verdaccio harbor-nginx jupyterhub label-studio lakefs
    airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker
    mlflow tika grobid qdrant hayhooks
  )

  log 'starting required foundation services and networks'
  "${FOUNDATION[@]}" up -d postgres redis rabbitmq keycloak caddy
  wait_service postgres
  wait_service redis
  wait_service rabbitmq
  reconcile_postgres

  log 'pulling pinned vendor images'
  "${COMPOSE[@]}" pull "${pull_services[@]}"

  log 'building pinned derivative images'
  "${COMPOSE[@]}" build "${build_services[@]}"

  # DockerSpawner creates notebook containers directly through the Docker API.
  set -a
  # shellcheck disable=SC1090
  source "${LOCK_ADDITIONS}"
  # shellcheck disable=SC1090
  source "${LOCK_PARENT}"
  set +a
  docker pull "${JUPYTERHUB_SINGLEUSER_IMAGE}"

  log 'starting engineering and data services'
  "${COMPOSE[@]}" up -d "${runtime_services[@]}"

  reconcile_products
  "${COMPOSE[@]}" up -d forgejo-runner
  health
}

converge() {
  local -a runtime_services=(
    devpi-bootstrap verdaccio harbor-nginx jupyterhub label-studio lakefs
    airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker
    mlflow tika grobid qdrant hayhooks
  )

  log 'converging prebuilt engineering and data services'
  "${FOUNDATION[@]}" up -d --no-build postgres redis rabbitmq keycloak caddy
  wait_service postgres
  wait_service redis
  wait_service rabbitmq
  reconcile_postgres
  "${COMPOSE[@]}" up -d --no-build "${runtime_services[@]}"
  reconcile_products
  "${COMPOSE[@]}" up -d --no-build forgejo-runner
  health
}

usage() {
  printf 'Usage: %s {start|converge|health}\n' "$0"
}

main() {
  require_command curl
  require_command docker
  docker compose version >/dev/null 2>&1 || die 'Docker Compose v2 is required'
  [[ -f "${LOCK_PARENT}" ]] || die "missing ${LOCK_PARENT}"

  case "${1:-start}" in
    start)
      start
      ;;
    converge)
      converge
      ;;
    health)
      health
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
