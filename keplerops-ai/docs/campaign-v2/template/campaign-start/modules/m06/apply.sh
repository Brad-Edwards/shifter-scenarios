#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-all}"
readonly FORGEJO_URL="${CINDER_FORGEJO_URL:-http://10.61.90.30:3000}"
readonly FORGEJO_API="${FORGEJO_URL}/api/v1"
readonly OPERATOR_AUTH="cinder-operator:Cinder-Operations-Git-K3m7Pq4x"
readonly EVALUATOR_USER="cinder-evaluation"
readonly EVALUATOR_PASSWORD="Cinder-Evaluation-Service-J9r4Wm7p"
readonly EVALUATOR_AUTH="${EVALUATOR_USER}:${EVALUATOR_PASSWORD}"
readonly EVALUATOR_REPOSITORY="capability-evaluators"
readonly RUNNER_SECRET="8a3df25e9b80e042d1108cad37d21779c269add7"
readonly PUBLIC_FORGEJO_URL="${PUBLIC_FORGEJO_URL:-http://10.61.40.20:3000}"
readonly PUBLIC_FORGEJO_API="${PUBLIC_FORGEJO_URL}/api/v1"
readonly PUBLIC_FORGEJO_AUTH="orion.release:KeplerV2-Orion-Publication-8mT4qN2v"
readonly PUBLIC_SOURCE_REPOSITORY="keplerops/orion-public"
readonly PUBLIC_BUILD_REPOSITORY="keplerops/orion-build"
readonly PUBLIC_RELEASE_WORKFLOW="orion-public-release.yml"
readonly PUBLIC_RELEASE_TAG="v1.0.0"
readonly HARBOR_API="${HARBOR_API_URL:-http://10.61.40.32:8080/api/v2.0}"
readonly HARBOR_ADMIN_AUTH="admin:KeplerV2-Training-Harbor"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"

log() { printf '[campaign-m06] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }
require() { command -v "$1" >/dev/null 2>&1 || die "required command unavailable: $1"; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.cinder.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

forgejo() {
  local auth=$1 method=$2 path=$3
  shift 3
  curl -fsS --user "$auth" -H 'Content-Type: application/json' \
    --request "$method" "$@" "${FORGEJO_API}${path}"
}

public_forgejo() {
  local method=$1 path=$2
  shift 2
  curl --silent --show-error --fail-with-body \
    --user "$PUBLIC_FORGEJO_AUTH" -H 'Content-Type: application/json' \
    --request "$method" "$@" "${PUBLIC_FORGEJO_API}${path}"
}

ensure_public_source_file() {
  local path=$1 source=$2 current payload content
  content="$(base64 -w0 "$source")"
  if current="$(public_forgejo GET "/repos/${PUBLIC_SOURCE_REPOSITORY}/contents/${path}" 2>/dev/null)"; then
    if [[ $(jq -r '.content | gsub("\\n"; "")' <<<"$current") == "$content" ]]; then
      return 1
    fi
    payload="$(jq -cn --arg content "$content" --arg sha "$(jq -r .sha <<<"$current")" \
      --arg message "Reconcile ${path}" '{content:$content,sha:$sha,message:$message}')"
    public_forgejo PUT "/repos/${PUBLIC_SOURCE_REPOSITORY}/contents/${path}" --data "$payload" >/dev/null
  else
    payload="$(jq -cn --arg content "$content" --arg message "Add ${path}" \
      '{content:$content,message:$message}')"
    public_forgejo POST "/repos/${PUBLIC_SOURCE_REPOSITORY}/contents/${path}" --data "$payload" >/dev/null
  fi
  return 0
}

latest_release_run() {
  local build_revision=$1
  public_forgejo GET "/repos/${PUBLIC_BUILD_REPOSITORY}/actions/tasks?limit=50" | jq -c \
    --arg workflow "$PUBLIC_RELEASE_WORKFLOW" --arg revision "$build_revision" '
      [.workflow_runs[] | select(.workflow_id == $workflow and .head_sha == $revision)]
      | max_by(.id) // empty
    '
}

rebuild_public_client_release() {
  local build_revision prior_run prior_id run status release release_id
  build_revision="$(public_forgejo GET "/repos/${PUBLIC_BUILD_REPOSITORY}/branches/main" | jq -er '.commit.id')"
  prior_run="$(latest_release_run "$build_revision")"
  prior_id="$(jq -r '.id // 0' <<<"${prior_run:-{}}")"

  release="$(public_forgejo GET "/repos/${PUBLIC_SOURCE_REPOSITORY}/releases/tags/${PUBLIC_RELEASE_TAG}" 2>/dev/null || true)"
  if jq -e 'type == "object" and has("id")' <<<"$release" >/dev/null 2>&1; then
    release_id="$(jq -er .id <<<"$release")"
    public_forgejo DELETE "/repos/${PUBLIC_SOURCE_REPOSITORY}/releases/${release_id}" >/dev/null
  fi
  public_forgejo DELETE "/repos/${PUBLIC_SOURCE_REPOSITORY}/tags/${PUBLIC_RELEASE_TAG}" >/dev/null 2>&1 || true
  public_forgejo POST "/repos/${PUBLIC_BUILD_REPOSITORY}/actions/workflows/${PUBLIC_RELEASE_WORKFLOW}/dispatches" \
    --data '{"ref":"main","inputs":{}}' >/dev/null

  run=''
  for _ in $(seq 1 240); do
    sleep 5
    run="$(latest_release_run "$build_revision")"
    [[ -n $run ]] || continue
    (( $(jq -er .id <<<"$run") > prior_id )) || continue
    status="$(jq -er .status <<<"$run")"
    [[ $status == success ]] && break
    [[ $status =~ ^(failure|cancelled|skipped)$ ]] && die "Orion client release workflow ended with ${status}"
  done
  [[ -n $run ]] && [[ $(jq -r .status <<<"$run") == success ]] || \
    die 'Orion client release workflow did not complete successfully'
}

download_public_release_asset() {
  local release=$1 name=$2 destination=$3 url
  url="$(jq -er --arg name "$name" '.assets[] | select(.name == $name) | .browser_download_url' <<<"$release")"
  curl -fsS --user "$PUBLIC_FORGEJO_AUTH" "$url" -o "$destination"
}

install_real_public_client() {
  local public_root=$1 source_changed=false release source_revision release_revision workdir
  if ensure_public_source_file ci/prepare-client.py \
      "${MODULE_ROOT}/payloads/public/client/prepare-client.py"; then
    source_changed=true
  fi
  source_revision="$(public_forgejo GET "/repos/${PUBLIC_SOURCE_REPOSITORY}/branches/main" | jq -er '.commit.id')"
  release="$(public_forgejo GET "/repos/${PUBLIC_SOURCE_REPOSITORY}/releases/tags/${PUBLIC_RELEASE_TAG}" 2>/dev/null || true)"
  release_revision="$(jq -r '.target_commitish // empty' <<<"${release:-{}}")"
  if [[ $source_changed == true || $release_revision != "$source_revision" ]]; then
    rebuild_public_client_release
    release="$(public_forgejo GET "/repos/${PUBLIC_SOURCE_REPOSITORY}/releases/tags/${PUBLIC_RELEASE_TAG}")"
  fi

  workdir="$(mktemp -d)"
  trap 'rm -rf "$workdir"' RETURN
  download_public_release_asset "$release" orion-mobile-1.0.0.apk "$workdir/client.apk"
  download_public_release_asset "$release" orion-mobile-1.0.0.cdx.json "$workdir/sbom.json"
  download_public_release_asset "$release" release-manifest.json "$workdir/manifest.json"
  unzip -p "$workdir/client.apk" assets/provenance/release.json >"$workdir/provenance.json"
  jq -e --arg revision "$source_revision" '
    .source.revision == $revision and .source.tag == "v1.0.0"
    and .release_reference_prefix == "FLAG{21505f62"
  ' "$workdir/provenance.json" >/dev/null
  jq -e '
    any(.metadata.component.properties[];
      .name == "keplerops:release-reference-suffix" and .value == "f49d176c}")
  ' "$workdir/sbom.json" >/dev/null
  [[ $(sha256sum "$workdir/sbom.json" | cut -d' ' -f1) == \
    "$(jq -er .sbom.sha256 "$workdir/provenance.json")" ]] || die 'APK provenance does not bind the published SBOM'
  install -m 0644 "$workdir/client.apk" "$public_root/software/orion-field-review/orion-field-review.apk"
  install -m 0644 "$workdir/sbom.json" "$public_root/software/orion-field-review/orion-field-review.cdx.json"
  install -m 0644 "$workdir/manifest.json" "$public_root/software/orion-field-review/release-manifest.json"
}

install_public_orion_kit() {
  local public_root=$1
  local candidate="${PLATFORM_STATE_DIR:-/var/lib/keplerops-platform}/current-candidate"
  local kit_root="$public_root/research/orion-kit"
  local name sha role
  [[ -d $candidate/model ]] || die 'current Orion release candidate is unavailable'
  install -d -m 0755 "$kit_root"
  for name in orion-release-risk.onnx model.safetensors tokenizer.json label-map.json preprocessing.json model-card.md release-metadata.json; do
    [[ -s $candidate/model/$name ]] || die "current Orion release candidate lacks ${name}"
    install -m 0644 "$candidate/model/$name" "$kit_root/$name"
  done
  for name in orion-release-risk-public.jsonl orion-agent-blueprint.json run-orion-kit.py; do
    install -m 0644 "${MODULE_ROOT}/payloads/public/bundle/$name" "$kit_root/$name"
  done
  jq -n \
    --arg release orion-release-risk-1.0.0 \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{schema:"https://keplerops.lab/schemas/orion-public-bundle/v1",release:$release,
      generated_at:$generated_at,artifacts:[]}' >"$kit_root/bundle-manifest.json"
  for name in orion-release-risk.onnx model.safetensors tokenizer.json label-map.json preprocessing.json model-card.md release-metadata.json orion-release-risk-public.jsonl orion-agent-blueprint.json run-orion-kit.py; do
    case "$name" in
      orion-release-risk.onnx|model.safetensors|tokenizer.json|label-map.json|preprocessing.json|model-card.md|release-metadata.json) role=model;;
      orion-release-risk-public.jsonl) role=dataset;;
      orion-agent-blueprint.json|run-orion-kit.py) role=agent;;
    esac
    sha="$(sha256sum "$kit_root/$name" | cut -d' ' -f1)"
    jq --arg name "$name" --arg role "$role" --arg sha "$sha" \
      '.artifacts += [{name:$name,role:$role,url:("https://keplerops.lab/research/orion-kit/"+$name),sha256:$sha}]' \
      "$kit_root/bundle-manifest.json" >"$kit_root/.bundle-manifest.json"
    mv "$kit_root/.bundle-manifest.json" "$kit_root/bundle-manifest.json"
  done
}

ensure_forgejo_file() {
  local path=$1 source=$2 message=$3 current payload
  if current="$(forgejo "$EVALUATOR_AUTH" GET "/repos/${EVALUATOR_USER}/${EVALUATOR_REPOSITORY}/contents/${path}" 2>/dev/null)"; then
    payload="$(jq -cn --arg content "$(base64 -w0 "$source")" --arg message "$message" --arg sha "$(jq -r .sha <<<"$current")" '{content:$content,message:$message,sha:$sha}')"
    forgejo "$EVALUATOR_AUTH" PUT "/repos/${EVALUATOR_USER}/${EVALUATOR_REPOSITORY}/contents/${path}" --data "$payload" >/dev/null
  else
    payload="$(jq -cn --arg content "$(base64 -w0 "$source")" --arg message "$message" '{content:$content,message:$message}')"
    forgejo "$EVALUATOR_AUTH" POST "/repos/${EVALUATOR_USER}/${EVALUATOR_REPOSITORY}/contents/${path}" --data "$payload" >/dev/null
  fi
}

install_public_material() {
  local public_root="${M06_PUBLIC_ROOT:-${TEMPLATE_ROOT}/content/public-site}"
  install -d -m 0755 \
    "$public_root/research" "$public_root/people/mira-chen" \
    "$public_root/conference" "$public_root/software/orion-field-review"
  install -m 0644 "${MODULE_ROOT}/payloads/public/research/"* "$public_root/research/"
  install -m 0644 "${MODULE_ROOT}/payloads/public/people/mira-chen/index.html" "$public_root/people/mira-chen/index.html"
  install -m 0644 "${MODULE_ROOT}/payloads/public/conference/"* "$public_root/conference/"
  curl -fsS \
    https://raw.githubusercontent.com/myshell-ai/OpenVoice/74a1d147b17a8c3092dd5430504bd83ef6c7eb23/resources/example_reference.mp3 \
    -o "$public_root/conference/mira-chen-reference.mp3"
  [[ $(sha256sum "$public_root/conference/mira-chen-reference.mp3" | cut -d' ' -f1) == \
    d0f5806f6e034e660c46a0b2fe4c597f0a1670859743c14e27a8823a7d169263 ]] || \
    die 'public conference audio differs from its admitted source revision'
  install -m 0644 "${MODULE_ROOT}/payloads/public/client/index.html" "$public_root/software/orion-field-review/index.html"
  install_real_public_client "$public_root"
  install_public_orion_kit "$public_root"

  if ! grep -q 'id="orion-public-work"' "$public_root/index.html"; then
    local updated
    updated="$(mktemp)"
    awk -v fragment="${MODULE_ROOT}/payloads/public/home-section.html" '
      /<\/main>/ {while ((getline line < fragment) > 0) print line; close(fragment)}
      {print}
    ' "$public_root/index.html" >"$updated"
    install -m 0644 "$updated" "$public_root/index.html"
    rm -f "$updated"
  fi
}

ensure_evaluator_identity() {
  local admin_auth=$OPERATOR_AUTH
  if forgejo "$EVALUATOR_AUTH" GET /user >/dev/null 2>&1; then
    admin_auth=$EVALUATOR_AUTH
  else
    forgejo "$OPERATOR_AUTH" POST /admin/users --data "$(jq -cn \
      --arg username "$EVALUATOR_USER" --arg email evaluation@cinder.lab \
      --arg password "$EVALUATOR_PASSWORD" \
      '{username:$username,email:$email,password:$password,must_change_password:false,admin:true,restricted:false,visibility:"private"}')" >/dev/null
  fi
  if ! forgejo "$EVALUATOR_AUTH" GET "/repos/${EVALUATOR_USER}/${EVALUATOR_REPOSITORY}" >/dev/null 2>&1; then
    forgejo "$EVALUATOR_AUTH" POST /user/repos --data "$(jq -cn --arg name "$EVALUATOR_REPOSITORY" \
      '{name:$name,description:"Independent Cinder experiment and capability evaluation",private:false,auto_init:true,default_branch:"main"}')" >/dev/null
  fi
  forgejo "$admin_auth" PATCH "/admin/users/cinder-operator" --data \
    '{"login_name":"cinder-operator","source_id":0,"email":"operator@cinder.lab","admin":false,"restricted":false,"active":true,"prohibit_login":false}' >/dev/null
}

install_evaluator() {
  compose up -d cinder-forgejo
  for _ in $(seq 1 60); do
    curl -fsS "${FORGEJO_API}/version" >/dev/null 2>&1 && break
    sleep 2
  done
  curl -fsS "${FORGEJO_API}/version" >/dev/null || die "Cinder Forgejo is unavailable"
  ensure_evaluator_identity
  ensure_forgejo_file README.md "${MODULE_ROOT}/payloads/evaluator/README.md" 'Update evaluator operating notes'
  ensure_forgejo_file .forgejo/workflows/evaluate.yaml "${MODULE_ROOT}/payloads/evaluator/workflow.yaml" 'Update independent evaluation workflow'

  docker exec --user 1000:1000 kep-v2-cinder-forgejo \
    forgejo --config /data/gitea/conf/app.ini forgejo-cli actions register \
      --name cinder-independent-evaluator \
      --scope "${EVALUATOR_USER}/${EVALUATOR_REPOSITORY}" \
      --labels cinder-evaluator \
      --secret "$RUNNER_SECRET" >/dev/null
  compose up -d --build cinder-evaluator-runner
}

install_cinder_routes() {
  local caddyfile="${TEMPLATE_ROOT}/config/caddy/Caddyfile"
  if ! grep -q 'campaign-m06-cinder-domains' "$caddyfile"; then
    cat >>"$caddyfile" <<'CADDY'

# campaign-m06-cinder-domains
https://*.cinder.lab {
  tls internal
  reverse_proxy 192.168.78.30:31080 {
    header_up Host {host}
  }
}

# campaign-m06-media-workbench
https://media.cinder.lab {
  tls internal
  reverse_proxy 10.61.90.33:8080
}

# campaign-m06-registrar
https://registrar.cinder.lab {
  tls internal
  reverse_proxy 10.61.90.34:8080
}

# campaign-m06-vector-workbench
https://vector.cinder.lab {
  tls internal
  reverse_proxy 10.61.90.35:6333
}

# campaign-m06-partner-intake-validation
https://partner-intake.keplerops.lab {
  tls internal
  reverse_proxy 10.61.10.29:8080
}
CADDY
  fi
}

install_scoped_model_access() {
  local caddyfile="${TEMPLATE_ROOT}/config/caddy/Caddyfile"
  python3 - "$caddyfile" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
old = """https://model.cinder.lab {
  tls internal
  reverse_proxy 192.168.78.30:30402
}
"""
new = """https://model.cinder.lab {
  tls internal
  @cinderOperator header Authorization \"Bearer Cinder-GLM-cinder-operator-6f2a9d8c\"
  handle @cinderOperator {
    reverse_proxy 192.168.78.30:30402 {
      header_up X-Cinder-Operator cinder-operator
    }
  }
  respond \"Cinder model credential required\" 401
  log {
    output file /data/cinder-model-access.json
    format json
  }
}
"""
if "X-Cinder-Operator cinder-operator" not in text:
    if old not in text:
        raise SystemExit("model.cinder.lab Caddy block differs from the campaign contract")
    path.write_text(text.replace(old, new, 1))
PY
  if docker inspect keplerops-participant-workstation-runtime >/dev/null 2>&1; then
    docker cp "${MODULE_ROOT}/payloads/workbench/opencode.json" \
      keplerops-participant-workstation-runtime:/tmp/cinder-opencode.json
    docker exec keplerops-participant-workstation-runtime sh -ec '
      install -d -m 0755 -o kasm-user -g kasm-user /home/kasm-user/.config/opencode
      install -m 0600 -o kasm-user -g kasm-user /tmp/cinder-opencode.json /home/kasm-user/.config/opencode/opencode.json
      rm /tmp/cinder-opencode.json
    '
  fi
}

reload_caddy() {
  if docker inspect kep-v2-caddy >/dev/null 2>&1; then
    docker exec kep-v2-caddy caddy reload --config /etc/caddy/Caddyfile >/dev/null
  fi
}

install_media_workbench() {
  compose up -d --build cinder-openvoice cinder-registrar cinder-qdrant keplerops-partner-intake
}

ensure_forgejo_secret() {
  local name=$1 value=$2
  forgejo "$OPERATOR_AUTH" PUT "/repos/cinder-operator/workbench-readiness/actions/secrets/${name}" \
    --data "$(jq -cn --arg data "$value" '{data:$data}')" >/dev/null
}

install_cinder_registry_identity() {
  local project robots robot_id robot robot_name robot_secret
  project='{"project_name":"cinder","public":false,"metadata":{"auto_scan":"false"}}'
  if ! curl -fsS --user "$HARBOR_ADMIN_AUTH" "${HARBOR_API}/projects?name=cinder" | jq -e 'length > 0' >/dev/null; then
    curl -fsS --user "$HARBOR_ADMIN_AUTH" -H 'Content-Type: application/json' \
      -X POST --data "$project" "${HARBOR_API}/projects" >/dev/null
  fi
  robots="$(curl -fsS --user "$HARBOR_ADMIN_AUTH" "${HARBOR_API}/robots?page=1&page_size=100")"
  robot_id="$(jq -r '.[] | select(.name | endswith("+cinder-publisher")) | .id' <<<"$robots" | head -n1)"
  if [[ -n $robot_id ]]; then
    curl -fsS --user "$HARBOR_ADMIN_AUTH" -X DELETE "${HARBOR_API}/robots/${robot_id}" >/dev/null
  fi
  robot="$(curl -fsS --user "$HARBOR_ADMIN_AUTH" -H 'Content-Type: application/json' -X POST \
    --data '{"name":"cinder-publisher","description":"Cinder operator image publication","duration":-1,"level":"project","permissions":[{"kind":"project","namespace":"cinder","access":[{"resource":"repository","action":"pull"},{"resource":"repository","action":"push"}]}]}' \
    "${HARBOR_API}/robots")"
  robot_name="$(jq -er .name <<<"$robot")"
  robot_secret="$(jq -er .secret <<<"$robot")"
  ensure_forgejo_secret CINDER_REGISTRY_USER "$robot_name"
  ensure_forgejo_secret CINDER_REGISTRY_PASSWORD "$robot_secret"
}

install_knative_publisher() {
  [[ -r $K3S01_SSH_KEY ]] || die 'k3s host key is unavailable for publisher installation'
  local state="${TEMPLATE_ROOT}/state/cinder-publisher" public_key
  install -d -m 0700 "$state"
  if [[ ! -s $state/id_ed25519 ]]; then
    ssh-keygen -q -t ed25519 -N '' -C cinder-knative-publisher -f "$state/id_ed25519"
  fi
  public_key="$(cat "$state/id_ed25519.pub")"
  ssh-keyscan -H 192.168.78.30 >"$state/known_hosts" 2>/dev/null
  tar -C "${MODULE_ROOT}/payloads/serverless" -cf - cinder-knative-publisher | \
    ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
      "$K3S01_SSH_TARGET" 'cat >/tmp/cinder-knative-publisher.tar && sudo tar -C /usr/local/sbin -xf /tmp/cinder-knative-publisher.tar && rm /tmp/cinder-knative-publisher.tar && sudo chmod 0755 /usr/local/sbin/cinder-knative-publisher'
  ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    "$K3S01_SSH_TARGET" sudo bash -s -- "$public_key" <<'REMOTE'
set -Eeuo pipefail
key=$1
id cinder-publisher >/dev/null 2>&1 || useradd -m -s /bin/bash cinder-publisher
install -d -m 0700 -o cinder-publisher -g cinder-publisher /home/cinder-publisher/.ssh
printf 'restrict,command="sudo /usr/local/sbin/cinder-knative-publisher" %s\n' "$key" > /home/cinder-publisher/.ssh/authorized_keys
chown cinder-publisher:cinder-publisher /home/cinder-publisher/.ssh/authorized_keys
chmod 0600 /home/cinder-publisher/.ssh/authorized_keys
printf 'cinder-publisher ALL=(root) NOPASSWD: /usr/local/sbin/cinder-knative-publisher\n' > /etc/sudoers.d/cinder-knative-publisher
chmod 0440 /etc/sudoers.d/cinder-knative-publisher
REMOTE
}

install_workbench_material() {
  local source name body
  for source in \
    "${MODULE_ROOT}/payloads/workbench/START-HERE.md" \
    "${MODULE_ROOT}/payloads/workbench/SERVERLESS-PUBLISH.md" \
    "${MODULE_ROOT}/payloads/workbench/SUBMISSION-SCHEMAS.json"; do
    name="$(basename "$source")"
    body="$(base64 -w0 "$source")"
    curl -fsS -X PUT -H 'Content-Type: application/json' \
      --data "$(jq -cn --arg content "$body" '{type:"file",format:"base64",content:$content}')" \
      "http://10.61.90.32:8888/api/contents/${name}?token=Cinder-Operations-Notebook-R5w8Nx2k" >/dev/null
  done
}

apply_common() {
  install_public_material
  install_cinder_routes
  install_scoped_model_access
  install_media_workbench
  reload_caddy
  install_evaluator
  install_cinder_registry_identity
  install_knative_publisher
  compose up -d cinder-forgejo-runner
  install_workbench_material
}

main() {
  for command in awk base64 curl docker jq python3 sha256sum ssh ssh-keygen ssh-keyscan tar unzip; do require "$command"; done
  if [[ $OPERATION != all ]]; then
    jq -e --arg id "$OPERATION" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: $OPERATION"
  fi
  apply_common
  if [[ $OPERATION == kep-m06-m ]]; then
    "${TEMPLATE_ROOT}/scripts/prove-hardware.sh"
  fi
  log "applied ${OPERATION}"
}

main "$@"
