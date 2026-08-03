#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly LAYER=${1:-foundation}
readonly TIMEOUT=${KEPLEROPS_HEALTH_TIMEOUT:-900}
readonly ROUTE_REQUEST_TIMEOUT=${KEPLEROPS_ROUTE_REQUEST_TIMEOUT:-8}
readonly ROUTE_ADDRESS=${KEPLEROPS_ROUTE_ADDRESS:-10.61.10.2}
readonly ROUTE_CA=${KEPLEROPS_ROUTE_CA:-${ROOT}/state/caddy-root.crt}

routes=()

case "$LAYER" in
  foundation)
    required=(
      kep-v2-postgres kep-v2-redis kep-v2-rabbitmq kep-v2-pdns-auth
      kep-v2-pdns-recursor kep-v2-keycloak kep-v2-step-ca kep-v2-caddy
      kep-v2-otel-collector kep-v2-jaeger kep-v2-prometheus
      kep-v2-alertmanager kep-v2-grafana kep-v2-opensearch
    )
    ;;
  enterprise)
    required=(
      kep-v2-mariadb kep-v2-mongodb kep-v2-meilisearch
      kep-v2-public-site kep-v2-preview kep-v2-stalwart kep-v2-roundcube
      kep-v2-forgejo kep-v2-redmine kep-v2-nextcloud
      kep-v2-zammad-memcached kep-v2-zammad-railsserver
      kep-v2-zammad-scheduler kep-v2-zammad-websocket kep-v2-zammad-nginx
      kep-v2-langflow kep-v2-librechat kep-v2-unleash kep-v2-odoo
      kep-v2-ghost kep-v2-mautic
    )
    routes=(
      'public-site|keplerops.lab|/'
      'preview|preview.keplerops.lab|/'
      'webmail|webmail.keplerops.lab|/'
      'forgejo|git.keplerops.lab|/api/v1/version'
      'redmine|workhub.keplerops.lab|/login'
      'nextcloud|files.keplerops.lab|/status.php'
      'zammad|support.keplerops.lab|/api/v1/getting_started'
      'langflow|flows.keplerops.lab|/health'
      'librechat|assistant.keplerops.lab|/'
      'odoo|business.keplerops.lab|/web/login?db=business'
      'ghost|status.keplerops.lab|/'
      'mautic|advisories.keplerops.lab|/'
    )
    ;;
  *)
    echo "unknown health layer: $LAYER" >&2
    exit 2
    ;;
esac

[[ $TIMEOUT =~ ^[1-9][0-9]*$ ]] || {
  echo "KEPLEROPS_HEALTH_TIMEOUT must be a positive integer" >&2
  exit 2
}
[[ $ROUTE_REQUEST_TIMEOUT =~ ^[1-9][0-9]*$ ]] || {
  echo "KEPLEROPS_ROUTE_REQUEST_TIMEOUT must be a positive integer" >&2
  exit 2
}
if ((${#routes[@]} > 0)); then
  command -v curl >/dev/null 2>&1 || {
    echo "curl is required for routed application health checks" >&2
    exit 2
  }
  [[ -r $ROUTE_CA ]] || {
    echo "Caddy route CA is not readable: $ROUTE_CA" >&2
    exit 2
  }
fi

deadline=$((SECONDS + TIMEOUT))
while ((SECONDS < deadline)); do
  failed=()
  for container in "${required[@]}"; do
    state=$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' \
      "$container" 2>/dev/null || true)
    if [[ $state != "running healthy" && $state != "running " ]]; then
      failed+=("$container=$state")
    fi
  done
  if ((${#failed[@]} == 0)); then
    for route in "${routes[@]}"; do
      IFS='|' read -r name host path <<<"$route"
      if ! curl --silent --show-error --fail --location \
        --connect-timeout 3 --max-time "$ROUTE_REQUEST_TIMEOUT" \
        --cacert "$ROUTE_CA" --resolve "${host}:443:${ROUTE_ADDRESS}" \
        "https://${host}${path}" >/dev/null 2>&1; then
        failed+=("$name=https://${host}${path}")
      fi
    done
  fi
  if ((${#failed[@]} == 0)); then
    install -d -m 0755 /run/shifter
    printf '%s\n' "$(cat /proc/sys/kernel/random/boot_id) $LAYER" \
      >"/run/shifter/keplerops-v2-$LAYER.ready"
    echo "campaign-v2 $LAYER healthy"
    exit 0
  fi
  sleep 10
done

printf '%s health timeout: %s\n' "$LAYER" "${failed[*]}" >&2
cd "$ROOT"
docker compose --env-file component-lock.env \
  -f compose.foundation.yaml -f compose.enterprise.yaml ps >&2
exit 1
