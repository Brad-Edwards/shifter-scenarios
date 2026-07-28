#!/bin/bash
set -euo pipefail
umask 077

readonly METADATA_ROOT='http://metadata.google.internal/computeMetadata/v1'
readonly METADATA_HEADER='Metadata-Flavor: Google'

metadata() {
  curl --fail --silent --show-error \
    --connect-timeout 5 --max-time 20 \
    -H "$METADATA_HEADER" "$METADATA_ROOT/instance/attributes/$1"
}

access_token() {
  curl --fail --silent --show-error \
    --connect-timeout 5 --max-time 20 \
    -H "$METADATA_HEADER" \
    "$METADATA_ROOT/instance/service-accounts/default/token" |
    jq -er '.access_token'
}

secret_access() {
  local token
  token=$(access_token)
  curl --fail --silent --show-error \
    --connect-timeout 5 --max-time 20 \
    -H "Authorization: Bearer $token" \
    "https://secretmanager.googleapis.com/v1/projects/$PROJECT_ID/secrets/$OVERLAY_TOKEN_SECRET/versions/latest:access" |
    jq -er '.payload.data' | base64 -d
}

secret_publish() {
  local value=$1 token payload
  token=$(access_token)
  payload=$(printf '%s' "$value" | base64 -w 0)
  curl --fail --silent --show-error -X POST \
    --connect-timeout 5 --max-time 20 \
    -H "Authorization: Bearer $token" \
    -H 'Content-Type: application/json' \
    --data "{\"payload\":{\"data\":\"$payload\"}}" \
    "https://secretmanager.googleapis.com/v1/projects/$PROJECT_ID/secrets/$OVERLAY_TOKEN_SECRET:addVersion" \
    >/dev/null
}

runtime_secret_access() {
  local logical=$1 token secret_id
  token=$(access_token)
  secret_id="kep-${logical//-/}-$SECRET_SUFFIX"
  curl --fail --silent --show-error \
    --connect-timeout 5 --max-time 20 \
    -H "Authorization: Bearer $token" \
    "https://secretmanager.googleapis.com/v1/projects/$PROJECT_ID/secrets/$secret_id/versions/latest:access" |
    jq -er '.payload.data' | base64 -d
}

readonly HOST_ID=$(metadata keplerops-host-id)
readonly RANGE_INSTANCE=$(metadata keplerops-range-instance)
readonly PARTICIPANT=$(metadata keplerops-participant)
readonly REGION=$(metadata keplerops-region)
readonly PROJECT_ID=$(metadata keplerops-project-id)
readonly SECRET_SUFFIX=$(metadata keplerops-secret-suffix)
readonly WORKSPACE_BUCKET_NAME=$(metadata keplerops-workspace-bucket-name)
readonly OVERLAY_TOKEN_SECRET=$(metadata keplerops-overlay-token-secret)
readonly RANGE_OPS_SERVICE_ACCOUNT=$(metadata keplerops-range-ops-service-account)
readonly SHARED_MODEL_URL=$(metadata keplerops-shared-model-url)
readonly MANAGER_ID='range-linux-carrier-01'
readonly CARRIER_ROOT='/var/lib/keplerops-carrier'
readonly CARRIER_BIN="$CARRIER_ROOT/bin"
readonly WORKLOAD_COMMAND="$CARRIER_BIN/keplerops-workload"
readonly WORKLOAD_INTERNAL="$CARRIER_BIN/keplerops-workload-internal"
readonly WORKLOAD_BOOTSTRAP="$CARRIER_BIN/workload-bootstrap"
readonly REGISTRY_HOST="$REGION-docker.pkg.dev"

install -d -m 0700 \
  "$CARRIER_ROOT" "$CARRIER_BIN" "$CARRIER_ROOT/input" "$CARRIER_ROOT/workloads"
rm -f "$CARRIER_ROOT/ready"
if ! grep -Fq "secretmanager.googleapis.com $REGISTRY_HOST" /etc/hosts; then
  printf '199.36.153.4 secretmanager.googleapis.com %s\n' "$REGISTRY_HOST" \
    >>/etc/hosts
fi

# Docker's registry token client uses the daemon trust pool, not only the
# per-registry CA directory. Establish trust before any packed workload starts.
trust_root=$(mktemp -d /var/lib/keplerops-carrier/.registry-trust.XXXXXXXX)
trap 'rm -rf "$trust_root"' EXIT
runtime_secret_access tls-range-ops-controller >"$trust_root/tls.tar"
tar -xf "$trust_root/tls.tar" -C "$trust_root" ca.crt
registry_ca=/usr/local/share/ca-certificates/keplerops-range.crt
docker_ca=/etc/docker/certs.d/repo-ticket-01.keplerops.lab/ca.crt
trust_changed=false
if ! cmp -s "$trust_root/ca.crt" "$registry_ca" ||
  ! cmp -s "$trust_root/ca.crt" "$docker_ca"; then
  install -d -m 0755 "$(dirname "$docker_ca")"
  install -m 0644 "$trust_root/ca.crt" "$registry_ca"
  install -m 0644 "$trust_root/ca.crt" "$docker_ca"
  update-ca-certificates >/dev/null
  trust_changed=true
fi
rm -rf "$trust_root"
trap - EXIT

metadata keplerops-logical-networks >"$CARRIER_ROOT/input/logical-networks.json"
metadata keplerops-workload-plan >"$CARRIER_ROOT/input/workload-plan.json"
metadata keplerops-all-workload-plans >"$CARRIER_ROOT/input/all-workload-plans.json"
metadata keplerops-declared-routes >"$CARRIER_ROOT/input/declared-routes.json"
metadata keplerops-physical-host-ips >"$CARRIER_ROOT/input/physical-host-ips.json"
metadata keplerops-image-lock >"$CARRIER_ROOT/input/image-lock.json"
metadata keplerops-workload-bootstrap >"$WORKLOAD_BOOTSTRAP"
chmod 0500 "$WORKLOAD_BOOTSTRAP"

while read -r peer_ip; do
  for rule in \
    "-p tcp -m multiport --dports 2377,7946" \
    "-p udp -m multiport --dports 7946,4789" \
    "-p esp"; do
    read -r -a rule_args <<<"$rule"
    if ! iptables -C INPUT -s "$peer_ip" "${rule_args[@]}" -j ACCEPT 2>/dev/null; then
      iptables -I INPUT 1 -s "$peer_ip" "${rule_args[@]}" -j ACCEPT
    fi
  done
done < <(jq -r '.[]' "$CARRIER_ROOT/input/physical-host-ips.json")

if [[ ! -s /etc/docker/daemon.json ]]; then
  install -d -m 0755 /etc/docker
  printf '%s\n' '{"live-restore":false}' >/etc/docker/daemon.json
fi
if [[ $(jq -r '.["live-restore"] // false' /etc/docker/daemon.json) != false ]]; then
  daemon_config=$(mktemp /var/lib/docker/.daemon.XXXXXXXX.json)
  trap 'rm -f "$daemon_config"' EXIT
  jq '.["live-restore"] = false' /etc/docker/daemon.json >"$daemon_config"
  chmod 0600 "$daemon_config"
  mv "$daemon_config" /var/lib/docker/daemon.json
  trap - EXIT
  systemctl restart docker
elif [[ $trust_changed == true ]]; then
  systemctl restart docker
fi

readonly MANAGER_IP=$(
  jq -er --arg manager "$MANAGER_ID" '.[$manager]' \
    "$CARRIER_ROOT/input/physical-host-ips.json"
)
readonly WORKHUB_HOST_ID=$(
  jq -er '
    to_entries[]
    | select(.value | has("repo-ticket-01"))
    | .key
  ' "$CARRIER_ROOT/input/all-workload-plans.json"
)
readonly WORKHUB_HOST_IP=$(
  jq -er --arg host "$WORKHUB_HOST_ID" '.[$host]' \
    "$CARRIER_ROOT/input/physical-host-ips.json"
)

for attempt in $(seq 1 60); do
  [[ $(systemctl is-active docker) == active ]] && break
  [[ $attempt -lt 60 ]] || exit 1
  sleep 2
done

swarm_state=$(docker info --format '{{.Swarm.LocalNodeState}}')
if [[ "$swarm_state" != active ]]; then
  if [[ "$HOST_ID" == "$MANAGER_ID" ]]; then
    docker swarm init --advertise-addr "$MANAGER_IP"
  else
    if [[ "$swarm_state" != inactive ]]; then
      docker swarm leave --force >/dev/null 2>&1 || true
    fi
    for attempt in $(seq 1 120); do
      if join_token=$(secret_access 2>/dev/null) && [[ -n "$join_token" ]]; then
        if docker swarm join --token "$join_token" "$MANAGER_IP:2377"; then
          break
        fi
        [[ $(docker info --format '{{.Swarm.LocalNodeState}}') == active ]] && break
      fi
      [[ $attempt -lt 120 ]] || exit 1
      sleep 5
    done
  fi
fi

if [[ "$HOST_ID" == "$MANAGER_ID" ]]; then
  join_token=$(docker swarm join-token --quiet worker)
  current_token=$(secret_access 2>/dev/null || true)
  if [[ "$current_token" != "$join_token" ]]; then
    secret_publish "$join_token"
  fi
  while IFS=$'\t' read -r network cidr; do
    if ! docker network inspect "$network" >/dev/null 2>&1; then
      if [[ "$cidr" =~ ^([0-9]+\.[0-9]+\.[0-9]+)\.0/24$ ]]; then
        dynamic_range="${BASH_REMATCH[1]}.128/25"
      else
        echo "logical network $network must use a /24 CIDR" >&2
        exit 1
      fi
      docker network create \
        --driver overlay \
        --attachable \
        --opt encrypted \
        --subnet "$cidr" \
        --ip-range "$dynamic_range" \
        "$network" >/dev/null
    fi
  done < <(
    jq -r 'to_entries[] | [.key, .value] | @tsv' \
      "$CARRIER_ROOT/input/logical-networks.json"
  )

  while IFS=$'\t' read -r network _cidr; do
    for attempt in $(seq 1 120); do
      docker network inspect "$network" >/dev/null 2>&1 && break
      [[ $attempt -lt 120 ]] || exit 1
      sleep 2
    done
  done < <(
    jq -r 'to_entries[] | [.key, .value] | @tsv' \
      "$CARRIER_ROOT/input/logical-networks.json"
  )
fi

# Reboots may restore carrier-owned containers before this reconciliation pass
# starts. Remove the old generation together so overlay endpoints cannot race
# the sequential workload recreation below.
for attempt in $(seq 1 60); do
  mapfile -t existing_containers < <(
    docker ps -aq --filter name=keplerops-
  )
  ((${#existing_containers[@]} == 0)) && break
  docker rm -f "${existing_containers[@]}" >/dev/null 2>&1 || true
  [[ $attempt -lt 60 ]] || exit 1
  sleep 2
done

jq -r '
  to_entries[].value
  | to_entries[]
  | [.value.ip, (.key + ".keplerops.lab"), .key]
  | @tsv
' "$CARRIER_ROOT/input/all-workload-plans.json" |
  tr '\t' ' ' >"$CARRIER_ROOT/input/hosts"
jq -r '
  to_entries[]
  | [.value, (.key + ".keplerops.lab"), (.key + ".keplerops.test"), .key]
  | @tsv
' "$CARRIER_ROOT/input/physical-host-ips.json" |
  tr '\t' ' ' >>"$CARRIER_ROOT/input/hosts"

write_env() {
  printf 'export %s=%q\n' "$1" "$2"
}

prepare_workload() {
  local asset_id=$1 workload_root=$2 environment_file=$3
  local component image network asset_ip tcp_ports udp_ports route_networks
  local helper_image model_image platform_deployment_image mail_readiness_image auxiliary_images
  component=$(jq -er --arg asset "$asset_id" '.[$asset].component' "$CARRIER_ROOT/input/workload-plan.json")
  image=$(jq -er --arg asset "$asset_id" '.[$asset].image' "$CARRIER_ROOT/input/workload-plan.json")
  network=$(jq -er --arg asset "$asset_id" '.[$asset].network' "$CARRIER_ROOT/input/workload-plan.json")
  asset_ip=$(jq -er --arg asset "$asset_id" '.[$asset].ip' "$CARRIER_ROOT/input/workload-plan.json")
  tcp_ports=$(jq -r --arg asset "$asset_id" '.[$asset].tcp_ports | join(" ")' "$CARRIER_ROOT/input/workload-plan.json")
  udp_ports=$(jq -r --arg asset "$asset_id" '.[$asset].udp_ports | join(" ")' "$CARRIER_ROOT/input/workload-plan.json")
  route_networks=$(jq -r --arg source "$network" \
    '[.[] | select(.source == $source) | .destination] | unique | join(" ")' \
    "$CARRIER_ROOT/input/declared-routes.json")
  helper_image=$(jq -er '.images["terraform-gcp-range-controller"] | .uri + "@" + .digest' \
    "$CARRIER_ROOT/input/image-lock.json")
  model_image=$(jq -er '.images["vllm-open-model-hosting"] | .uri + "@" + .digest' \
    "$CARRIER_ROOT/input/image-lock.json")
  platform_deployment_image=$(jq -er \
    '.auxiliary_images["keplerops-platform-deployment"] | .uri + "@" + .digest' \
    "$CARRIER_ROOT/input/image-lock.json")
  mail_readiness_image=$(jq -er \
    '.auxiliary_images["mail-protocol-readiness"] | .uri + "@" + .digest' \
    "$CARRIER_ROOT/input/image-lock.json")
  auxiliary_images=$(jq -r \
    '[.auxiliary_images[] | .uri + "@" + .digest] | join(" ")' \
    "$CARRIER_ROOT/input/image-lock.json")

  install -d -m 0700 "$workload_root/state" "$workload_root/config" "$workload_root/input"
  install -m 0600 "$CARRIER_ROOT/input/hosts" "$workload_root/input/hosts"
  install -m 0600 "$CARRIER_ROOT/input/image-lock.json" "$workload_root/input/image-lock.json"
  {
    write_env ASSET_ID "$asset_id"
    write_env ASSET_IP "$asset_ip"
    write_env COMPONENT_ID "$component"
    write_env RUNTIME_IMAGE "$image"
    write_env HELPER_IMAGE "$helper_image"
    write_env SHARED_MODEL_IMAGE "$model_image"
    write_env RANGE_INSTANCE "$RANGE_INSTANCE"
    write_env PARTICIPANT "$PARTICIPANT"
    write_env PROJECT_ID "$PROJECT_ID"
    write_env RANGE_OPS_SERVICE_ACCOUNT "$RANGE_OPS_SERVICE_ACCOUNT"
    write_env SHARED_MODEL_URL "$SHARED_MODEL_URL"
    write_env WORKSPACE_BUCKET_NAME "$WORKSPACE_BUCKET_NAME"
    write_env PLATFORM_DEPLOYMENT_IMAGE "$platform_deployment_image"
    write_env SECRET_SUFFIX "$SECRET_SUFFIX"
    write_env REGION "$REGION"
    write_env HOST_ENTRIES_FILE "$workload_root/input/hosts"
    write_env IMAGE_LOCK_FILE "$workload_root/input/image-lock.json"
    write_env WORKLOAD_ROOT "$workload_root"
    write_env LOGICAL_NETWORK "$network"
    write_env RUNTIME_TCP_PORTS_TEXT "$tcp_ports"
    write_env RUNTIME_UDP_PORTS_TEXT "$udp_ports"
    write_env ROUTE_NETWORKS_TEXT "$route_networks"
    write_env WORKHUB_HOST_IP "$WORKHUB_HOST_IP"
    write_env EVIDENCE_PRODUCERS "$(metadata keplerops-evidence-producers)"
    write_env RESEARCH_CAPTURE_SIGNALS "$(metadata keplerops-research-capture-signals)"
    write_env AUXILIARY_IMAGES_TEXT "$auxiliary_images"
    write_env MAIL_PROTOCOL_READINESS_IMAGE "$mail_readiness_image"
    while IFS=$'\t' read -r image_id locked_image local_tag; do
      variable=$(printf 'AUX_%s_IMAGE' "$image_id" | tr '[:lower:]-' '[:upper:]_')
      write_env "$variable" "$locked_image"
      if [[ -n "$local_tag" ]]; then
        variable=$(printf 'AUX_%s_LOCAL_TAG' "$image_id" | tr '[:lower:]-' '[:upper:]_')
        write_env "$variable" "$local_tag"
      fi
    done < <(
      jq -r '
        .auxiliary_images
        | to_entries[]
        | [.key, (.value.uri + "@" + .value.digest), (.value.local_tag // "")]
        | @tsv
      ' "$CARRIER_ROOT/input/image-lock.json"
    )
  } >"$environment_file"
  chmod 0600 "$environment_file"
}

deactivate_workload() {
  if [[ -L /var/lib/keplerops ]]; then
    unlink /var/lib/keplerops
  fi
  if [[ -L /etc/keplerops ]]; then
    unlink /etc/keplerops
  fi
}

activate_workload() {
  local workload_root=$1
  if [[ -e /var/lib/keplerops && ! -L /var/lib/keplerops ]]; then
    echo '/var/lib/keplerops must remain carrier-managed' >&2
    exit 1
  fi
  if [[ -e /etc/keplerops && ! -L /etc/keplerops ]]; then
    echo '/etc/keplerops must remain carrier-managed' >&2
    exit 1
  fi
  deactivate_workload
  ln -s "$workload_root/state" /var/lib/keplerops
  ln -s "$workload_root/config" /etc/keplerops
}

run_workload_action() {
  local action=$1 asset_id=$2
  local workload_root="$CARRIER_ROOT/workloads/$asset_id"
  local environment_file="$workload_root/environment"
  if [[ "$action" == bootstrap || "$action" == reset || ! -s "$environment_file" ]]; then
    prepare_workload "$asset_id" "$workload_root" "$environment_file"
  fi
  # shellcheck source=/dev/null
  source "$environment_file"
  activate_workload "$workload_root"
  trap deactivate_workload RETURN
  case "$action" in
    bootstrap)
      bash "$WORKLOAD_BOOTSTRAP"
      ;;
    health|quiesce|reset|reset-verify)
      script=${action//-/-local}
      [[ "$action" == health ]] && script=health-local
      [[ "$action" == quiesce ]] && script=quiesce-local
      [[ "$action" == reset ]] && script=reset-local
      [[ "$action" == reset-verify ]] && script=reset-verify-local
      shift 2
      if [[ "$action" == reset ]]; then
        env \
          ASSET_ID="$ASSET_ID" \
          ASSET_IP="$ASSET_IP" \
          HOST_ENTRIES_FILE="$HOST_ENTRIES_FILE" \
          LOGICAL_NETWORK="$LOGICAL_NETWORK" \
          ROUTE_NETWORKS_TEXT="$ROUTE_NETWORKS_TEXT" \
          WORKLOAD_ROOT="$WORKLOAD_ROOT" \
          bash "$workload_root/state/$script" "$@"
        return
      fi
      main_container="keplerops-${asset_id}-runtime"
      pid=$(docker inspect --format '{{.State.Pid}}' "$main_container")
      nsenter --target "$pid" --net -- env \
        ASSET_ID="$ASSET_ID" \
        ASSET_IP="$ASSET_IP" \
        HOST_ENTRIES_FILE="$HOST_ENTRIES_FILE" \
        LOGICAL_NETWORK="$LOGICAL_NETWORK" \
        ROUTE_NETWORKS_TEXT="$ROUTE_NETWORKS_TEXT" \
        WORKLOAD_ROOT="$WORKLOAD_ROOT" \
        bash "$workload_root/state/$script" "$@"
      ;;
    exec)
      shift 2
      docker exec "keplerops-${asset_id}-runtime" "$@"
      ;;
    *)
      echo 'unsupported workload action' >&2
      exit 2
      ;;
  esac
}

cat >"$WORKLOAD_COMMAND" <<'WORKLOAD_COMMAND_SCRIPT'
#!/bin/bash
set -euo pipefail
[[ $# -ge 2 ]] || exit 2
exec flock /run/keplerops-workload.lock \
  bash /var/lib/keplerops-carrier/bin/keplerops-workload-internal "$@"
WORKLOAD_COMMAND_SCRIPT
chmod 0500 "$WORKLOAD_COMMAND"

declare -f metadata access_token secret_access secret_publish write_env \
  prepare_workload deactivate_workload activate_workload run_workload_action \
  >"$CARRIER_BIN/keplerops-workload-functions"
{
  printf '#!/bin/bash\nset -euo pipefail\n'
  declare -p METADATA_ROOT METADATA_HEADER HOST_ID RANGE_INSTANCE PARTICIPANT REGION \
    PROJECT_ID SECRET_SUFFIX WORKSPACE_BUCKET_NAME OVERLAY_TOKEN_SECRET \
    RANGE_OPS_SERVICE_ACCOUNT SHARED_MODEL_URL MANAGER_ID CARRIER_ROOT \
    CARRIER_BIN WORKLOAD_COMMAND WORKLOAD_INTERNAL WORKLOAD_BOOTSTRAP REGISTRY_HOST \
    WORKHUB_HOST_ID WORKHUB_HOST_IP |
    sed 's/^declare -r /declare /'
  cat "$CARRIER_BIN/keplerops-workload-functions"
  printf 'run_workload_action "$@"\n'
} >"$WORKLOAD_INTERNAL"
chmod 0500 "$WORKLOAD_INTERNAL"
rm -f "$CARRIER_BIN/keplerops-workload-functions"

mapfile -t workload_ids < <(
  jq -r '
    to_entries
    | sort_by(.value.startup_rank, .key)
    | .[].key
  ' "$CARRIER_ROOT/input/workload-plan.json"
)
for asset_id in "${workload_ids[@]}"; do
  bash "$WORKLOAD_COMMAND" bootstrap "$asset_id"
done

deactivate_workload
cat /proc/sys/kernel/random/boot_id >"$CARRIER_ROOT/ready"
chmod 0600 "$CARRIER_ROOT/ready"
