#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Build and sign the complete Orion Release Risk model package.

Usage: build-model-package.sh <candidate-dir> <release-id> <output-dir>

The signing directory defaults to /var/lib/keplerops-platform/signing and may
be overridden with PLATFORM_SIGNING_DIR for an isolated verification run.
EOF
}

[[ ${1:-} != --help ]] || { usage; exit 0; }
[[ $# -eq 3 ]] || { usage >&2; exit 2; }

candidate_dir=$(readlink -f "$1")
release_id=${2#sha256:}
output_dir=$3
signing_dir=${PLATFORM_SIGNING_DIR:-/var/lib/keplerops-platform/signing}
model_dir=$candidate_dir/model

[[ $release_id =~ ^[a-f0-9]{64}$ ]] || {
  echo "release ID must be a SHA-256 digest" >&2
  exit 2
}
for command in gzip jq openssl readlink sha256sum stat tar; do
  command -v "$command" >/dev/null || {
    echo "required command is unavailable: $command" >&2
    exit 2
  }
done
for file in config.json model.safetensors tokenizer.json model-card.md provenance.json; do
  [[ -s $model_dir/$file ]] || {
    echo "complete model package member is absent: $file" >&2
    exit 3
  }
done
for file in package-signing.key package-signing.pub; do
  [[ -s $signing_dir/$file ]] || {
    echo "model-package signing material is absent: $signing_dir/$file" >&2
    exit 3
  }
done

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
install -d -m 0750 "$output_dir"
install -d -m 0750 "$output_dir/members"
for file in config.json model.safetensors tokenizer.json model-card.md provenance.json; do
  install -m 0644 "$model_dir/$file" "$work/$file"
  install -m 0644 "$model_dir/$file" "$output_dir/members/$file"
done

members=$(for file in config.json model.safetensors tokenizer.json model-card.md provenance.json; do
  printf '%s\t%s\n' "$file" "$(sha256sum "$work/$file" | awk '{print $1}')"
done | jq -Rn '[inputs | split("\t") | {(.[0]): .[1]}] | add')
inventory=$(for file in config.json model.safetensors tokenizer.json model-card.md provenance.json; do
  printf '%s\t%s\t%s\n' "$file" \
    "$(sha256sum "$work/$file" | awk '{print $1}')" \
    "$(stat -c '%s' "$work/$file")"
done | jq -Rn '[inputs | split("\t") | {
  path:.[0],sha256:.[1],size:(.[2] | tonumber),
  object_key:("members/" + .[0]),role:(if .[0] == "model.safetensors" then "weights"
    elif .[0] == "config.json" then "configuration"
    elif .[0] == "tokenizer.json" then "tokenizer"
    elif .[0] == "model-card.md" then "documentation" else "provenance" end),
  media_type:(if .[0] == "model.safetensors" then "application/x-safetensors"
    elif (.[0] | endswith(".json")) then "application/json"
    else "text/markdown" end)}]')

tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
  -C "$work" -cf - config.json model.safetensors tokenizer.json model-card.md provenance.json |
  gzip -n >"$output_dir/orion-release-risk.tar.gz"
package_sha=$(sha256sum "$output_dir/orion-release-risk.tar.gz" | awk '{print $1}')
public_key_sha=$(sha256sum "$signing_dir/package-signing.pub" | awk '{print $1}')
mlflow_run_id=$(jq -er '.model.mlflow_run_id | select(test("^[a-f0-9]{32}$"))' \
  "$candidate_dir/candidate.json")
model_digest=$(jq -er '.model.native_weights_digest | select(test("^[a-f0-9]{64}$"))' \
  "$candidate_dir/candidate.json")
[[ $(sha256sum "$work/model.safetensors" | awk '{print $1}') == "$model_digest" ]] || {
  echo "candidate native-weights digest differs from model.safetensors" >&2
  exit 3
}

jq -nS \
  --arg package_sha "$package_sha" \
  --arg mlflow_run_id "$mlflow_run_id" \
  --arg release_id "sha256:$release_id" \
  --arg public_key_sha "$public_key_sha" \
  --arg model_digest "$model_digest" \
  --argjson members "$members" \
  --argjson inventory "$inventory" \
  '{schema:"keplerops.release-risk.package-manifest/v1",
    model_family:"release-risk",mlflow_run_id:$mlflow_run_id,
    release_id:$release_id,package_sha256:$package_sha,model_digest:$model_digest,
    package_format:"transformers-safetensors-tar-gzip",members:$members,
    inventory:$inventory,
    signing:{algorithm:"rsa-sha256",identity:"svc-orion-signer.platform.corp.keplerops.lab",
      public_key_sha256:$public_key_sha}}' \
  >"$output_dir/package-manifest.json"

openssl dgst -sha256 -sign "$signing_dir/package-signing.key" \
  -out "$output_dir/package-manifest.sig" "$output_dir/package-manifest.json"
openssl dgst -sha256 -verify "$signing_dir/package-signing.pub" \
  -signature "$output_dir/package-manifest.sig" "$output_dir/package-manifest.json" >/dev/null
install -m 0644 "$signing_dir/package-signing.pub" "$output_dir/package-manifest.pub"

printf 'model package ready: release=sha256:%s package=sha256:%s\n' \
  "$release_id" "$package_sha"
