#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-all}"
readonly FORGEJO_URL="${CINDER_FORGEJO_URL:-http://10.61.90.30:3000}"
readonly FORGEJO_API="${FORGEJO_URL}/api/v1"
readonly PARTICIPANT_AUTH="cinder-field-operator:Cinder-Field-Operator-Git-V6n4Qs8p"
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
readonly DIRECTORY_SSH_KEY="${KEPLEROPS_GUEST_KEY:-/root/.ssh/keplerops-v2}"
readonly DC01="${KEPLEROPS_DC01_ADDRESS:-192.168.78.10}"

log() { printf '[campaign-m06] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }
require() { command -v "$1" >/dev/null 2>&1 || die "required command unavailable: $1"; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" \
    -f "${TEMPLATE_ROOT}/compose.cinder.yaml" \
    -f "${TEMPLATE_ROOT}/campaign-start/modules/m07/compose.overlay.yaml" \
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
  local build_revision prior_run prior_id run status release release_id dispatch
  build_revision="$(public_forgejo GET "/repos/${PUBLIC_BUILD_REPOSITORY}/branches/main" | jq -er '.commit.id')"
  prior_run="$(latest_release_run "$build_revision")"
  prior_id="$(jq -r '.id // 0' <<<"${prior_run:-null}")"

  release="$(public_forgejo GET "/repos/${PUBLIC_SOURCE_REPOSITORY}/releases/tags/${PUBLIC_RELEASE_TAG}" 2>/dev/null || true)"
  if jq -e 'type == "object" and has("id")' <<<"$release" >/dev/null 2>&1; then
    release_id="$(jq -er .id <<<"$release")"
    public_forgejo DELETE "/repos/${PUBLIC_SOURCE_REPOSITORY}/releases/${release_id}" >/dev/null
  fi
  public_forgejo DELETE "/repos/${PUBLIC_SOURCE_REPOSITORY}/tags/${PUBLIC_RELEASE_TAG}" >/dev/null 2>&1 || true
  dispatch="$(public_forgejo POST "/repos/${PUBLIC_BUILD_REPOSITORY}/actions/workflows/${PUBLIC_RELEASE_WORKFLOW}/dispatches" \
    --data '{"ref":"main","inputs":{},"return_run_info":true}')"
  jq -e '.id > 0 and (.jobs | index("release")) != null' <<<"$dispatch" >/dev/null

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
  [[ $url == https://git.keplerops.lab/* ]] || die "unexpected public release asset URL: ${url}"
  url="${PUBLIC_FORGEJO_URL}${url#https://git.keplerops.lab}"
  curl -fsS --user "$PUBLIC_FORGEJO_AUTH" "$url" -o "$destination"
}

install_real_public_client() (
  local public_root=$1 source_changed=false release source_revision release_revision workdir
  if ensure_public_source_file ci/prepare-client.py \
      "${MODULE_ROOT}/payloads/public/client/prepare-client.py"; then
    source_changed=true
  fi
  source_revision="$(public_forgejo GET "/repos/${PUBLIC_SOURCE_REPOSITORY}/branches/main" | jq -er '.commit.id')"
  release="$(public_forgejo GET "/repos/${PUBLIC_SOURCE_REPOSITORY}/releases/tags/${PUBLIC_RELEASE_TAG}" 2>/dev/null || true)"
  release_revision="$(jq -r '.target_commitish // empty' <<<"${release:-null}")"
  if [[ $source_changed == true || $release_revision != "$source_revision" ]]; then
    rebuild_public_client_release
    release="$(public_forgejo GET "/repos/${PUBLIC_SOURCE_REPOSITORY}/releases/tags/${PUBLIC_RELEASE_TAG}")"
  fi

  workdir="$(mktemp -d)"
  trap 'rm -rf "$workdir"' EXIT
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
  local repo_root="$public_root/software/orion-field-review/repo"
  local fdroid_root="${TEMPLATE_ROOT}/state/campaign-start/m06-fdroid"
  local keystore="$fdroid_root/keystore.jks"
  rm -rf "$fdroid_root/repo" "$fdroid_root/archive" "$fdroid_root/metadata"
  install -d -m 0755 "$fdroid_root/repo" "$fdroid_root/metadata"
  install -m 0644 "$workdir/client.apk" "$fdroid_root/repo/orion-mobile-1.0.0.apk"
  install -m 0644 "${TEMPLATE_ROOT}/seeding/payloads/orion-public/metadata/com.keplerops.orion.yml" \
    "$fdroid_root/metadata/com.keplerops.orion.yml"
  if [[ ! -s $keystore ]]; then
    keytool -genkeypair -noprompt -keystore "$keystore" -storepass Cinder-FDroid-Signing-P4m8Zx2n \
      -keypass Cinder-FDroid-Signing-P4m8Zx2n -alias cinder-fdroid -keyalg RSA -keysize 3072 \
      -validity 3650 -dname 'CN=KeplerOps Orion Field Review,O=KeplerOps AI Systems,C=DE' >/dev/null
  fi
  cat >"$fdroid_root/config.yml" <<'YAML'
repo_url: https://keplerops.lab/software/orion-field-review/repo
repo_name: KeplerOps Orion Field Review
repo_description: Signed mobile releases used by KeplerOps field reviewers.
keystore: keystore.jks
repo_keyalias: cinder-fdroid
keystorepass: Cinder-FDroid-Signing-P4m8Zx2n
keypass: Cinder-FDroid-Signing-P4m8Zx2n
archive_older: 0
YAML
  compose build cinder-fdroidserver >/dev/null
  compose run --rm --no-deps cinder-fdroidserver update --create-metadata >/dev/null
  local signed_index_dir="$workdir/fdroid-index"
  install -d -m 0755 "$signed_index_dir"
  unzip -p "$fdroid_root/repo/index-v1.jar" index-v1.json \
    >"$signed_index_dir/index-v1.json"
  (cd "$signed_index_dir" && jar --create --file index-v1.jar index-v1.json)
  jarsigner -keystore "$keystore" \
    -storepass Cinder-FDroid-Signing-P4m8Zx2n \
    -keypass Cinder-FDroid-Signing-P4m8Zx2n \
    -sigalg SHA256withRSA -digestalg SHA-256 \
    "$signed_index_dir/index-v1.jar" cinder-fdroid >/dev/null
  jarsigner -verify -strict -keystore "$keystore" \
    -storepass Cinder-FDroid-Signing-P4m8Zx2n \
    "$signed_index_dir/index-v1.jar" >/dev/null
  install -m 0644 "$signed_index_dir/index-v1.jar" \
    "$fdroid_root/repo/index-v1.jar"
  rm -rf "$repo_root"
  install -d -m 0755 "$repo_root"
  cp -a "$fdroid_root/repo/." "$repo_root/"
  install -m 0644 "$workdir/sbom.json" "$repo_root/orion-field-review.cdx.json"
  install -m 0644 "$workdir/manifest.json" "$repo_root/release-manifest.json"
  keytool -exportcert -rfc -keystore "$keystore" -storepass Cinder-FDroid-Signing-P4m8Zx2n \
    -alias cinder-fdroid >"$repo_root/repo-signing.pem"
  keytool -printcert -file "$repo_root/repo-signing.pem" | awk -F': ' '/SHA256:/{gsub(":", "", $2); print tolower($2)}' >"$repo_root/repo-signing-sha256.txt"
)

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

install_cinder_routes() {
  local caddyfile="${TEMPLATE_ROOT}/config/caddy/Caddyfile"
  if ! grep -q 'campaign-m06-cinder-domains' "$caddyfile"; then
    cat >>"$caddyfile" <<'CADDY'

# campaign-m06-cinder-domains
# campaign-m06-media-workbench
https://media.cinder.lab {
  tls internal
  reverse_proxy 10.61.90.33:8080
}

# campaign-m06-developer-assistant
https://developer.cinder.lab {
  tls internal
  reverse_proxy 10.61.90.37:8080
}

# campaign-m06-host-bridge
https://bridge.cinder.lab {
  tls internal
  reverse_proxy 10.61.90.38:8080
}

# campaign-m06-experiments
https://experiments.cinder.lab {
  tls internal
  reverse_proxy 10.61.90.39:8080
}

# campaign-m06-release-registry
https://releases.cinder.lab {
  tls internal
  reverse_proxy 10.61.90.40:8080
}

# campaign-m06-registrar
https://registrar.cinder.lab {
  tls internal
  reverse_proxy 10.61.90.34:8080
}

# campaign-m06-step-ca
https://ca.keplerops.lab {
  tls internal
  reverse_proxy https://10.61.20.21:9000 {
    transport http {
      tls_insecure_skip_verify
    }
  }
}

# campaign-m06-vector-workbench
https://vector.cinder.lab {
  tls internal
  reverse_proxy 10.61.90.35:6333
}

# campaign-m06-partner-intake
https://partner-intake.keplerops.lab {
  tls internal
  reverse_proxy 10.61.10.29:8080
}

# campaign-m06-edge-observer
https://external-intake.keplerops.lab {
  tls internal
  reverse_proxy 10.61.10.28:8080
}

# campaign-m06-independent-osint
https://orion-open-systems.org {
  tls internal
  reverse_proxy 10.61.10.30:80
}

# campaign-m06-knative-records
https://knative.cinder.lab {
  tls internal
  reverse_proxy 192.168.78.30:31082
}
CADDY
  fi
  python3 - "$caddyfile" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
start = text.index("# campaign-m06-cinder-domains")
end = text.find("# campaign-m06-prerequisite-records", start)
end = len(text) if end < 0 else end
managed = text[start:end]
managed = managed.replace("https://status.keplerops.lab {\n  tls internal\n  reverse_proxy 10.61.10.28:8080\n}",
                          "https://external-intake.keplerops.lab {\n  tls internal\n  reverse_proxy 10.61.10.28:8080\n}")
if "https://external-intake.keplerops.lab" not in managed or "https://status.keplerops.lab" in managed:
    raise SystemExit("m06 external-intake Caddy route differs from the campaign contract")
path.write_text(text[:start] + managed + text[end:])
PY
  if ! grep -q 'campaign-m06-prerequisite-records' "$caddyfile"; then
    cat >>"$caddyfile" <<'CADDY'

# campaign-m06-prerequisite-records
https://artifacts.keplerops.lab {
  tls internal
  reverse_proxy 10.61.50.60:9000
}
CADDY
  fi
  if ! grep -q 'campaign-m06-scoped-object-api' "$caddyfile"; then
    cat >>"$caddyfile" <<'CADDY'

# campaign-m06-scoped-object-api
https://storage.cinder.lab {
  tls internal
  reverse_proxy 10.61.90.31:9000
}
CADDY
  fi
}

install_osint_records() {
  curl -fsS -H 'X-API-Key: KeplerV2-Training-PDNS' -H 'Content-Type: application/json' -X PATCH \
    --data '{"rrsets":[{"name":"partner-intake.keplerops.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.10.2","disabled":false}]},{"name":"external-intake.keplerops.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.10.2","disabled":false}]},{"name":"artifacts.keplerops.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.10.2","disabled":false}]},{"name":"ca.keplerops.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.10.2","disabled":false}]}]}' \
    http://10.61.10.10:8081/api/v1/servers/localhost/zones/keplerops.lab. >/dev/null
  curl -fsS -H 'X-API-Key: KeplerV2-Training-PDNS' -H 'Content-Type: application/json' -X PATCH \
    --data '{"rrsets":[{"name":"media.cinder.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.90.2","disabled":false}]},{"name":"developer.cinder.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.90.2","disabled":false}]},{"name":"bridge.cinder.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.90.2","disabled":false}]},{"name":"experiments.cinder.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.90.2","disabled":false}]},{"name":"releases.cinder.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.90.2","disabled":false}]},{"name":"registrar.cinder.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.90.2","disabled":false}]},{"name":"vector.cinder.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.90.2","disabled":false}]},{"name":"knative.cinder.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.90.2","disabled":false}]},{"name":"storage.cinder.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.90.2","disabled":false}]}]}' \
    http://10.61.10.10:8081/api/v1/servers/localhost/zones/cinder.lab. >/dev/null
  if ! docker exec kep-v2-pdns-auth pdnsutil list-zone orion-open-systems.org >/dev/null 2>&1; then
    docker exec kep-v2-pdns-auth pdnsutil create-zone \
      orion-open-systems.org ns1.keplerops.lab
  fi
  docker exec kep-v2-pdns-auth pdnsutil replace-rrset \
    orion-open-systems.org @ A 300 10.61.10.2
  docker exec kep-v2-pdns-auth pdnsutil replace-rrset \
    orion-open-systems.org @ MX 300 '10 mail.keplerops.lab.'
  docker exec kep-v2-pdns-auth pdnsutil check-zone orion-open-systems.org
  local admin='range-admin:KeplerV2-Training-Forgejo-Admin'
  curl -fsS --user "$admin" -H 'Content-Type: application/json' -X POST \
    --data '{"username":"mira.chen","email":"mira.chen@orion-open-systems.org","password":"OSINT-Profile-Not-Participant-3mP8vQ","must_change_password":false,"visibility":"public"}' \
    "${PUBLIC_FORGEJO_API}/admin/users" >/dev/null 2>&1 || true
  curl -fsS --user "$admin" -H 'Content-Type: application/json' -X POST \
    --data '{"username":"northstar-research","full_name":"Northstar Research Cooperative","description":"Research partner for Orion Open Systems","visibility":"public"}' \
    "${PUBLIC_FORGEJO_API}/orgs" >/dev/null 2>&1 || true
  docker exec kep-v2-pdns-recursor rec_control wipe-cache \
    'keplerops.lab$' 'cinder.lab$' 'orion-open-systems.org$' >/dev/null
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
  reverse_proxy 10.61.90.36:8080
}
"""
if "reverse_proxy 10.61.90.36:8080" not in text:
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

install_operator_dossier() {
  docker inspect keplerops-participant-workstation-runtime >/dev/null 2>&1 || \
    die 'Cinder operator workstation is unavailable'
  local staging
  staging="$(mktemp -d)"
  install -m 0644 "${MODULE_ROOT}/payloads/workbench/START-HERE.md" "$staging/START-HERE.md"
  install -m 0644 "${MODULE_ROOT}/payloads/workbench/SERVERLESS-PUBLISH.md" "$staging/SERVERLESS-PUBLISH.md"
  install -m 0644 "${MODULE_ROOT}/integrations.json" "$staging/integrations.json"
  docker cp "$staging/." keplerops-participant-workstation-runtime:/tmp/cinder-operations
  rm -rf "$staging"
  docker exec keplerops-participant-workstation-runtime sh -ec '
    rm -rf /home/kasm-user/Desktop/Cinder-Operations
    install -d -m 0750 -o kasm-user -g kasm-user /home/kasm-user/Desktop/Cinder-Operations
    cp -a /tmp/cinder-operations/. /home/kasm-user/Desktop/Cinder-Operations/
    chown -R kasm-user:kasm-user /home/kasm-user/Desktop/Cinder-Operations
    rm -rf /tmp/cinder-operations
  '
}

prepare_range_model_identity() {
  local identity_file key range key_id
  install -d -m 0700 "${TEMPLATE_ROOT}/state"
  for identity_file in \
      "${TEMPLATE_ROOT}/state/cinder-model-identity.env" \
      "${TEMPLATE_ROOT}/state/partner-model-identity.env"; do
    if [[ ! -s $identity_file ]]; then
      umask 077
      range="range-$(cat /proc/sys/kernel/random/uuid)"
      key="$(openssl rand -hex 32)"
      key_id="m06-$(printf %s "$key" | sha256sum | cut -c1-16)"
      printf 'CINDER_RANGE_ID=%s\nCINDER_RANGE_ASSERTION_KEY=%s\nCINDER_RANGE_ASSERTION_KEY_ID=%s\n' \
        "$range" "$key" "$key_id" >"$identity_file"
    fi
    grep -Eq '^CINDER_RANGE_ID=range-[0-9a-f-]{36}$' "$identity_file" || die 'Cinder range model identity is malformed'
    grep -Eq '^CINDER_RANGE_ASSERTION_KEY=[0-9a-f]{64}$' "$identity_file" || die 'Cinder range assertion key is malformed'
    grep -Eq '^CINDER_RANGE_ASSERTION_KEY_ID=m06-[0-9a-f]{16}$' "$identity_file" || die 'Cinder range assertion key ID is malformed'
    chmod 0600 "$identity_file"
  done
}

reload_caddy() {
  if docker inspect kep-v2-caddy >/dev/null 2>&1; then
    docker exec kep-v2-caddy caddy reload --config /etc/caddy/Caddyfile >/dev/null
  fi
}

ensure_preview_shared_audit_mount() {
  if ! docker inspect kep-v2-preview >/dev/null 2>&1; then
    return
  fi
  if docker inspect kep-v2-preview --format '{{range .Mounts}}{{println .Destination}}{{end}}' |
      grep -Fxq /var/lib/orion-preview/audit; then
    return
  fi
  log "recreating preview with shared Orion audit volume"
  compose up -d --build --force-recreate --no-deps preview
}

install_native_services() {
  compose build preview >/dev/null
  compose run --rm --no-deps --user 0:0 --entrypoint sh preview -ec \
    'chown 10001:10001 /var/lib/orion-preview/audit && chmod 0755 /var/lib/orion-preview/audit'
  compose up -d --build \
    preview orion-osint-site cinder-forgejo cinder-buildkit cinder-jupyter \
    cinder-model-edge cinder-developer-assistant cinder-host-bridge \
    cinder-openvoice cinder-registrar cinder-qdrant keplerops-intake-qdrant \
    keplerops-model-edge keplerops-partner-intake keplerops-edge-observer \
    cinder-experiments cinder-release-registry
  ensure_preview_shared_audit_mount
}

ensure_cinder_acme() {
  if docker exec kep-v2-step-ca step ca provisioner list \
      --ca-url https://localhost:9000 --root /home/step/certs/root_ca.crt | \
      jq -e 'any(.[]; .name == "cinder-acme" and .type == "ACME")' >/dev/null; then
    return
  fi
  docker exec kep-v2-step-ca step ca provisioner add cinder-acme --type ACME \
    --admin-subject step --admin-provisioner range-provisioner \
    --admin-password-file /home/step/secrets/password \
    --ca-url https://localhost:9000 --root /home/step/certs/root_ca.crt >/dev/null
  docker exec kep-v2-step-ca step ca provisioner list \
    --ca-url https://localhost:9000 --root /home/step/certs/root_ca.crt | \
    jq -e 'any(.[]; .name == "cinder-acme" and .type == "ACME")' >/dev/null || \
    die 'Cinder ACME provisioner did not become ready'
}

prepare_cinder_trust_bundle() {
  local bundle="${TEMPLATE_ROOT}/state/cinder-trust-bundle.crt"
  local step_root="${TEMPLATE_ROOT}/state/cinder-step-root.crt"
  install -d -m 0700 "${TEMPLATE_ROOT}/state"
  docker exec kep-v2-step-ca sed -n '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/p' /home/step/certs/root_ca.crt >"$step_root"
  {
    sed -n '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/p' "${TEMPLATE_ROOT}/state/caddy-root.crt"
    cat "$step_root"
  } >"$bundle"
  [[ $(grep -c '^-----BEGIN CERTIFICATE-----$' "$bundle") -eq 2 ]] || die 'Cinder trust bundle does not contain all admitted roots'
  chmod 0644 "$bundle" "$step_root"
  if docker inspect keplerops-participant-workstation-runtime >/dev/null 2>&1; then
    docker exec --user root keplerops-participant-workstation-runtime sh -ec '
      update-ca-certificates >/dev/null
    '
  fi
}

install_cinder_registry_identity() {
  local project robots robot_id
  project='{"project_name":"cinder","public":false,"metadata":{"auto_scan":"false"}}'
  if ! curl -fsS --user "$HARBOR_ADMIN_AUTH" "${HARBOR_API}/projects?name=cinder" | jq -e 'any(.[]; .name == "cinder")' >/dev/null; then
    curl -fsS --user "$HARBOR_ADMIN_AUTH" -H 'Content-Type: application/json' \
      -X POST --data "$project" "${HARBOR_API}/projects" >/dev/null
  fi
  robots="$(curl -fsS --user "$HARBOR_ADMIN_AUTH" "${HARBOR_API}/robots?page=1&page_size=100")"
  robot_id="$(jq -r '.[] | select(.name | endswith("+cinder-publisher")) | .id' <<<"$robots" | head -n1)"
  if [[ -n $robot_id ]]; then
    curl -fsS --user "$HARBOR_ADMIN_AUTH" -X DELETE "${HARBOR_API}/robots/${robot_id}" >/dev/null
  fi
  forgejo "$PARTICIPANT_AUTH" DELETE /user/actions/secrets/CINDER_REGISTRY_USER >/dev/null 2>&1 || true
  forgejo "$PARTICIPANT_AUTH" DELETE /user/actions/secrets/CINDER_REGISTRY_PASSWORD >/dev/null 2>&1 || true
}

install_participant_object_identity() {
  compose run --rm --no-deps --entrypoint sh cinder-bootstrap -ec '
    set -eu
    mc alias set cinder http://10.61.90.31:9000 cinder-operator Cinder-Operations-ObjectStore-T7v2Lm9q >/dev/null
    mc admin user add cinder cinder-field-operator Cinder-Field-Operator-Objects-H8r3Tm5w >/dev/null 2>&1 || true
    printf %s "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:ListBucket\"],\"Resource\":[\"arn:aws:s3:::operations\"],\"Condition\":{\"StringLike\":{\"s3:prefix\":[\"acquired/cinder-field-operator/*\",\"staged/cinder-field-operator/*\"]}}},{\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:PutObject\"],\"Resource\":[\"arn:aws:s3:::operations/acquired/cinder-field-operator/*\",\"arn:aws:s3:::operations/staged/cinder-field-operator/*\"]}]}" >/tmp/cinder-field-operator-policy.json
    mc admin policy create cinder cinder-field-operator-rw /tmp/cinder-field-operator-policy.json >/dev/null 2>&1 || mc admin policy info cinder cinder-field-operator-rw >/dev/null
    mc admin policy attach cinder cinder-field-operator-rw --user cinder-field-operator >/dev/null
  '
}

install_participant_prerequisite_identity() {
  local mc_image
  mc_image="$(awk -F= '$1=="MINIO_MC_IMAGE"{print substr($0,index($0,"=")+1)}' "${TEMPLATE_ROOT}/engineering/component-lock.additions.env")"
  [[ -n $mc_image ]] || die 'MINIO_MC_IMAGE is not pinned'
  docker run --rm --network kep-v2-data --entrypoint sh "$mc_image" -ec '
    set -eu
    mc alias set source http://minio:9000 kepler-minio KeplerV2-Training-Minio-Object-Store >/dev/null
    mc admin user add source cinder-prerequisite-reader Cinder-Field-Operator-Prerequisites-F4s9Wk2q >/dev/null 2>&1 || true
    printf %s "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\"],\"Resource\":[\"arn:aws:s3:::artifacts/evaluation-reports/compatibility/*\",\"arn:aws:s3:::artifacts/evaluation-reports/prompt-renderer-compatibility/*\",\"arn:aws:s3:::artifacts/evaluation-reports/agent-capability-audit/*\"]}]}" >/tmp/cinder-prerequisite-policy.json
    mc admin policy create source cinder-prerequisite-read /tmp/cinder-prerequisite-policy.json >/dev/null 2>&1 || mc admin policy info source cinder-prerequisite-read >/dev/null
    mc admin policy attach source cinder-prerequisite-read --user cinder-prerequisite-reader >/dev/null
  '
}

install_participant_mail_identity() {
  [[ -r $DIRECTORY_SSH_KEY ]] || die 'directory guest SSH key is unavailable'
  ssh -i "$DIRECTORY_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null "kepler@${DC01}" sudo bash -s <<'REMOTE'
set -Eeuo pipefail

ensure_external_mail_user() {
  local username=$1 password=$2 description=$3 address=$4
  samba-tool ou add 'OU=External Accounts' >/dev/null 2>&1 || true
  if ! samba-tool user show "$username" >/dev/null 2>&1; then
    samba-tool user create "$username" "$password" \
      --userou='OU=External Accounts' --description="$description" \
      --mail-address="$address" >/dev/null
  elif ! samba-tool user show "$username" | grep -Fqi ',OU=External Accounts,DC='; then
    samba-tool user move "$username" 'OU=External Accounts' >/dev/null
  fi
  samba-tool user setpassword "$username" --newpassword="$password" >/dev/null
  samba-tool user rename "$username" --mail-address="$address" >/dev/null
  samba-tool user setexpiry "$username" --noexpiry >/dev/null
  samba-tool user enable "$username" >/dev/null
}

ensure_external_mail_user cinder.field-operator \
  Cinder-Field-Operator-Mail-J7p4Vn6s 'Cinder field operator' \
  cinder.field-operator@cinder.lab
ensure_external_mail_user orion.program \
  Orion-Program-Mail-N4w7Qp2m 'Orion Open Systems program office' \
  program@orion-open-systems.org
REMOTE
}

install_knative_publisher() {
  [[ -r $K3S01_SSH_KEY ]] || die 'k3s host key is unavailable for publisher installation'
  local state="${TEMPLATE_ROOT}/state/cinder-publisher" public_key_b64
  install -d -m 0700 "$state"
  if [[ ! -s $state/id_ed25519 ]]; then
    ssh-keygen -q -t ed25519 -N '' -C cinder-knative-publisher -f "$state/id_ed25519"
  fi
  public_key_b64="$(base64 -w0 "$state/id_ed25519.pub")"
  ssh-keyscan -H 192.168.78.30 >"$state/known_hosts" 2>/dev/null
  ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    "$K3S01_SSH_TARGET" 'sudo tee /usr/local/share/ca-certificates/cinder-trust-bundle.crt >/dev/null && sudo chmod 0644 /usr/local/share/ca-certificates/cinder-trust-bundle.crt' \
    <"${TEMPLATE_ROOT}/state/cinder-trust-bundle.crt"
  tar -C "${MODULE_ROOT}/payloads/serverless" -cf - cinder-knative-publisher cinder-knative-records-server | \
    ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
      "$K3S01_SSH_TARGET" 'cat >/tmp/cinder-knative-publisher.tar && sudo tar -C /usr/local/sbin -xf /tmp/cinder-knative-publisher.tar && rm /tmp/cinder-knative-publisher.tar && sudo chmod 0755 /usr/local/sbin/cinder-knative-publisher /usr/local/sbin/cinder-knative-records-server'
  ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    "$K3S01_SSH_TARGET" sudo bash -s -- "$public_key_b64" <<'REMOTE'
set -Eeuo pipefail
key="$(printf '%s' "$1" | base64 -d)"
id cinder-publisher >/dev/null 2>&1 || useradd -m -s /bin/bash cinder-publisher
install -d -m 0700 -o cinder-publisher -g cinder-publisher /home/cinder-publisher/.ssh
printf 'restrict,command="sudo /usr/local/sbin/cinder-knative-publisher" %s\n' "$key" > /home/cinder-publisher/.ssh/authorized_keys
chown cinder-publisher:cinder-publisher /home/cinder-publisher/.ssh/authorized_keys
chmod 0600 /home/cinder-publisher/.ssh/authorized_keys
printf 'cinder-publisher ALL=(root) NOPASSWD: /usr/local/sbin/cinder-knative-publisher\n' > /etc/sudoers.d/cinder-knative-publisher
chmod 0440 /etc/sudoers.d/cinder-knative-publisher
install -d -m 0750 -o cinder-publisher -g cinder-publisher /var/lib/cinder-publisher/lifecycles /var/lib/cinder-publisher/deployments
cat >/etc/systemd/system/cinder-knative-records.service <<'UNIT'
[Unit]
Description=Cinder native Knative lifecycle journal
After=network-online.target
[Service]
ExecStart=/usr/local/sbin/cinder-knative-records-server
User=cinder-publisher
Group=cinder-publisher
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadOnlyPaths=/var/lib/cinder-publisher/lifecycles
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now cinder-knative-records.service
REMOTE
}

prepare_cinder_jupyterhub() {
  [[ -r $K3S01_SSH_KEY ]] || die 'k3s host key is unavailable for JupyterHub installation'
  local state="${TEMPLATE_ROOT}/state/cinder-jupyterhub" token ca singleuser_base singleuser_image
  install -d -m 0700 "$state"
  ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$K3S01_SSH_TARGET" sudo k3s kubectl apply -f - <<'RBAC' >/dev/null
apiVersion: v1
kind: ServiceAccount
metadata: {name: cinder-jupyterhub, namespace: cinder}
---
apiVersion: v1
kind: ServiceAccount
metadata: {name: cinder-jupyter-user, namespace: cinder}
automountServiceAccountToken: false
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: {name: cinder-jupyterhub, namespace: cinder}
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "pods/exec", "persistentvolumeclaims", "events", "configmaps"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: cinder-jupyterhub, namespace: cinder}
subjects: [{kind: ServiceAccount, name: cinder-jupyterhub, namespace: cinder}]
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: Role, name: cinder-jupyterhub}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: cinder-jupyter-participant, namespace: cinder}
spec:
  podSelector:
    matchLabels: {cinder.keplerops.lab/workspace: participant}
  policyTypes: [Ingress, Egress]
  ingress:
    - from: [{ipBlock: {cidr: 192.168.78.1/32}}]
      ports: [{protocol: TCP, port: 8888}]
  egress:
    - to:
        - namespaceSelector:
            matchLabels: {kubernetes.io/metadata.name: kube-system}
          podSelector:
            matchLabels: {k8s-app: kube-dns}
      ports: [{protocol: UDP, port: 53}, {protocol: TCP, port: 53}]
    - to: [{ipBlock: {cidr: 10.61.90.2/32}}]
      ports: [{protocol: TCP, port: 443}]
    - to: [{ipBlock: {cidr: 192.168.78.1/32}}]
      ports: [{protocol: TCP, port: 18081}]
RBAC
  ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes "$K3S01_SSH_TARGET" \
    'sudo k3s kubectl -n cinder create configmap cinder-workbench-ca --from-file=trust-bundle.crt=/dev/stdin --dry-run=client -o yaml | sudo k3s kubectl apply -f -' \
    <"${TEMPLATE_ROOT}/state/cinder-trust-bundle.crt" >/dev/null
  token="$(ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes "$K3S01_SSH_TARGET" sudo k3s kubectl -n cinder create token cinder-jupyterhub --duration=8760h)"
  ca="$(ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes "$K3S01_SSH_TARGET" sudo k3s kubectl config view --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')"
  umask 077
  printf '%s\n' \
    'apiVersion: v1' 'kind: Config' \
    'clusters:' '  - name: cinder' "    cluster: {server: https://192.168.78.30:6443, certificate-authority-data: ${ca}}" \
    'users:' '  - name: cinder-jupyterhub' "    user: {token: ${token}}" \
    'contexts:' '  - name: cinder' '    context: {cluster: cinder, user: cinder-jupyterhub, namespace: cinder}' \
    'current-context: cinder' >"$state/kubeconfig"
  singleuser_base="$(awk -F= '$1=="JUPYTER_IMAGE"{print substr($0,index($0,"=")+1)}' "${TEMPLATE_ROOT}/component-lock.env")"
  [[ -n $singleuser_base ]] || die 'JUPYTER_IMAGE is not pinned'
  singleuser_image="keplerops/cinder-jupyter-singleuser:campaign-v2"
  docker pull "$singleuser_base" >/dev/null
  docker build --pull=false \
    --build-arg JUPYTER_IMAGE="$singleuser_base" \
    -t "$singleuser_image" \
    -f "${MODULE_ROOT}/payloads/jupyter-singleuser/Dockerfile" \
    "${MODULE_ROOT}" >/dev/null
  docker save "$singleuser_image" | ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes "$K3S01_SSH_TARGET" sudo k3s ctr images import - >/dev/null
}

install_participant_publisher_access() {
  docker cp "${TEMPLATE_ROOT}/state/cinder-publisher/id_ed25519" \
    keplerops-participant-workstation-runtime:/tmp/cinder-publisher-id
  docker cp "${TEMPLATE_ROOT}/state/cinder-publisher/known_hosts" \
    keplerops-participant-workstation-runtime:/tmp/cinder-publisher-known-hosts
  docker exec keplerops-participant-workstation-runtime sh -ec '
    install -d -m 0700 -o kasm-user -g kasm-user /home/kasm-user/.cinder/publisher
    install -m 0600 -o kasm-user -g kasm-user /tmp/cinder-publisher-id /home/kasm-user/.cinder/publisher/id_ed25519
    install -m 0600 -o kasm-user -g kasm-user /tmp/cinder-publisher-known-hosts /home/kasm-user/.cinder/publisher/known_hosts
    rm -f /tmp/cinder-publisher-id /tmp/cinder-publisher-known-hosts
  '
}

apply_common() {
  install_public_material
  install_cinder_routes
  install_osint_records
  prepare_range_model_identity
  install_scoped_model_access
  ensure_cinder_acme
  prepare_cinder_trust_bundle
  prepare_cinder_jupyterhub
  install_native_services
  install_operator_dossier
  reload_caddy
  install_cinder_registry_identity
  install_participant_object_identity
  install_participant_prerequisite_identity
  install_participant_mail_identity
  install_knative_publisher
  compose up -d --build cinder-forgejo-runner
  install_participant_publisher_access
}

main() {
  for command in awk base64 curl docker jar jarsigner jq keytool python3 sha256sum ssh ssh-keygen ssh-keyscan tar unzip; do require "$command"; done
  if [[ $OPERATION != all ]]; then
    jq -e --arg id "$OPERATION" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: $OPERATION"
  fi
  apply_common
  if [[ $OPERATION == kep-m06-m ]]; then
    [[ ${CAMPAIGN_APPLY_ID:-} =~ ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]] || \
      die 'CAMPAIGN_APPLY_ID must be the explicit current physical proof UUID'
    "${TEMPLATE_ROOT}/scripts/prove-hardware.sh"
  fi
  log "applied ${OPERATION}"
}

main "$@"
