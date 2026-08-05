#!/bin/bash
set -euo pipefail
umask 077

: "${ASSET_ID:?}" "${ASSET_IP:?}" "${COMPONENT_ID:?}" "${RUNTIME_IMAGE:?}"
: "${HELPER_IMAGE:?}" "${SHARED_MODEL_IMAGE:?}"
: "${RANGE_INSTANCE:?}" "${PARTICIPANT:?}" "${PROJECT_ID:?}"
: "${RANGE_OPS_SERVICE_ACCOUNT:?}" "${WORKSPACE_BUCKET_NAME:?}"
: "${SHARED_MODEL_URL:?}"
: "${PLATFORM_DEPLOYMENT_IMAGE:?}" "${SECRET_SUFFIX:?}" "${REGION:?}"
: "${HOST_ENTRIES_FILE:?}" "${IMAGE_LOCK_FILE:?}" "${WORKLOAD_ROOT:?}"
: "${LOGICAL_NETWORK:?}" "${RUNTIME_TCP_PORTS_TEXT:=}" "${RUNTIME_UDP_PORTS_TEXT:=}"
: "${ROUTE_NETWORKS_TEXT:=}"
: "${WORKHUB_HOST_IP:?}"
: "${EVIDENCE_PRODUCERS:=}" "${RESEARCH_CAPTURE_SIGNALS:=}"
: "${AUXILIARY_IMAGES_TEXT:=}" "${MAIL_PROTOCOL_READINESS_IMAGE:?}"
readonly ASSET_ID ASSET_IP COMPONENT_ID RUNTIME_IMAGE HELPER_IMAGE
readonly RANGE_INSTANCE PARTICIPANT PROJECT_ID RANGE_OPS_SERVICE_ACCOUNT
readonly WORKSPACE_BUCKET_NAME PLATFORM_DEPLOYMENT_IMAGE SECRET_SUFFIX
readonly REGISTRY_HOST="$REGION-docker.pkg.dev"
readonly TLS_PROFILE='rsa-2048-v4-mtls'
readonly CONTAINER_PREFIX="keplerops-${ASSET_ID}"
readonly MAIN_CONTAINER="${CONTAINER_PREFIX}-runtime"

install -d -m 0700 /var/lib/keplerops /var/lib/keplerops/secrets /var/lib/keplerops/data /var/lib/keplerops/tls /etc/keplerops
export HOME=/var/lib/keplerops
export DOCKER_CONFIG=/var/lib/keplerops/.docker
chown -R 65532:65532 /var/lib/keplerops/data
if [[ "$0" != "/var/lib/keplerops/bootstrap" ]]; then
  cp "$0" /var/lib/keplerops/bootstrap
  chmod 0700 /var/lib/keplerops/bootstrap
fi
[[ -s /var/lib/keplerops/reset-generation ]] || printf '0\n' >/var/lib/keplerops/reset-generation
printf 'enabled\n' >/var/lib/keplerops/telemetry-enabled
chmod 0600 /var/lib/keplerops/telemetry-enabled
chown 65532:65532 /var/lib/keplerops/telemetry-enabled
readonly RESET_GENERATION=$(</var/lib/keplerops/reset-generation)
rm -f /var/lib/keplerops/quiesced

cat "$HOST_ENTRIES_FILE" >>/etc/hosts
printf '%s %s\n' \
  '199.36.153.4' \
  "$REGISTRY_HOST secretmanager.googleapis.com artifactregistry.googleapis.com storage.googleapis.com" \
  >>/etc/hosts

install -m 0600 "$IMAGE_LOCK_FILE" /etc/keplerops/environment-images.json
chmod 0600 /etc/keplerops/environment-images.json

PEER_ARGS=()
while read -r peer_ip peer_name; do
  [[ -n "$peer_ip" && -n "$peer_name" ]] && PEER_ARGS+=(--add-host "$peer_name:$peer_ip")
done <"$HOST_ENTRIES_FILE"

cat >/etc/keplerops/docker-wrapper.sh <<'DOCKER_WRAPPER'
#!/bin/bash

: "${ASSET_ID:?}" "${ASSET_IP:?}" "${HOST_ENTRIES_FILE:?}" "${LOGICAL_NETWORK:?}"
: "${WORKLOAD_ROOT:?}"
if [[ -z ${CONTAINER_PREFIX+x} ]]; then
  CONTAINER_PREFIX="keplerops-${ASSET_ID}"
fi
if [[ -z ${MAIN_CONTAINER+x} ]]; then
  MAIN_CONTAINER="${CONTAINER_PREFIX}-runtime"
fi
PEER_ARGS=()
while read -r peer_ip peer_name; do
  [[ -n "$peer_ip" && -n "$peer_name" ]] && PEER_ARGS+=(--add-host "$peer_name:$peer_ip")
done <"$HOST_ENTRIES_FILE"

docker_container_name() {
  local name=$1
  if [[ "$name" == keplerops-* ]]; then
    printf '%s-%s\n' "$CONTAINER_PREFIX" "${name#keplerops-}"
  else
    printf '%s\n' "$name"
  fi
}

docker_host_path() {
  local value=$1
  value=${value//src=\/var\/lib\/keplerops/src=$WORKLOAD_ROOT\/state}
  value=${value//src=\/etc\/keplerops/src=$WORKLOAD_ROOT\/config}
  if [[ "$value" == /var/lib/keplerops* ]]; then
    value="$WORKLOAD_ROOT/state${value#/var/lib/keplerops}"
  elif [[ "$value" == /etc/keplerops* ]]; then
    value="$WORKLOAD_ROOT/config${value#/etc/keplerops}"
  fi
  printf '%s\n' "$value"
}

restore_main_publications() {
  local pid publish_protocol publish_spec published_port target_port
  [[ -s "$WORKLOAD_ROOT/state/published-ports" ]] || return 0
  pid=$(command docker inspect --format '{{.State.Pid}}' "$MAIN_CONTAINER")
  while read -r publish_spec; do
    publish_protocol=tcp
    if [[ "$publish_spec" == */* ]]; then
      publish_protocol=${publish_spec##*/}
      publish_spec=${publish_spec%/*}
    fi
    if [[ "$publish_protocol" == tcp && "$publish_spec" =~ ^([0-9]+):([0-9]+)$ ]]; then
      published_port=${BASH_REMATCH[1]}
      target_port=${BASH_REMATCH[2]}
      if [[ "$published_port" != "$target_port" ]]; then
        nsenter --target "$pid" --net -- iptables -t nat -C PREROUTING \
          -p tcp --dport "$published_port" -j REDIRECT --to-ports "$target_port" \
          2>/dev/null ||
          nsenter --target "$pid" --net -- iptables -t nat -A PREROUTING \
            -p tcp --dport "$published_port" -j REDIRECT --to-ports "$target_port"
      fi
    fi
  done <"$WORKLOAD_ROOT/state/published-ports"
}

docker() {
  local subcommand=${1-}
  shift || true
  local -a args=()
  local argument status
  for argument in "$@"; do
    if [[ "$argument" == keplerops-* ]]; then
      args+=("$(docker_container_name "$argument")")
    else
      args+=("$(docker_host_path "$argument")")
    fi
  done
  command docker "$subcommand" "${args[@]}"
  status=$?
  if [[ $status == 0 && "$subcommand" == restart ]]; then
    for argument in "${args[@]}"; do
      if [[ "$argument" == "$MAIN_CONTAINER" ]]; then
        restore_main_publications
        break
      fi
    done
  fi
  return "$status"
}

docker_run() {
  local -a input=("$@") output=()
  local -a network_args=()
  local -a publications=()
  local name='' network='' index=0
  local publish_protocol publish_spec published_port target_port pid
  while (( index < ${#input[@]} )); do
    case "${input[$index]}" in
      --name)
        name=$(docker_container_name "${input[$((index + 1))]}")
        output+=(--name "$name")
        index=$((index + 2))
        ;;
      --network)
        network=${input[$((index + 1))]}
        if [[ "$network" == keplerops-* ]]; then
          network=$(docker_container_name "$network")
        fi
        index=$((index + 2))
        ;;
      -p|--publish)
        publications+=("${input[$((index + 1))]}")
        index=$((index + 2))
        ;;
      *)
        output+=("$(docker_host_path "${input[$index]}")")
        index=$((index + 1))
        ;;
    esac
  done
  if [[ "$name" == "$MAIN_CONTAINER" ]]; then
    network_args+=("${PEER_ARGS[@]}")
    if [[ "$ASSET_ID" == participant-workstation ]]; then
      network_args+=(--network bridge)
      for argument in "${publications[@]}"; do
        network_args+=(--publish "$argument")
      done
    else
      network_args+=(--network "$LOGICAL_NETWORK" --ip "$ASSET_IP")
      network_args+=(--network-alias "$ASSET_ID" --network-alias "$ASSET_ID.keplerops.lab")
    fi
  elif [[ -n "$name" ]]; then
    if [[ "$network" == none ]]; then
      network_args+=(--network none)
    elif [[ -n "$network" && "$network" != host ]]; then
      network_args+=("${PEER_ARGS[@]}")
      network_args+=(--network "$network")
    else
      network_args+=(--network "container:$MAIN_CONTAINER")
    fi
  elif [[ "$network" == none ]]; then
    network_args+=(--network none)
  elif [[ "$network" == host ]]; then
    network_args+=("${PEER_ARGS[@]}")
    network_args+=(--network "$LOGICAL_NETWORK")
  else
    network_args+=("${PEER_ARGS[@]}")
  fi
  command docker run "${network_args[@]}" "${output[@]}"
  if [[ "$name" == "$MAIN_CONTAINER" ]]; then
    printf '%s\n' "${publications[@]}" >"$WORKLOAD_ROOT/state/published-ports"
    chmod 0600 "$WORKLOAD_ROOT/state/published-ports"
    if [[ "$ASSET_ID" == participant-workstation ]]; then
      command docker network connect \
        --ip "$ASSET_IP" \
        --alias "$ASSET_ID" \
        --alias "$ASSET_ID.keplerops.lab" \
        "$LOGICAL_NETWORK" "$MAIN_CONTAINER"
    fi
    if [[ "$ASSET_ID" != participant-workstation ]]; then
      pid=$(command docker inspect --format '{{.State.Pid}}' "$MAIN_CONTAINER")
      for argument in "${publications[@]}"; do
        publish_protocol=tcp
        publish_spec=$argument
        if [[ "$publish_spec" == */* ]]; then
          publish_protocol=${publish_spec##*/}
          publish_spec=${publish_spec%/*}
        fi
        if [[ "$publish_protocol" == tcp && "$publish_spec" =~ ^([0-9]+):([0-9]+)$ ]]; then
          published_port=${BASH_REMATCH[1]}
          target_port=${BASH_REMATCH[2]}
          if [[ "$published_port" != "$target_port" ]]; then
            nsenter --target "$pid" --net -- iptables -t nat -A PREROUTING \
              -p tcp --dport "$published_port" -j REDIRECT --to-ports "$target_port"
          fi
        fi
      done
    fi
    local route_network
    for route_network in $ROUTE_NETWORKS_TEXT; do
      [[ "$route_network" == "$LOGICAL_NETWORK" ]] && continue
      command docker network connect "$route_network" "$MAIN_CONTAINER"
    done
  fi
}
DOCKER_WRAPPER
chmod 0500 /etc/keplerops/docker-wrapper.sh
# shellcheck source=/dev/null
. /etc/keplerops/docker-wrapper.sh

workload_netns() {
  local pid
  pid=$(command docker inspect --format '{{.State.Pid}}' "$MAIN_CONTAINER")
  [[ "$pid" =~ ^[1-9][0-9]*$ ]] || return 1
  nsenter --target "$pid" --net -- "$@"
}

pull_image() {
  local image=$1
  local attempt
  local ingest_root
  local -a ingest_roots=(
    /var/lib/containerd/io.containerd.content.v1.content/ingest
    /var/lib/docker/containerd/daemon/io.containerd.content.v1.content/ingest
  )
  for attempt in 1 2 3 4 5 6; do
    if docker pull "$image"; then
      return 0
    fi
    # A dropped large-layer transfer can leave an ingest transaction that
    # deterministically poisons every later retry.
    for ingest_root in "${ingest_roots[@]}"; do
      if [[ -d "$ingest_root" ]]; then
        find "$ingest_root" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
      fi
    done
    sleep $((attempt * 5))
  done
  return 1
}

if command -v docker-credential-gcr >/dev/null; then
  docker-credential-gcr configure-docker --registries "$REGISTRY_HOST"
else
  gcloud auth configure-docker "$REGISTRY_HOST" --quiet
fi
pull_image "$HELPER_IMAGE"
pull_image "$RUNTIME_IMAGE"
read -r -a AUXILIARY_IMAGES <<<"$AUXILIARY_IMAGES_TEXT"
for auxiliary_image in "${AUXILIARY_IMAGES[@]}"; do
  [[ -n "$auxiliary_image" ]] || continue
  pull_image "$auxiliary_image"
done

case "$ASSET_ID" in
  participant-workstation|idp-01|artifact-store-01|exfil-sink|notebook-runner-01|model-registry-01|research-index-01) readonly RUNTIME_UID=1000 ;;
  lab-portal|inference-gateway|guardrail-policy|telemetry-proof-01|range-ops-controller|platform-impact-01|platform-ml-01|platform-camera-01|platform-agent-01|policy-lab-01) readonly RUNTIME_UID=65532 ;;
  repo-ticket-01|dataset-store-01) readonly RUNTIME_UID=999 ;;
  distillation-runner-01) readonly RUNTIME_UID=50000 ;;
  mail-server-01) readonly RUNTIME_UID=2000 ;;
  webmail-01) readonly RUNTIME_UID=33 ;;
  text-generation-01|image-generation-01) readonly RUNTIME_UID=65534 ;;
  *) readonly RUNTIME_UID=0 ;;
esac

read -r -a RUNTIME_TCP_PORTS <<<"$RUNTIME_TCP_PORTS_TEXT"
read -r -a RUNTIME_UDP_PORTS <<<"$RUNTIME_UDP_PORTS_TEXT"

iptables_port_spec() {
  local value="$1"
  if [[ "$value" =~ ^[0-9]+-[0-9]+$ ]]; then
    echo "${value%-*}:${value#*-}"
  else
    echo "$value"
  fi
}

for runtime_port in "${RUNTIME_TCP_PORTS[@]}"; do
  runtime_rule_port=$(iptables_port_spec "$runtime_port")
  iptables -C INPUT -p tcp --dport "$runtime_rule_port" -j ACCEPT 2>/dev/null ||
    iptables -A INPUT -p tcp --dport "$runtime_rule_port" -j ACCEPT
done
for runtime_port in "${RUNTIME_UDP_PORTS[@]}"; do
  runtime_rule_port=$(iptables_port_spec "$runtime_port")
  iptables -C INPUT -p udp --dport "$runtime_rule_port" -j ACCEPT 2>/dev/null ||
    iptables -A INPUT -p udp --dport "$runtime_rule_port" -j ACCEPT
done
chown -R "$RUNTIME_UID:$RUNTIME_UID" /var/lib/keplerops/data
chown "$RUNTIME_UID:$RUNTIME_UID" /var/lib/keplerops/secrets
printf '%s\n' "$RUNTIME_UID" >/var/lib/keplerops/runtime-uid
printf 'resetting\n' >/var/lib/keplerops/runtime-state
chmod 0600 /var/lib/keplerops/runtime-state /var/lib/keplerops/reset-generation
chown "$RUNTIME_UID:$RUNTIME_UID" /var/lib/keplerops/runtime-state /var/lib/keplerops/reset-generation

secret_id() {
  local compact
  compact=$(printf '%s' "$1" | tr -d '-')
  printf 'kep-%s-%s' "$compact" "$SECRET_SUFFIX"
}

fetch_secret() {
  local logical=$1 destination=$2
  local directory filename temporary
  directory=$(dirname -- "$destination")
  filename=$(basename -- "$destination")
  temporary=".$filename.$$"
  rm -f -- "$directory/$temporary"
  docker run --rm --network host --add-host secretmanager.googleapis.com:199.36.153.4 \
    --mount type=bind,src="$directory",dst=/output \
    --user 0:0 \
    -e HOME=/tmp --entrypoint gcloud "$HELPER_IMAGE" \
    secrets versions access latest --project "$PROJECT_ID" --secret "$(secret_id "$logical")" \
    --out-file="/output/$temporary" >/dev/null
  mv -f -- "$directory/$temporary" "$destination"
  chmod 0600 "$destination"
  chown "$RUNTIME_UID:$RUNTIME_UID" "$destination"
}

fetch_tls() {
  fetch_secret "tls-$ASSET_ID" /var/lib/keplerops/tls.tar
  rm -rf /var/lib/keplerops/tls
  install -d -m 0700 /var/lib/keplerops/tls
  tar -xf /var/lib/keplerops/tls.tar -C /var/lib/keplerops/tls
  cat /etc/ssl/certs/ca-certificates.crt \
    /var/lib/keplerops/tls/ca.crt \
    >/var/lib/keplerops/tls/combined-ca.crt
  chmod 0600 /var/lib/keplerops/tls/*
  chown -R "$RUNTIME_UID:$RUNTIME_UID" /var/lib/keplerops/tls
}

write_runtime_config() {
  local role=$1
  cat >/etc/keplerops/runtime.yaml <<EOF
role: $role
asset_id: $ASSET_ID
range_instance: $RANGE_INSTANCE
reset_generation: $RESET_GENERATION
issuer: https://idp-01.keplerops.lab/realms/keplerops
identity_internal_issuer: https://idp-01.keplerops.lab:8443/realms/keplerops
audience: keplerops-lab
opa_url: http://guardrail-policy.keplerops.lab:8181
policy_api_url: https://guardrail-policy.keplerops.lab
agent_worker_url: http://127.0.0.1:8450
agent_action_worker_url: http://127.0.0.1:8451
package_resolver_url: http://package-resolver:8452
package_analysis_worker_url: http://package-analysis:8453
package_evaluation_worker_url: http://package-worker:8454
text_generation_url: http://text-generation-01.keplerops.lab:8080
image_generation_url: http://image-generation-01.keplerops.lab:8092
platform_agent_url: http://platform-agent-01.keplerops.lab:8470
platform_agent_admin_token_file: /run/keplerops/platform-agent-admin-token
platform_agent_seed_token_file: /run/keplerops/platform-agent-seed-token
platform_camera_url: https://platform-camera-01.keplerops.lab:8480
platform_camera_admin_token: keplerops-platform-camera-operator
platform_camera_init_token: keplerops-platform-camera-session
platform_deployment_url: http://range-ops-controller.keplerops.lab:8490
platform_deployment_token_file: /run/keplerops/platform-deployment-token
platform_impact_url: http://platform-impact-01.keplerops.lab:8460
platform_impact_admin_token: platform-impact-admin-synthetic
platform_ml_url: http://platform-ml-01.keplerops.lab:8470
mail_host: mail-server-01.keplerops.lab
workhub_url: https://repo-ticket-01.keplerops.lab
model_url: $SHARED_MODEL_URL
model_identity_audience: $SHARED_MODEL_URL
registry_url: http://model-registry-01.keplerops.lab:9000
artifact_store_url: https://artifact-store-01.keplerops.lab:9000
exfil_store_url: https://exfil-sink.keplerops.lab:9000
minio_user_file: /run/keplerops/minio-root-user
minio_password_file: /run/keplerops/minio-root-password
teacher_model_manifest_path: /opt/keplerops/environment/model.yaml
proof_url: https://telemetry-proof-01.keplerops.lab
research_ingest_url: https://telemetry-proof-01.keplerops.lab:4319
service_token_file: /run/keplerops/service-token
signing_key_file: /run/keplerops/signing-key
database_path: /var/lib/keplerops/proof.sqlite3
environment_image_lock_path: /etc/keplerops/environment-images.json
research_database_path: /var/lib/keplerops-research/research.sqlite3
research_pseudonym_key_file: /run/keplerops/research-pseudonym-key
research_content_key_file: /run/keplerops/research-content-key
otel_endpoint: https://telemetry-proof-01.keplerops.lab:4318
telemetry_queue_capacity: 256
telemetry_enabled_file: /run/keplerops/telemetry-enabled
research_capture_signals: $RESEARCH_CAPTURE_SIGNALS
postgres_host: dataset-store-01.keplerops.lab
postgres_password_file: /run/keplerops/postgres-password
producer_id: $ASSET_ID
producer_token_file: /run/keplerops/producer-token
producer_tokens_dir: /run/keplerops/producer-tokens
runtime_state_file: /run/keplerops/runtime-state
generation_file: /run/keplerops/reset-generation
challenge_contract_path: /opt/keplerops/sdl/keplerops-ai.sdl.yaml
agent_control_ui_path: /opt/keplerops/ui/agent-control.html
model_evasion_ui_path: /opt/keplerops/ui/model-evasion.html
context_poisoning_ui_path: /opt/keplerops/ui/context-poisoning.html
model_secrets_ui_path: /opt/keplerops/ui/model-secrets.html
agent_persistence_ui_path: /opt/keplerops/ui/agent-persistence.html
embedding_model_path: /models/context-embedding
privacy_population_path: /opt/keplerops/oracle/model-secrets.json
extraction_population_path: /opt/keplerops/oracle/model-extraction.json
backdoor_population_path: /opt/keplerops/oracle/model-backdoor.json
model_revision: 12fd25f77366fa6b3b4b768ec3050bf629380bac
policy_revision: guardrails-v2
safe_fields: [actor_role, asset_id, byte_count, destination, digest, event_kind, object_id, outcome_id, participant, range_instance, record_count, stage, status, timestamp, workflow_id]
EOF
  chmod 0600 /etc/keplerops/runtime.yaml
  chown "$RUNTIME_UID:$RUNTIME_UID" /etc/keplerops/runtime.yaml
}

runtime_mounts=(
  --mount type=bind,src=/etc/keplerops/runtime.yaml,dst=/etc/keplerops/runtime.yaml,readonly
  --mount type=bind,src=/etc/keplerops/environment-images.json,dst=/etc/keplerops/environment-images.json,readonly
  --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly
  --mount type=bind,src=/var/lib/keplerops/data,dst=/var/lib/keplerops
  --mount type=bind,src=/var/lib/keplerops/runtime-state,dst=/run/keplerops/runtime-state,readonly
  --mount type=bind,src=/var/lib/keplerops/reset-generation,dst=/run/keplerops/reset-generation,readonly
  --mount type=bind,src=/var/lib/keplerops/telemetry-enabled,dst=/run/keplerops/telemetry-enabled,readonly
)

docker rm -f keplerops-runtime keplerops-package-resolver keplerops-package-analysis \
  keplerops-package-worker keplerops-context-api keplerops-context-file-worker \
  keplerops-context-sync-worker keplerops-platform-agent keplerops-isolation-loader \
  keplerops-edge-registry keplerops-bounded-worker-engine keplerops-platform-deployment \
  keplerops-platform-deployment-lifecycle keplerops-green-activity \
  keplerops-workhub-registry-proxy >/dev/null 2>&1 || true
fetch_tls
case " $EVIDENCE_PRODUCERS " in
  *" $ASSET_ID "*) fetch_secret "producer-token-$ASSET_ID" /var/lib/keplerops/secrets/producer-token ;;
esac

case "$ASSET_ID" in
  participant-workstation)
    fetch_secret participant-password /var/lib/keplerops/secrets/participant-password
    docker_run -d --name keplerops-runtime --restart unless-stopped \
      --shm-size 1g --security-opt no-new-privileges -p 443:6901 \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/producer-token,dst=/run/keplerops/producer-token,readonly \
      --mount type=bind,src=/var/lib/keplerops/reset-generation,dst=/run/keplerops/reset-generation,readonly \
      -v /var/lib/keplerops/secrets/participant-password:/run/keplerops/participant-password:ro \
      -e KEPLEROPS_RANGE_INSTANCE="$RANGE_INSTANCE" \
      -e KEPLEROPS_PARTICIPANT="$PARTICIPANT" \
      -e KEPLEROPS_RESEARCH_INGEST_URL=https://telemetry-proof-01.keplerops.lab:4319 \
      -e SSL_CERT_FILE=/run/tls/ca.crt \
      --entrypoint /usr/local/bin/keplerops-kasm-startup "$RUNTIME_IMAGE"
    ;;
  lab-portal)
    fetch_secret service-token /var/lib/keplerops/secrets/service-token
    write_runtime_config portal
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only -p 443:8443 \
      --tmpfs /tmp:rw,noexec,nosuid,size=64m "${runtime_mounts[@]}" \
      --mount type=bind,src=/var/lib/keplerops/secrets/service-token,dst=/run/keplerops/service-token,readonly \
      -e SSL_CERT_FILE=/run/tls/ca.crt "$RUNTIME_IMAGE" \
      --ssl-keyfile /run/tls/tls.key --ssl-certfile /run/tls/tls.crt
    ;;
  idp-01)
    fetch_secret ad-federation-bind-password /var/lib/keplerops/secrets/ad-federation-bind-password
    docker_run -d --name keplerops-runtime --restart unless-stopped -p 443:8443 \
      --tmpfs /tmp:rw,noexec,nosuid,size=256m \
      --mount type=bind,src=/var/lib/keplerops/data,dst=/opt/keycloak/data \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/ad-federation-bind-password,dst=/run/keplerops/ad-federation-bind-password,readonly \
      -e RANGE_INSTANCE="$RANGE_INSTANCE" \
      -e LDAP_BIND_CREDENTIAL_FILE=/run/keplerops/ad-federation-bind-password \
      "$RUNTIME_IMAGE" start-dev --import-realm \
      --https-port=8443 --https-certificate-file=/run/tls/tls.crt --https-certificate-key-file=/run/tls/tls.key \
      --truststore-paths=/run/tls/ca.crt \
      --hostname=idp-01.keplerops.lab --hostname-strict=true
    ;;
  repo-ticket-01)
    fetch_secret platform-context-token /var/lib/keplerops/secrets/platform-context-token
    fetch_secret keycloak-platform-context-secret /var/lib/keplerops/secrets/keycloak-platform-context-secret
    fetch_secret postgres-password /var/lib/keplerops/secrets/postgres-password
    install -d -m 0750 /var/lib/keplerops/data/gitea/conf /var/lib/keplerops/data/redmine/files /var/lib/keplerops/data/redmine/sqlite
    chown -R 999:999 /var/lib/keplerops/data
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only -p 443:8443 \
      --tmpfs /tmp:rw,noexec,nosuid,size=256m \
      --tmpfs /usr/src/redmine/tmp:rw,noexec,nosuid,size=128m,uid=999,gid=999,mode=0750 \
      --tmpfs /usr/src/redmine/log:rw,noexec,nosuid,size=128m,uid=999,gid=999,mode=0750 \
      --tmpfs /usr/src/redmine/public/assets:rw,noexec,nosuid,size=256m,uid=999,gid=999,mode=0750 \
      --mount type=bind,src=/var/lib/keplerops/data/gitea,dst=/data/gitea \
      --mount type=bind,src=/var/lib/keplerops/data/redmine/files,dst=/usr/src/redmine/files \
      --mount type=bind,src=/var/lib/keplerops/data/redmine/sqlite,dst=/usr/src/redmine/sqlite \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      -e REDMINE_DB_SQLITE=/usr/src/redmine/sqlite/redmine.db "$RUNTIME_IMAGE" # gitea-redmine-workhub
    for attempt in $(seq 1 60); do
      if [[ -s /var/lib/keplerops/data/gitea/platform-context-gitea-token \
        && -s /var/lib/keplerops/data/redmine/sqlite/platform-context-redmine-key ]]; then
        break
      fi
      [[ $attempt -lt 60 ]] || exit 1
      sleep 2
    done
    install -d -m 0700 -o 65532 -g 65532 \
      /var/lib/keplerops/context-secrets \
      /var/lib/keplerops/data/platform-context \
      /var/lib/keplerops/data/context-shared \
      /var/lib/keplerops/data/context-workhub
    chown -R 65532:65532 /var/lib/keplerops/data/platform-context
    install -m 0600 -o 65532 -g 65532 \
      /var/lib/keplerops/data/gitea/platform-context-gitea-token \
      /var/lib/keplerops/context-secrets/workhub-gitea-token
    install -m 0600 -o 65532 -g 65532 \
      /var/lib/keplerops/data/redmine/sqlite/platform-context-redmine-key \
      /var/lib/keplerops/context-secrets/workhub-redmine-key
    install -m 0600 -o 65532 -g 65532 \
      /var/lib/keplerops/secrets/platform-context-token \
      /var/lib/keplerops/context-secrets/platform-context-token
    install -m 0600 -o 65532 -g 65532 \
      /var/lib/keplerops/secrets/keycloak-platform-context-secret \
      /var/lib/keplerops/context-secrets/keycloak-platform-context-secret
    install -m 0600 -o 65532 -g 65532 \
      /var/lib/keplerops/secrets/postgres-password \
      /var/lib/keplerops/context-secrets/postgres-password
    install -m 0600 -o 65532 -g 65532 \
      /var/lib/keplerops/tls/ca.crt /var/lib/keplerops/context-secrets/ca.crt
    context_mounts=(
      --mount type=bind,src=/var/lib/keplerops/data/platform-context,dst=/var/lib/keplerops-platform-context
      --mount type=bind,src=/var/lib/keplerops/data/context-shared,dst=/mnt/keplerops-context/shared,readonly
      --mount type=bind,src=/var/lib/keplerops/data/context-workhub,dst=/mnt/keplerops-context/workhub,readonly
      --mount type=bind,src=/var/lib/keplerops/context-secrets,dst=/run/keplerops,readonly
      --mount type=bind,src=/var/lib/keplerops/context-secrets/ca.crt,dst=/run/tls/ca.crt,readonly
    )
    context_environment=(
      -e PLATFORM_CONTEXT_CA_FILE=/run/tls/ca.crt
      -e PLATFORM_CONTEXT_TOKEN_FILE=/run/keplerops/platform-context-token
      -e PLATFORM_CONTEXT_GITEA_TOKEN_FILE=/run/keplerops/workhub-gitea-token
      -e PLATFORM_CONTEXT_REDMINE_KEY_FILE=/run/keplerops/workhub-redmine-key
      -e PLATFORM_CONTEXT_KEYCLOAK_SECRET_FILE=/run/keplerops/keycloak-platform-context-secret
      -e PLATFORM_CONTEXT_POSTGRES_PASSWORD_FILE=/run/keplerops/postgres-password
      -e PLATFORM_CONTEXT_ADAPTER_URL=http://127.0.0.1:8480
      -e PLATFORM_CONTEXT_GITEA_URL=https://repo-ticket-01.keplerops.lab:8443/git/api/v1
      -e PLATFORM_CONTEXT_REDMINE_URL=https://repo-ticket-01.keplerops.lab:8443/tickets
      -e PLATFORM_CONTEXT_KEYCLOAK_URL=https://idp-01.keplerops.lab:8443
      -e PLATFORM_CONTEXT_OPENSEARCH_URL=http://research-index-01.keplerops.lab:9200
    )
    docker_run -d --name keplerops-context-api --restart unless-stopped --read-only \
      --network host --tmpfs /tmp:rw,noexec,nosuid,size=64m,uid=65532,gid=65532 \
      "${context_mounts[@]}" "${context_environment[@]}" "$AUX_KEPLEROPS_PLATFORM_CONTEXT_IMAGE" api
    docker_run -d --name keplerops-context-file-worker --restart unless-stopped --read-only \
      --network host --tmpfs /tmp:rw,noexec,nosuid,size=64m,uid=65532,gid=65532 \
      "${context_mounts[@]}" "${context_environment[@]}" "$AUX_KEPLEROPS_PLATFORM_CONTEXT_IMAGE" \
      file-worker --poll-seconds 1
    docker_run -d --name keplerops-context-sync-worker --restart unless-stopped --read-only \
      --network host --tmpfs /tmp:rw,noexec,nosuid,size=64m,uid=65532,gid=65532 \
      "${context_mounts[@]}" "${context_environment[@]}" "$AUX_KEPLEROPS_PLATFORM_CONTEXT_IMAGE" \
      sync-worker --poll-seconds 2
    ;;
  platform-camera-01)
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only \
      --network host --tmpfs /tmp:rw,noexec,nosuid,size=128m,uid=65532,gid=65532 \
      --mount type=bind,src=/var/lib/keplerops/data,dst=/var/lib/keplerops-platform-camera \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      -e PLATFORM_CAMERA_TLS_SERVER_NAME=platform-camera-01.keplerops.lab \
      -e PLATFORM_CAMERA_ML_BASE_URL=http://platform-ml-01.keplerops.lab:8470 \
      "$RUNTIME_IMAGE"
    ;;
  platform-agent-01)
    fetch_secret platform-agent-admin-token /var/lib/keplerops/secrets/platform-agent-admin-token
    fetch_secret platform-agent-seed-token /var/lib/keplerops/secrets/platform-agent-seed-token
    fetch_secret platform-isolation-admin-token /var/lib/keplerops/secrets/platform-isolation-admin-token
    fetch_secret edge-registry-admin-token /var/lib/keplerops/secrets/edge-registry-admin-token
    install -d -m 0700 -o 65532 -g 65532 \
      /var/lib/keplerops/data/platform-agent \
      /var/lib/keplerops/data/platform-isolation \
      /var/lib/keplerops/data/edge-registry \
      /var/lib/keplerops/data/k6
    install -d -m 0770 -o 1000 -g 1000 /run/keplerops-bounded-worker
    install -d -m 0700 -o 1000 -g 1000 /var/lib/keplerops/data/bounded-worker-engine
    chown -R 1000:1000 \
      /run/keplerops-bounded-worker \
      /var/lib/keplerops/data/bounded-worker-engine
    chmod 0770 /run/keplerops-bounded-worker
    docker_run -d --name keplerops-bounded-worker-engine --restart unless-stopped \
      --privileged --security-opt apparmor=unconfined --network bridge \
      --add-host "$REGISTRY_HOST:199.36.153.4" \
      --mount type=bind,src=/run/keplerops-bounded-worker,dst=/run/user/1000 \
      --mount type=bind,src=/var/lib/keplerops/data/bounded-worker-engine,dst=/home/rootless/.local/share/docker \
      "$AUX_KEPLEROPS_BOUNDED_WORKER_ENGINE_IMAGE"
    for attempt in $(seq 1 60); do
      if docker --host=unix:///run/keplerops-bounded-worker/docker.sock info >/dev/null 2>&1; then
        break
      fi
      [[ $attempt -lt 60 ]] || exit 1
      sleep 2
    done
    chgrp 1000 /run/keplerops-bounded-worker/docker.sock
    chmod 0660 /run/keplerops-bounded-worker/docker.sock
    inner_docker_config=$(mktemp -d /var/lib/keplerops/.inner-docker.XXXXXX)
    trap 'rm -rf -- "$inner_docker_config"' EXIT
    docker run --rm --network host --env HOME=/tmp --env CLOUDSDK_CONFIG=/tmp/gcloud \
      --entrypoint gcloud "$HELPER_IMAGE" auth print-access-token | \
      DOCKER_CONFIG="$inner_docker_config" \
      docker --host=unix:///run/keplerops-bounded-worker/docker.sock login \
        --username oauth2accesstoken --password-stdin "$REGISTRY_HOST" >/dev/null
    DOCKER_CONFIG="$inner_docker_config" \
      docker --host=unix:///run/keplerops-bounded-worker/docker.sock \
      pull "$AUX_KEPLEROPS_BOUNDED_PYTHON_WORKER_IMAGE"
    DOCKER_CONFIG="$inner_docker_config" \
      docker --host=unix:///run/keplerops-bounded-worker/docker.sock logout "$REGISTRY_HOST" >/dev/null
    rm -rf -- "$inner_docker_config"
    trap - EXIT
    docker network disconnect bridge keplerops-bounded-worker-engine
    platform_control_mounts=(
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly
      --mount type=bind,src=/var/lib/keplerops/secrets,dst=/run/keplerops,readonly
      --mount type=bind,src=/run/keplerops-bounded-worker,dst=/run/keplerops-worker
      --group-add 1000
    )
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only \
      --network host --security-opt no-new-privileges --cap-drop ALL \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m,uid=65532,gid=65532 \
      "${platform_control_mounts[@]}" \
      --mount type=bind,src=/var/lib/keplerops/data/platform-agent,dst=/var/lib/keplerops-platform-agent \
      -e PLATFORM_AGENT_ADMIN_TOKEN_FILE=/run/keplerops/platform-agent-admin-token \
      -e PLATFORM_AGENT_SEED_TOKEN_FILE=/run/keplerops/platform-agent-seed-token \
      -e PLATFORM_AGENT_WORKER_IMAGE="$AUX_KEPLEROPS_BOUNDED_PYTHON_WORKER_IMAGE" \
      "$RUNTIME_IMAGE"
    docker_run -d --name keplerops-isolation-loader --restart unless-stopped --read-only \
      --network host --security-opt no-new-privileges --cap-drop ALL \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m,uid=65532,gid=65532 \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets,dst=/run/keplerops,readonly \
      --mount type=bind,src=/run/keplerops-bounded-worker,dst=/run/keplerops-isolation-engine \
      --mount type=bind,src=/var/lib/keplerops/data/platform-isolation,dst=/var/lib/keplerops-isolation \
      --group-add 1000 \
      -e ISOLATION_ADMIN_TOKEN_FILE=/run/keplerops/platform-isolation-admin-token \
      -e ISOLATION_WORKER_IMAGE="$AUX_KEPLEROPS_BOUNDED_PYTHON_WORKER_IMAGE" \
      "$AUX_KEPLEROPS_PLATFORM_ISOLATION_LOADER_IMAGE"
    docker_run -d --name keplerops-edge-registry --restart unless-stopped --read-only \
      --network host --security-opt no-new-privileges --cap-drop ALL \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m,uid=65532,gid=65532 \
      --mount type=bind,src=/var/lib/keplerops/secrets,dst=/run/keplerops,readonly \
      --mount type=bind,src=/var/lib/keplerops/data/edge-registry,dst=/var/lib/keplerops-edge-registry \
      -e EDGE_REGISTRY_ADMIN_TOKEN_FILE=/run/keplerops/edge-registry-admin-token \
      "$AUX_KEPLEROPS_EDGE_REGISTRY_IMAGE"
    cat >/var/lib/keplerops/run-bounded-client <<BOUNDED_CLIENT
#!/bin/bash
set -euo pipefail
: "\${ASSET_ID:?}"
. /etc/keplerops/docker-wrapper.sh
[[ \$# == 4 ]] || exit 2
[[ \$1 =~ ^https?://(localhost|127\.0\.0\.1|[a-z0-9][a-z0-9.-]*\.keplerops\.lab)(:[0-9]{1,5})?/[a-zA-Z0-9/_-]*$ ]] || exit 2
[[ \$2 =~ ^[1-5]$ ]] || exit 2
[[ \$3 =~ ^([1-9]|[1-5][0-9]|60)$ ]] || exit 2
[[ \$4 =~ ^([1-9]|10)$ ]] || exit 2
exec docker_run --rm --network host --read-only --security-opt no-new-privileges --cap-drop ALL \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m \
  --mount type=bind,src=/var/lib/keplerops/data/k6,dst=/var/lib/keplerops-k6 \
  -e TARGET_URL="\$1" -e CLIENT_RATE="\$2" -e CLIENT_SECONDS="\$3" -e CLIENT_MAX_VUS="\$4" \
  "$AUX_KEPLEROPS_K6_RUNNER_IMAGE"
BOUNDED_CLIENT
    chmod 0700 /var/lib/keplerops/run-bounded-client
    ;;
  policy-lab-01)
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only \
      --network host --security-opt no-new-privileges --cap-drop ALL \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=32m,uid=65532,gid=65532 \
      "$RUNTIME_IMAGE"
    ;;
  inference-gateway)
    fetch_secret service-token /var/lib/keplerops/secrets/service-token
    fetch_secret postgres-password /var/lib/keplerops/secrets/postgres-password
    fetch_secret minio-root-user /var/lib/keplerops/secrets/minio-root-user
    fetch_secret minio-root-password /var/lib/keplerops/secrets/minio-root-password
    fetch_secret producer-token-inference-gateway /var/lib/keplerops/secrets/producer-token
    fetch_secret platform-agent-admin-token /var/lib/keplerops/secrets/platform-agent-admin-token
    fetch_secret platform-agent-seed-token /var/lib/keplerops/secrets/platform-agent-seed-token
    fetch_secret platform-deployment-token /var/lib/keplerops/secrets/platform-deployment-token
    write_runtime_config gateway
    docker network inspect keplerops-gateway >/dev/null 2>&1 || docker network create keplerops-gateway >/dev/null
    docker network inspect keplerops-package-control >/dev/null 2>&1 || \
      docker network create --internal keplerops-package-control >/dev/null
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only \
      --network keplerops-gateway -p 443:8444 \
      --tmpfs /tmp:rw,noexec,nosuid,size=64m "${runtime_mounts[@]}" \
      --mount type=bind,src=/var/lib/keplerops/secrets/service-token,dst=/run/keplerops/service-token,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/postgres-password,dst=/run/keplerops/postgres-password,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/minio-root-user,dst=/run/keplerops/minio-root-user,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/minio-root-password,dst=/run/keplerops/minio-root-password,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/producer-token,dst=/run/keplerops/producer-token,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/platform-agent-admin-token,dst=/run/keplerops/platform-agent-admin-token,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/platform-agent-seed-token,dst=/run/keplerops/platform-agent-seed-token,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/platform-deployment-token,dst=/run/keplerops/platform-deployment-token,readonly \
      -e SSL_CERT_FILE=/run/tls/combined-ca.crt "$RUNTIME_IMAGE" # envoy-fastapi-inference-gateway
    docker network connect --alias gateway keplerops-gateway keplerops-runtime
    docker network connect --alias gateway keplerops-package-control keplerops-runtime
    docker_run -d --name keplerops-package-resolver --restart unless-stopped --read-only \
      --network keplerops-gateway --security-opt no-new-privileges --cap-drop ALL \
      --tmpfs /tmp:rw,noexec,nosuid,size=128m \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      -e KEPLEROPS_PACKAGE_WORKER_MODE=resolver --entrypoint python "$RUNTIME_IMAGE" \
      -m uvicorn python_package_worker:app --host 0.0.0.0 --port 8452 --no-access-log --no-proxy-headers
    for route_network in $ROUTE_NETWORKS_TEXT; do
      docker network inspect "$route_network" >/dev/null 2>&1 || continue
      docker network connect "$route_network" keplerops-package-resolver
    done
    docker network connect --alias package-resolver keplerops-package-control keplerops-package-resolver
    docker_run -d --name keplerops-package-analysis --restart unless-stopped --read-only \
      --network keplerops-package-control --network-alias package-analysis \
      --security-opt no-new-privileges --cap-drop ALL \
      --tmpfs /tmp:rw,noexec,nosuid,size=128m \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      -e KEPLEROPS_PACKAGE_WORKER_MODE=analysis --entrypoint python "$RUNTIME_IMAGE" \
      -m uvicorn python_package_worker:app --host 0.0.0.0 --port 8453 --no-access-log --no-proxy-headers
    docker_run -d --name keplerops-package-worker --restart unless-stopped --read-only \
      --network keplerops-package-control --network-alias package-worker \
      --security-opt no-new-privileges --cap-drop ALL \
      --tmpfs /tmp:rw,noexec,nosuid,size=128m \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      -e KEPLEROPS_PACKAGE_WORKER_MODE=worker --entrypoint python "$RUNTIME_IMAGE" \
      -m uvicorn python_package_worker:app --host 0.0.0.0 --port 8454 --no-access-log --no-proxy-headers
    ;;
  guardrail-policy)
    fetch_secret service-token /var/lib/keplerops/secrets/service-token
    fetch_secret producer-token-guardrail-policy /var/lib/keplerops/secrets/producer-token
    write_runtime_config policy
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only -p 443:8443 -p 8181:8181 \
      --tmpfs /tmp:rw,noexec,nosuid,size=64m "${runtime_mounts[@]}" \
      --mount type=bind,src=/var/lib/keplerops/secrets/service-token,dst=/run/keplerops/service-token,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/producer-token,dst=/run/keplerops/producer-token,readonly \
      -e SSL_CERT_FILE=/run/tls/ca.crt "$RUNTIME_IMAGE" # opa-guardrail-policy
    ;;
  model-registry-01)
    fetch_secret minio-root-user /var/lib/keplerops/secrets/minio-root-user
    fetch_secret minio-root-password /var/lib/keplerops/secrets/minio-root-password
    pull_image "$SHARED_MODEL_IMAGE"
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only \
      -p 5000:5000 -p 9000:5000 \
      --tmpfs /tmp:rw,noexec,nosuid,size=128m \
      --mount type=bind,src=/var/lib/keplerops/data,dst=/data \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets,dst=/run/keplerops,readonly \
      --entrypoint sh "$RUNTIME_IMAGE" -c 'export AWS_ACCESS_KEY_ID=$(cat /run/keplerops/minio-root-user) AWS_SECRET_ACCESS_KEY=$(cat /run/keplerops/minio-root-password) MLFLOW_S3_ENDPOINT_URL=https://artifact-store-01.keplerops.lab:9000 AWS_CA_BUNDLE=/run/tls/ca.crt SSL_CERT_FILE=/run/tls/ca.crt; exec mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:////data/mlflow.db --artifacts-destination s3://keplerops-artifacts'
    for attempt in $(seq 1 30); do
      if docker_run --rm --network host --user 1000:1000 \
        --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
        --mount type=bind,src=/var/lib/keplerops/secrets,dst=/run/keplerops,readonly \
        --entrypoint python3 "$SHARED_MODEL_IMAGE" /opt/keplerops/register_model.py; then
        break
      fi
      [[ $attempt -lt 30 ]] || exit 1
      sleep 10
    done
    ;;
  artifact-store-01|exfil-sink)
    fetch_secret minio-root-user /var/lib/keplerops/secrets/minio-root-user
    fetch_secret minio-root-password /var/lib/keplerops/secrets/minio-root-password
    if [[ "$ASSET_ID" == artifact-store-01 ]]; then KEPLEROPS_BUCKET=keplerops-artifacts; else KEPLEROPS_BUCKET=keplerops-exfil; fi
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only --network host \
      --tmpfs /tmp:rw,noexec,nosuid,size=64m \
      --mount type=bind,src=/var/lib/keplerops/data,dst=/data \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets,dst=/run/keplerops,readonly \
      -e KEPLEROPS_BUCKET="$KEPLEROPS_BUCKET" "$RUNTIME_IMAGE" # minio server via image entrypoint
    ;;
  dataset-store-01)
    fetch_secret postgres-password /var/lib/keplerops/secrets/postgres-password
    cat >/etc/keplerops/pg_hba.conf <<'POSTGRES_HBA'
local all all trust
host all all 127.0.0.1/32 trust
host all all ::1/128 trust
hostssl all all 10.71.0.0/16 scram-sha-256
host all all 0.0.0.0/0 reject
POSTGRES_HBA
    chmod 0444 /etc/keplerops/pg_hba.conf
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only --network host \
      --tmpfs /tmp:rw,noexec,nosuid,size=64m \
      --tmpfs /var/run/postgresql:rw,noexec,nosuid,size=16m \
      --mount type=bind,src=/var/lib/keplerops/data,dst=/var/lib/postgresql/data \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      --mount type=bind,src=/etc/keplerops/pg_hba.conf,dst=/run/keplerops/pg_hba.conf,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/postgres-password,dst=/run/keplerops/postgres-password,readonly \
      -e POSTGRES_USER=keplerops -e POSTGRES_DB=keplerops -e POSTGRES_PASSWORD_FILE=/run/keplerops/postgres-password \
      "$RUNTIME_IMAGE" -c ssl=on -c ssl_cert_file=/run/tls/tls.crt -c ssl_key_file=/run/tls/tls.key \
      -c hba_file=/run/keplerops/pg_hba.conf # postgresql-dataset-store
    for attempt in $(seq 1 60); do
      if docker exec keplerops-runtime pg_isready --quiet; then
        break
      fi
      [[ $attempt -lt 60 ]] || exit 1
      sleep 2
    done
    for attempt in $(seq 1 90); do
      if docker exec keplerops-runtime sh -c \
        'test "$(head -n1 /var/lib/postgresql/data/postmaster.pid 2>/dev/null)" = 1' &&
        docker exec keplerops-runtime psql -U keplerops -d postgres -tAc 'SELECT 1' |
        grep -qx 1; then
        break
      fi
      [[ $attempt -lt 90 ]] || exit 1
      sleep 2
    done
    if ! docker exec keplerops-runtime psql -U keplerops -d postgres -tAc \
      "SELECT 1 FROM pg_database WHERE datname = 'keplerops'" | grep -qx 1; then
      for attempt in $(seq 1 30); do
        if docker exec keplerops-runtime createdb -U keplerops keplerops; then
          break
        fi
        [[ $attempt -lt 30 ]] || exit 1
        sleep 2
      done
      docker exec keplerops-runtime /docker-entrypoint-initdb.d/10-keplerops.sh
      for seed in 20-keplerops-data.sql 30-keplerops-company-data.sql; do
        docker exec keplerops-runtime psql --set ON_ERROR_STOP=1 \
          -U keplerops -d keplerops -f "/docker-entrypoint-initdb.d/$seed"
      done
    fi
    ;;
  distillation-runner-01)
    fetch_secret service-token /var/lib/keplerops/secrets/service-token
    fetch_secret postgres-password /var/lib/keplerops/secrets/postgres-password
    fetch_secret producer-token-distillation-runner-01 /var/lib/keplerops/secrets/producer-token
    docker_run -d --name keplerops-runtime --restart unless-stopped --network host \
      --tmpfs /tmp:rw,noexec,nosuid,size=256m \
      --mount type=bind,src=/var/lib/keplerops/data,dst=/var/lib/airflow \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/service-token,dst=/run/keplerops/service-token,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/postgres-password,dst=/run/keplerops/postgres-password,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/producer-token,dst=/run/keplerops/producer-token,readonly \
      --mount type=bind,src=/var/lib/keplerops/reset-generation,dst=/run/keplerops/reset-generation,readonly \
      -e AIRFLOW_HOME=/var/lib/airflow \
      -e AIRFLOW__CORE__DAGS_FOLDER=/opt/airflow/dags \
      -e AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS=ml.engineer:admin \
      -e AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE=/opt/keplerops/airflow-passwords.json \
      -e KEPLEROPS_RANGE_INSTANCE="$RANGE_INSTANCE" \
      -e KEPLEROPS_PARTICIPANT="$PARTICIPANT" \
      -e KEPLEROPS_MODEL_URL="$SHARED_MODEL_URL" \
      -e KEPLEROPS_RESEARCH_INGEST_URL=https://telemetry-proof-01.keplerops.lab:4319 \
      "$RUNTIME_IMAGE" standalone
    ;;
  notebook-runner-01)
    fetch_secret jupyter-token /var/lib/keplerops/secrets/jupyter-token
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only --network host \
      --tmpfs /tmp:rw,noexec,nosuid,size=256m \
      --mount type=bind,src=/var/lib/keplerops/data,dst=/home/jovyan/work \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/jupyter-token,dst=/run/keplerops/jupyter-token,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/producer-token,dst=/run/keplerops/producer-token,readonly \
      --mount type=bind,src=/var/lib/keplerops/reset-generation,dst=/run/keplerops/reset-generation,readonly \
      -e JUPYTER_CONFIG_DIR=/home/jovyan/work/.jupyter \
      -e KEPLEROPS_RANGE_INSTANCE="$RANGE_INSTANCE" \
      -e KEPLEROPS_PARTICIPANT="$PARTICIPANT" \
      -e KEPLEROPS_RESEARCH_INGEST_URL=https://telemetry-proof-01.keplerops.lab:4319 \
      -e SSL_CERT_FILE=/run/tls/ca.crt \
      --entrypoint sh "$RUNTIME_IMAGE" -c 'exec start-notebook.py --ServerApp.ip=0.0.0.0 --ServerApp.port=8888 --ServerApp.certfile=/run/tls/tls.crt --ServerApp.keyfile=/run/tls/tls.key --IdentityProvider.token=$(cat /run/keplerops/jupyter-token)'
    ;;
  telemetry-proof-01)
    fetch_secret service-token /var/lib/keplerops/secrets/service-token
    fetch_secret receipt-signing-key /var/lib/keplerops/secrets/signing-key
    fetch_secret research-pseudonym-key /var/lib/keplerops/secrets/research-pseudonym-key
    fetch_secret research-content-key /var/lib/keplerops/secrets/research-content-key
    install -d -m 0700 /var/lib/keplerops/research
    chown "$RUNTIME_UID:$RUNTIME_UID" /var/lib/keplerops/research
    install -d -m 0700 /var/lib/keplerops/secrets/producer-tokens
    chown "$RUNTIME_UID:$RUNTIME_UID" /var/lib/keplerops/secrets/producer-tokens
    for producer in $EVIDENCE_PRODUCERS; do
      fetch_secret "producer-token-$producer" "/var/lib/keplerops/secrets/producer-tokens/$producer"
    done
    write_runtime_config proof
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only -p 443:8443 -p 4318:4318 -p 4319:4319 \
      --tmpfs /tmp:rw,noexec,nosuid,size=64m "${runtime_mounts[@]}" \
      --mount type=bind,src=/var/lib/keplerops/secrets/service-token,dst=/run/keplerops/service-token,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/signing-key,dst=/run/keplerops/signing-key,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/research-pseudonym-key,dst=/run/keplerops/research-pseudonym-key,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/research-content-key,dst=/run/keplerops/research-content-key,readonly \
      --mount type=bind,src=/var/lib/keplerops/research,dst=/var/lib/keplerops-research \
      --mount type=bind,src=/var/lib/keplerops/secrets/producer-tokens,dst=/run/keplerops/producer-tokens,readonly \
      -e SSL_CERT_FILE=/run/tls/ca.crt "$RUNTIME_IMAGE" # opentelemetry-proof-store
    ;;
  range-ops-controller)
    fetch_secret service-token /var/lib/keplerops/secrets/service-token
    fetch_secret jupyter-token /var/lib/keplerops/secrets/jupyter-token
    fetch_secret platform-deployment-token /var/lib/keplerops/secrets/platform-deployment-token
    fetch_secret gitea-registry-credential /var/lib/keplerops/secrets/gitea-registry-token
    fetch_secret reputation-signing-key /var/lib/keplerops/secrets/reputation-signing-key
    install -d -m 0700 -o 65532 -g 65532 /var/lib/keplerops/data/platform-deployment
    docker_run --rm --read-only --network none \
      --mount type=bind,src=/var/lib/keplerops/data/platform-deployment,dst=/output \
      -e PLATFORM_DEPLOYMENT_POLICY_OUTPUT_ROOT=/output \
      "$AUX_KEPLEROPS_PLATFORM_DEPLOYMENT_IMAGE" render-policy \
      --range-instance "$RANGE_INSTANCE" \
      --participant "$PARTICIPANT" \
      --project-id "$PROJECT_ID" \
      --region "$REGION" \
      --service-account "$RANGE_OPS_SERVICE_ACCOUNT" \
      --export-bucket "$WORKSPACE_BUCKET_NAME" \
      --platform-deployment-image "$PLATFORM_DEPLOYMENT_IMAGE" \
      --output /output/deployment-policy.json
    install -d -m 0755 /etc/docker/certs.d/repo-ticket-01.keplerops.lab
    install -m 0644 /var/lib/keplerops/tls/ca.crt \
      /etc/docker/certs.d/repo-ticket-01.keplerops.lab/ca.crt
    readonly WORKHUB_REGISTRY_PROXY_IP=127.77.0.11
    sed -i \
      '/[[:space:]]repo-ticket-01\.keplerops\.lab\([[:space:]]\|$\)/d' \
      /etc/hosts
    printf '%s repo-ticket-01.keplerops.lab repo-ticket-01\n' \
      "$WORKHUB_REGISTRY_PROXY_IP" >>/etc/hosts
    cat >/var/lib/keplerops/workhub-registry-proxy.py <<'PY'
import asyncio


async def copy_stream(reader, writer):
    try:
        while data := await reader.read(64 * 1024):
            writer.write(data)
            await writer.drain()
    finally:
        try:
            writer.write_eof()
        except (AttributeError, OSError):
            pass


async def relay(local_reader, local_writer):
    try:
        remote_reader, remote_writer = await asyncio.open_connection(
            "repo-ticket-01.keplerops.lab", 443
        )
    except OSError:
        local_writer.close()
        await local_writer.wait_closed()
        return
    try:
        await asyncio.gather(
            copy_stream(local_reader, remote_writer),
            copy_stream(remote_reader, local_writer),
        )
    finally:
        remote_writer.close()
        local_writer.close()
        await asyncio.gather(
            remote_writer.wait_closed(),
            local_writer.wait_closed(),
            return_exceptions=True,
        )


async def main():
    server = await asyncio.start_server(relay, "0.0.0.0", 9443)
    async with server:
        await server.serve_forever()


asyncio.run(main())
PY
    chmod 0444 /var/lib/keplerops/workhub-registry-proxy.py
    command docker run -d --name "${CONTAINER_PREFIX}-workhub-registry-proxy" \
      --restart unless-stopped --read-only --network enterprise-services \
      -p 127.0.0.1:9443:9443 \
      --security-opt no-new-privileges --cap-drop ALL \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m \
      --mount type=bind,src="$WORKLOAD_ROOT/state/workhub-registry-proxy.py",dst=/opt/keplerops/proxy.py,readonly \
      --entrypoint python3 "$RUNTIME_IMAGE" /opt/keplerops/proxy.py
    iptables -t nat -C OUTPUT -d "$WORKHUB_REGISTRY_PROXY_IP"/32 \
      -p tcp --dport 443 -j REDIRECT --to-ports 9443 2>/dev/null ||
      iptables -t nat -I OUTPUT 1 -d "$WORKHUB_REGISTRY_PROXY_IP"/32 \
        -p tcp --dport 443 -j REDIRECT --to-ports 9443
    for attempt in $(seq 1 60); do
      [[ $(curl --silent --show-error --cacert /var/lib/keplerops/tls/ca.crt \
        --output /dev/null --write-out '%{http_code}' \
        https://repo-ticket-01.keplerops.lab/v2/ || true) == 401 ]] && break
      [[ $attempt -lt 60 ]] || exit 1
      sleep 2
    done
    readonly GITEA_WORKSPACE_IMAGE=repo-ticket-01.keplerops.lab/ml.engineer/keplerops-workspace:clean
    docker tag "$AUX_KEPLEROPS_PLATFORM_DEPLOYMENT_IMAGE" "$GITEA_WORKSPACE_IMAGE"
    for attempt in $(seq 1 360); do
      if docker login --username ml.engineer --password-stdin repo-ticket-01.keplerops.lab \
        </var/lib/keplerops/secrets/gitea-registry-token >/dev/null 2>&1 && \
        docker push "$GITEA_WORKSPACE_IMAGE" >/dev/null; then
        break
      fi
      [[ $attempt -lt 360 ]] || exit 1
      sleep 5
    done
    docker logout repo-ticket-01.keplerops.lab >/dev/null
    deployment_mounts=(
      --mount type=bind,src=/var/lib/keplerops/data/platform-deployment,dst=/var/lib/keplerops-platform-deployment
      --mount type=bind,src=/var/lib/keplerops/data/platform-deployment/deployment-policy.json,dst=/run/keplerops/deployment-policy.json,readonly
      --mount type=bind,src=/var/lib/keplerops/secrets/platform-deployment-token,dst=/run/keplerops/platform-deployment-token,readonly
      --mount type=bind,src=/var/lib/keplerops/secrets/gitea-registry-token,dst=/run/keplerops/gitea-registry-token,readonly
      --mount type=bind,src=/var/lib/keplerops/secrets/reputation-signing-key,dst=/run/keplerops/reputation-signing-key,readonly
      --mount type=bind,src=/var/lib/keplerops/tls/ca.crt,dst=/run/tls/ca.crt,readonly
    )
    write_runtime_config reset
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only -p 443:8443 \
      --add-host run.googleapis.com:199.36.153.4 \
      --add-host storage.googleapis.com:199.36.153.4 \
      --tmpfs /tmp:rw,noexec,nosuid,size=64m "${runtime_mounts[@]}" \
      --mount type=bind,src=/var/lib/keplerops/secrets/service-token,dst=/run/keplerops/service-token,readonly \
      -e SSL_CERT_FILE=/run/tls/ca.crt "$RUNTIME_IMAGE" \
      --ssl-keyfile /run/tls/tls.key --ssl-certfile /run/tls/tls.crt
    install -d -m 0700 -o 65532 -g 65532 /var/lib/keplerops/data/green-activity
    docker_run -d --name keplerops-green-activity --restart unless-stopped --read-only \
      --network enterprise-services --network-alias green-activity \
      --security-opt no-new-privileges --cap-drop ALL \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=32m,uid=65532,gid=65532 \
      --mount type=bind,src=/etc/keplerops/runtime.yaml,dst=/etc/keplerops/runtime.yaml,readonly \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      --mount type=bind,src=/var/lib/keplerops/data/green-activity,dst=/var/lib/keplerops/green-activity \
      --mount type=bind,src=/var/lib/keplerops/secrets/service-token,dst=/run/keplerops/service-token,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/jupyter-token,dst=/run/keplerops/jupyter-token,readonly \
      --mount type=bind,src=/var/lib/keplerops/reset-generation,dst=/run/keplerops/reset-generation,readonly \
      -e SSL_CERT_FILE=/run/tls/combined-ca.crt --entrypoint python3 "$RUNTIME_IMAGE" \
      -m uvicorn green_activity.app:app --host 0.0.0.0 --port 8491 \
      --no-access-log --no-proxy-headers
    docker network connect data-workflows keplerops-green-activity
    docker network connect registry-artifacts keplerops-green-activity
    docker network connect model-serving keplerops-green-activity
    docker_run -d --name keplerops-platform-deployment --restart unless-stopped --read-only \
      --network host --security-opt no-new-privileges --cap-drop ALL \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m,uid=65532,gid=65532 \
      "${deployment_mounts[@]}" "$AUX_KEPLEROPS_PLATFORM_DEPLOYMENT_IMAGE" api
    docker_run -d --name keplerops-platform-deployment-lifecycle --restart unless-stopped --read-only \
      --network host --security-opt no-new-privileges --cap-drop ALL \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m,uid=65532,gid=65532 \
      "${deployment_mounts[@]}" "$AUX_KEPLEROPS_PLATFORM_DEPLOYMENT_IMAGE" lifecycle-worker
    ;;
  research-index-01)
    sysctl -w vm.max_map_count=262144 >/dev/null
    docker_run -d --name keplerops-runtime --restart unless-stopped --network host \
      --ulimit nofile=65536:65536 \
      --mount type=bind,src=/var/lib/keplerops/data,dst=/usr/share/opensearch/data \
      -e discovery.type=single-node \
      -e DISABLE_INSTALL_DEMO_CONFIG=true \
      -e DISABLE_SECURITY_PLUGIN=true \
      -e OPENSEARCH_JAVA_OPTS='-Xms1g -Xmx1g' \
      "$RUNTIME_IMAGE"
    for attempt in $(seq 1 60); do
      if workload_netns curl --fail --silent \
        http://127.0.0.1:9200/_cluster/health >/dev/null; then
        docker exec keplerops-runtime /opt/keplerops/seed.sh
        break
      fi
      [[ $attempt -lt 60 ]] || exit 1
      sleep 5
    done
    ;;
  range-dns-01)
    install -d -m 0755 /var/lib/keplerops/data/zones
    cat >/var/lib/keplerops/data/zones/db.keplerops.lab <<'ZONE_HEADER'
$ORIGIN keplerops.lab.
$TTL 300
@ 300 IN SOA range-dns-01.keplerops.lab. hostmaster.keplerops.lab. (
  1 300 60 86400 300
)
@ 300 IN NS range-dns-01.keplerops.lab.
ZONE_HEADER
    declare -A zone_names=()
    while read -r peer_ip peer_name _aliases; do
      peer_name=${peer_name%.keplerops.lab}
      [[ ${zone_names[$peer_name]+present} ]] && continue
      zone_names[$peer_name]=present
      printf '%s 300 IN A %s\n' "$peer_name" "$peer_ip" >>/var/lib/keplerops/data/zones/db.keplerops.lab
    done <"$HOST_ENTRIES_FILE"
    cat >>/var/lib/keplerops/data/zones/db.keplerops.lab <<'ZONE_SERVICES'
_opensearch._tcp 300 IN SRV 0 0 9200 research-index-01.keplerops.lab.
_http._tcp 300 IN SRV 0 0 8080 public-sites-01.keplerops.lab.
ZONE_SERVICES
    chmod 0444 /var/lib/keplerops/data/zones/db.keplerops.lab
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only \
      -p "$ASSET_IP:53:53/tcp" -p "$ASSET_IP:53:53/udp" \
      -p 8080:8080 -p 8181:8181 -p 9153:9153 \
      --mount type=bind,src=/var/lib/keplerops/data/zones,dst=/var/lib/keplerops/zones,readonly \
      "$RUNTIME_IMAGE"
    ;;
  public-sites-01)
    docker_run -d --name keplerops-runtime --restart unless-stopped --network host --read-only \
      --tmpfs /tmp:rw,noexec,nosuid,size=16m \
      --tmpfs /var/cache/nginx:rw,noexec,nosuid,size=32m \
      "$RUNTIME_IMAGE" nginx -g 'daemon off;' -c /opt/keplerops/public-web/nginx.conf
    ;;
  scan-services-01)
    docker_run -d --name keplerops-runtime --restart unless-stopped --network host --read-only \
      --tmpfs /tmp:rw,noexec,nosuid,size=16m \
      --tmpfs /var/cache/nginx:rw,noexec,nosuid,size=32m \
      "$RUNTIME_IMAGE" nginx -g 'daemon off;' -c /opt/keplerops/scan-targets/nginx.conf
    ;;
  platform-impact-01)
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only -p 8460:8460 \
      --tmpfs /tmp:rw,noexec,nosuid,size=128m \
      --mount type=bind,src=/var/lib/keplerops/data,dst=/var/lib/keplerops-platform-impact \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/producer-token,dst=/run/keplerops/producer-token,readonly \
      -e PLATFORM_IMPACT_ADMIN_TOKEN=platform-impact-admin-synthetic \
      -e KEPLEROPS_RANGE_INSTANCE="$RANGE_INSTANCE" \
      -e KEPLEROPS_PARTICIPANT="$PARTICIPANT" \
      -e KEPLEROPS_RESET_GENERATION="$RESET_GENERATION" \
      "$RUNTIME_IMAGE"
    ;;
  platform-ml-01)
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only -p 8470:8470 \
      --tmpfs /tmp:rw,noexec,nosuid,size=128m \
      --mount type=bind,src=/var/lib/keplerops/data,dst=/var/lib/keplerops-platform-ml \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/run/tls,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/producer-token,dst=/run/keplerops/producer-token,readonly \
      -e PLATFORM_ML_ADMIN_TOKEN=keplerops-platform-ml-operator \
      -e KEPLEROPS_RANGE_INSTANCE="$RANGE_INSTANCE" \
      -e KEPLEROPS_PARTICIPANT="$PARTICIPANT" \
      -e KEPLEROPS_RESET_GENERATION="$RESET_GENERATION" \
      "$RUNTIME_IMAGE"
    ;;
  mail-server-01)
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only \
      -p 25:25 -p 587:587 -p 993:993 -p 8080:8080 \
      --tmpfs /tmp:rw,noexec,nosuid,size=64m \
      --mount type=bind,src=/var/lib/keplerops/data,dst=/var/lib/stalwart \
      --mount type=bind,src=/var/lib/keplerops/tls/ca.crt,dst=/etc/keplerops/pki/ca.crt,readonly \
      --mount type=bind,src=/var/lib/keplerops/tls/tls.crt,dst=/etc/keplerops/pki/mail.crt,readonly \
      --mount type=bind,src=/var/lib/keplerops/tls/tls.key,dst=/etc/keplerops/pki/mail.key,readonly \
      "$RUNTIME_IMAGE"
    ;;
  webmail-01)
    docker_run -d --name keplerops-runtime --restart unless-stopped -p 8000:8000 \
      --tmpfs /tmp:rw,noexec,nosuid,size=128m,uid=33,gid=33 \
      --tmpfs /tmp/roundcube-temp:rw,noexec,nosuid,size=64m,uid=33,gid=33 \
      --mount type=bind,src=/var/lib/keplerops/data,dst=/var/roundcube/db \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/etc/keplerops/pki,readonly \
      "$RUNTIME_IMAGE"
    ;;
  text-generation-01)
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only -p 8080:8080 \
      --tmpfs /tmp:rw,noexec,nosuid,size=128m \
      "$RUNTIME_IMAGE"
    ;;
  image-generation-01)
    fetch_secret postgres-password /var/lib/keplerops/secrets/postgres-password
    fetch_secret minio-root-user /var/lib/keplerops/secrets/minio-root-user
    fetch_secret minio-root-password /var/lib/keplerops/secrets/minio-root-password
    readonly IMAGE_POSTGRES_DSN="postgresql://keplerops:$(</var/lib/keplerops/secrets/postgres-password)@dataset-store-01.keplerops.lab:5432/keplerops?sslmode=verify-full&sslrootcert=/etc/keplerops/pki/ca.crt"
    docker_run -d --name keplerops-runtime --restart unless-stopped --read-only -p 8092:8092 \
      --tmpfs /tmp:rw,noexec,nosuid,size=512m \
      --mount type=bind,src=/var/lib/keplerops/tls,dst=/etc/keplerops/pki,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/postgres-password,dst=/run/keplerops/postgres-password,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/minio-root-user,dst=/run/keplerops/minio-root-user,readonly \
      --mount type=bind,src=/var/lib/keplerops/secrets/minio-root-password,dst=/run/keplerops/minio-root-password,readonly \
      -e IMAGE_POSTGRES_DSN="$IMAGE_POSTGRES_DSN" \
      -e MINIO_ENDPOINT=artifact-store-01.keplerops.lab:9000 \
      -e MINIO_SECURE=true \
      -e MINIO_CA_FILE=/etc/keplerops/pki/ca.crt \
      -e MINIO_ACCESS_KEY="$(</var/lib/keplerops/secrets/minio-root-user)" \
      -e MINIO_SECRET_KEY="$(</var/lib/keplerops/secrets/minio-root-password)" \
      -e MINIO_IMAGE_BUCKET=keplerops-generated-images \
      -e RESET_GENERATION="$RESET_GENERATION" \
      "$RUNTIME_IMAGE"
    ;;
  *) echo 'unsupported asset binding' >&2; exit 2 ;;
esac

cat >/var/lib/keplerops/health-local <<'HEALTH'
#!/bin/bash
set -euo pipefail
: "${ASSET_ID:?}"
. /etc/keplerops/docker-wrapper.sh
docker inspect --format '{{.State.Running}}' keplerops-runtime | grep -qx true
case "$ASSET_ID" in
  participant-workstation) curl --fail --silent --show-error --insecure \
    --user "kasm_user:$(cat /var/lib/keplerops/secrets/participant-password)" \
    https://127.0.0.1:6901/ >/dev/null ;;
  lab-portal|guardrail-policy|telemetry-proof-01) curl --fail --silent --show-error --insecure https://127.0.0.1:8443/healthz >/dev/null ;;
  range-ops-controller)
    curl --fail --silent --show-error --insecure https://127.0.0.1:8443/healthz >/dev/null
    curl --fail --silent --show-error http://127.0.0.1:8490/readyz >/dev/null
    docker inspect --format '{{.State.Health.Status}}' keplerops-platform-deployment | grep -qx healthy
    docker inspect --format '{{.State.Health.Status}}' keplerops-platform-deployment-lifecycle | grep -qx healthy
    docker inspect --format '{{.State.Running}}' keplerops-workhub-registry-proxy | grep -qx true
    docker exec keplerops-green-activity python3 -c \
      "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8491/readyz', timeout=2).read()" >/dev/null
    ;;
  inference-gateway)
    curl --fail --silent --show-error --insecure -H 'Host: inference-gateway.keplerops.lab' https://127.0.0.1:8444/healthz >/dev/null
    for worker in keplerops-package-resolver keplerops-package-analysis keplerops-package-worker; do
      docker inspect --format '{{.State.Running}}' "$worker" | grep -qx true
      case "$worker" in
        keplerops-package-resolver) worker_port=8452 ;;
        keplerops-package-analysis) worker_port=8453 ;;
        keplerops-package-worker) worker_port=8454 ;;
      esac
      docker exec "$worker" python -c "import json,urllib.request; response=json.load(urllib.request.urlopen('http://127.0.0.1:$worker_port/healthz', timeout=2)); raise SystemExit(response.get('status') != 'ok')"
    done
    ;;
  idp-01) curl --fail --silent --show-error --insecure https://127.0.0.1:8443/realms/keplerops/.well-known/openid-configuration >/dev/null ;;
  repo-ticket-01)
    curl --fail --silent --show-error --insecure -H 'Host: workhub.keplerops.lab' https://127.0.0.1:8443/git/ >/dev/null
    curl --fail --silent --show-error http://127.0.0.1:8480/readyz >/dev/null
    for worker in keplerops-context-file-worker keplerops-context-sync-worker; do
      docker inspect --format '{{.State.Health.Status}}' "$worker" | grep -qx healthy
    done
    ;;
  model-registry-01) curl --fail --silent --show-error http://127.0.0.1:5000/health >/dev/null ;;
  artifact-store-01|exfil-sink) curl --fail --silent --show-error --insecure https://127.0.0.1:9000/minio/health/live >/dev/null ;;
  dataset-store-01) docker exec keplerops-runtime pg_isready --quiet ;;
  distillation-runner-01) curl --fail --silent --show-error http://127.0.0.1:8080/api/v2/monitor/health >/dev/null ;;
  notebook-runner-01) curl --fail --silent --show-error --insecure \
    -H "Authorization: token $(cat /var/lib/keplerops/secrets/jupyter-token)" \
    https://127.0.0.1:8888/api/status >/dev/null ;;
  research-index-01) curl --fail --silent --show-error http://127.0.0.1:9200/_cluster/health >/dev/null ;;
  range-dns-01)
    curl --fail --silent --show-error http://127.0.0.1:8080/health | grep -qx OK
    curl --fail --silent --show-error http://127.0.0.1:8181/ready | grep -qx OK
    ;;
  public-sites-01) curl --fail --silent --show-error http://127.0.0.1:8080/healthz | grep -qx ok ;;
  scan-services-01)
    curl --fail --silent --show-error http://127.0.0.1:18080/healthz | grep -qx ok
    curl --fail --silent --show-error http://127.0.0.1:18081/healthz | grep -qx ok
    ;;
  platform-impact-01) curl --fail --silent --show-error http://127.0.0.1:8460/readyz >/dev/null ;;
  platform-ml-01) curl --fail --silent --show-error http://127.0.0.1:8470/readyz >/dev/null ;;
  mail-server-01) curl --fail --silent --show-error http://127.0.0.1:8080/healthz/live >/dev/null ;;
  webmail-01)
    curl --fail --silent --show-error http://127.0.0.1:8000/ >/dev/null
    if [[ ! -s /var/lib/keplerops/data/.mail-flow-ready ]]; then
      docker_run --rm --name keplerops-mail-readiness \
        --user 33:33 \
        --mount type=bind,src=/var/lib/keplerops/tls,dst=/etc/keplerops/pki,readonly \
        -e MAIL_HOST=mail-server-01.keplerops.lab \
        -e WEBMAIL_URL=http://127.0.0.1:8000/ \
        "$MAIL_PROTOCOL_READINESS_IMAGE" >/var/lib/keplerops/data/.mail-flow-ready
      chown 33:33 /var/lib/keplerops/data/.mail-flow-ready
      chmod 0600 /var/lib/keplerops/data/.mail-flow-ready
    fi
    ;;
  text-generation-01) curl --fail --silent --show-error http://127.0.0.1:8080/health >/dev/null ;;
  image-generation-01) curl --fail --silent --show-error http://127.0.0.1:8092/healthz/ready >/dev/null ;;
  platform-camera-01)
    docker inspect --format '{{.State.Health.Status}}' keplerops-runtime | grep -qx healthy
    ;;
  platform-agent-01)
    curl --fail --silent --show-error http://127.0.0.1:8470/readyz >/dev/null
    curl --fail --silent --show-error \
      -H "X-Isolation-Admin-Token: $(cat /var/lib/keplerops/secrets/platform-isolation-admin-token)" \
      http://127.0.0.1:8480/readyz >/dev/null
    curl --fail --silent --show-error \
      -H "X-Edge-Registry-Token: $(cat /var/lib/keplerops/secrets/edge-registry-admin-token)" \
      http://127.0.0.1:8481/readyz >/dev/null
    docker inspect --format '{{.State.Health.Status}}' keplerops-bounded-worker-engine | grep -qx healthy
    docker inspect --format '{{len .NetworkSettings.Networks}}' keplerops-bounded-worker-engine | grep -qx 0
    [[ -f /var/lib/keplerops/run-bounded-client ]]
    [[ $(stat -c '%a' /var/lib/keplerops/run-bounded-client) == 700 ]]
    bash -n /var/lib/keplerops/run-bounded-client
    ;;
  policy-lab-01) curl --fail --silent --show-error http://127.0.0.1:8182/health >/dev/null ;;
  *) exit 2 ;;
esac
HEALTH
chmod 0700 /var/lib/keplerops/health-local

cat >/var/lib/keplerops/quiesce-local <<'QUIESCE'
#!/bin/bash
set -euo pipefail
: "${ASSET_ID:?}"
. /etc/keplerops/docker-wrapper.sh
umask 077
printf 'resetting\n' >/var/lib/keplerops/runtime-state
RUNTIME_UID=$(</var/lib/keplerops/runtime-uid)
chown "$RUNTIME_UID:$RUNTIME_UID" /var/lib/keplerops/runtime-state
chmod 0600 /var/lib/keplerops/runtime-state
case "$ASSET_ID" in
  platform-agent-01)
    curl --fail --silent --show-error -X POST \
      -H "X-Platform-Admin-Token: $(cat /var/lib/keplerops/secrets/platform-agent-admin-token)" \
      http://127.0.0.1:8470/v1/admin/reset >/dev/null
    curl --fail --silent --show-error -X POST \
      -H "X-Isolation-Admin-Token: $(cat /var/lib/keplerops/secrets/platform-isolation-admin-token)" \
      http://127.0.0.1:8480/v1/admin/reset >/dev/null
    curl --fail --silent --show-error -X POST \
      -H "X-Edge-Registry-Token: $(cat /var/lib/keplerops/secrets/edge-registry-admin-token)" \
      http://127.0.0.1:8481/v1/admin/reset >/dev/null
    docker stop keplerops-runtime keplerops-isolation-loader keplerops-edge-registry >/dev/null
    docker stop keplerops-bounded-worker-engine >/dev/null
    ;;
  range-ops-controller)
    docker exec keplerops-green-activity python3 -c \
      "import pathlib,urllib.request; token=pathlib.Path('/run/keplerops/service-token').read_text().strip(); request=urllib.request.Request('http://127.0.0.1:8491/v1/control', data=b'{\"action\":\"drain\"}', headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}, method='POST'); urllib.request.urlopen(request, timeout=5).read()" >/dev/null
    curl --fail --silent --show-error -X POST \
      -H "Authorization: Bearer $(cat /var/lib/keplerops/secrets/platform-deployment-token)" \
      http://127.0.0.1:8490/v1/admin/reset >/dev/null
    docker stop keplerops-green-activity keplerops-platform-deployment-lifecycle \
      keplerops-platform-deployment keplerops-workhub-registry-proxy \
      keplerops-runtime >/dev/null
    ;;
  image-generation-01)
    curl --fail --silent --show-error -X POST \
      -H 'Content-Type: application/json' \
      --data "{\"reset_generation\":$(</var/lib/keplerops/reset-generation)}" \
      http://127.0.0.1:8092/internal/reset >/dev/null
    docker stop keplerops-runtime >/dev/null
    ;;
  *)
    docker stop keplerops-runtime keplerops-package-resolver keplerops-package-analysis \
      keplerops-package-worker keplerops-context-api keplerops-context-file-worker \
      keplerops-context-sync-worker >/dev/null 2>&1 || true
    ;;
esac
touch /var/lib/keplerops/quiesced
chmod 0600 /var/lib/keplerops/quiesced
QUIESCE
chmod 0700 /var/lib/keplerops/quiesce-local

cat >/var/lib/keplerops/reset-local <<'RESET'
#!/bin/bash
set -euo pipefail
: "${ASSET_ID:?}"
. /etc/keplerops/docker-wrapper.sh
[[ ${1-} =~ ^[0-9]+$ ]] || exit 2
umask 077
printf 'resetting\n' >/var/lib/keplerops/runtime-state
case "$ASSET_ID" in
  platform-agent-01|range-ops-controller|image-generation-01) [[ -f /var/lib/keplerops/quiesced ]] || exit 1 ;;
esac
docker rm -f keplerops-runtime keplerops-package-resolver keplerops-package-analysis \
  keplerops-package-worker keplerops-context-api keplerops-context-file-worker \
  keplerops-context-sync-worker keplerops-isolation-loader keplerops-edge-registry \
  keplerops-bounded-worker-engine keplerops-platform-deployment \
  keplerops-platform-deployment-lifecycle keplerops-green-activity \
  keplerops-workhub-registry-proxy >/dev/null 2>&1 || true
case "$ASSET_ID" in
  platform-agent-01) rm -rf /run/keplerops-bounded-worker ;;
esac
rm -rf /var/lib/keplerops/data
install -d -m 0700 /var/lib/keplerops/data
RUNTIME_UID=$(</var/lib/keplerops/runtime-uid)
[[ $RUNTIME_UID =~ ^[0-9]+$ ]] || exit 2
chown "$RUNTIME_UID:$RUNTIME_UID" /var/lib/keplerops/data
printf '%s\n' "$1" >/var/lib/keplerops/reset-generation
chown "$RUNTIME_UID:$RUNTIME_UID" /var/lib/keplerops/runtime-state /var/lib/keplerops/reset-generation
chmod 0600 /var/lib/keplerops/runtime-state /var/lib/keplerops/reset-generation
exec bash /var/lib/keplerops/bootstrap
RESET
chmod 0700 /var/lib/keplerops/reset-local

cat >/var/lib/keplerops/reset-verify-local <<'VERIFY'
#!/bin/bash
set -euo pipefail
: "${ASSET_ID:?}"
. /etc/keplerops/docker-wrapper.sh
[[ $(</var/lib/keplerops/runtime-state) == ready ]]
bash /var/lib/keplerops/health-local
case "$ASSET_ID" in
  telemetry-proof-01)
    docker exec keplerops-runtime python -c 'import sqlite3; c=sqlite3.connect("/var/lib/keplerops/proof.sqlite3"); tables=c.execute("SELECT count(*) FROM sqlite_master WHERE type=\"table\" AND name=\"evidence\"").fetchone()[0]; rows=c.execute("SELECT count(*) FROM evidence").fetchone()[0] if tables else 0; raise SystemExit(rows != 0)'
    ;;
  model-registry-01)
    docker exec keplerops-runtime python -c 'import sqlite3; c=sqlite3.connect("/data/mlflow.db"); experiments=c.execute("SELECT count(*) FROM experiments WHERE name IN (?, ?, ?)", ("keplerops-training-poisoning", "keplerops-model-extraction", "keplerops-model-dependencies")).fetchone()[0]; models=c.execute("SELECT count(*) FROM registered_models WHERE name LIKE ? OR name LIKE ?", ("keplerops-backdoor-%", "keplerops-policy-model-%")).fetchone()[0]; raise SystemExit(experiments + models != 0)'
    ;;
  artifact-store-01)
    ! find /var/lib/keplerops/data -type f \( -name adapter.json -o -name proxy.json -o -name policy-model.json \) -print -quit | grep -q .
    ;;
  dataset-store-01)
    docker exec keplerops-runtime psql -U keplerops -d keplerops -tAc 'SELECT (SELECT count(*) FROM retrieval_context WHERE range_instance <> $$baseline$$ OR participant <> $$baseline$$) + (SELECT count(*) FROM context_controls) + (SELECT count(*) FROM agent_context_documents) + (SELECT count(*) FROM agent_attempts) + (SELECT count(*) FROM agent_tool_effects) + (SELECT count(*) FROM agent_memories) + (SELECT count(*) FROM agent_memory_uses) + (SELECT count(*) FROM agent_runtime_restarts) + CASE WHEN (SELECT count(*) FROM agent_runtime_boots) >= 1 THEN 0 ELSE 1 END + (SELECT count(*) FROM model_secret_queries) + (SELECT count(*) FROM model_secret_attempts) + (SELECT count(*) FROM adversarial_artifacts) + (SELECT count(*) FROM adversarial_probes) + (SELECT count(*) FROM adversarial_attempts) + (SELECT count(*) FROM training_datasets) + (SELECT count(*) FROM training_rows) + (SELECT count(*) FROM training_jobs) + (SELECT count(*) FROM training_attempts) + (SELECT count(*) FROM extraction_corpora) + (SELECT count(*) FROM extraction_queries) + (SELECT count(*) FROM extraction_jobs) + (SELECT count(*) FROM extraction_attempts) + (SELECT count(*) FROM backdoor_candidates) + (SELECT count(*) FROM backdoor_evaluations) + (SELECT count(*) FROM backdoor_approvals) + (SELECT count(*) FROM backdoor_promotions) + (SELECT count(*) FROM backdoor_deployments) + (SELECT count(*) FROM backdoor_attempts) + (SELECT count(*) FROM capstone_activations) + (SELECT count(*) FROM capstone_effects) + (SELECT count(*) FROM capstone_artifact_access) + (SELECT count(*) FROM capstone_attempts) + (SELECT count(*) FROM platform_challenge_events) + (SELECT count(*) FROM data_dependencies) + (SELECT count(*) FROM data_dependency_jobs) + (SELECT count(*) FROM model_dependencies) + (SELECT count(*) FROM web_deliveries) + (SELECT count(*) FROM supply_attempts) + (SELECT count(*) FROM runtime_dependencies) + (SELECT count(*) FROM sandbox_evaluations) + (SELECT count(*) FROM runtime_supply_attempts) + (SELECT count(*) FROM spearphish_campaigns) + (SELECT count(*) FROM spearphish_attempts) + (SELECT count(*) FROM retrieval_documents WHERE provenance IN ($$participant$$, $$model$$)) + (SELECT count(*) FROM retrieval_index_revisions) + (SELECT count(*) FROM retrieval_sessions) + (SELECT count(*) FROM retrieval_attempts) + abs((SELECT count(*) FROM agent_tool_objects) - 2) + abs((SELECT count(*) FROM retrieval_documents WHERE provenance = $$trusted$$) - 3) + CASE WHEN (SELECT count(*) FROM retrieval_chunks c JOIN retrieval_documents d ON d.id = c.document_id WHERE d.provenance = $$trusted$$ AND c.revision = d.current_revision) >= 3 THEN 0 ELSE 1 END + CASE WHEN (SELECT extversion FROM pg_extension WHERE extname = $$vector$$) = $$0.8.2$$ THEN 0 ELSE 1 END' | grep -qx 0
    ;;
  distillation-runner-01)
    docker exec keplerops-runtime python -c 'import sqlite3; c=sqlite3.connect("/var/lib/airflow/airflow.db"); rows=c.execute("SELECT count(*) FROM dag_run WHERE dag_id = ? AND (run_id LIKE ? OR run_id LIKE ? OR instr(CAST(conf AS TEXT), ?) > 0)", ("keplerops_distillation", "m07-%", "m08-%", "data_dependency_job_id")).fetchone()[0]; raise SystemExit(rows != 0)'
    ;;
esac
VERIFY
chmod 0700 /var/lib/keplerops/reset-verify-local

printf 'ready\n' >/var/lib/keplerops/runtime-state
chown "$RUNTIME_UID:$RUNTIME_UID" /var/lib/keplerops/runtime-state
chmod 0600 /var/lib/keplerops/runtime-state
for attempt in $(seq 1 30); do
  if workload_netns bash /var/lib/keplerops/health-local; then
    exit 0
  fi
  sleep 10
done
printf 'resetting\n' >/var/lib/keplerops/runtime-state
chown "$RUNTIME_UID:$RUNTIME_UID" /var/lib/keplerops/runtime-state
exit 1
