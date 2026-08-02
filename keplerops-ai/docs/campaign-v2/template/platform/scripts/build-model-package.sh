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
for command in gzip jq openssl readlink sha256sum tar; do
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
for file in config.json model.safetensors tokenizer.json model-card.md provenance.json; do
  install -m 0644 "$model_dir/$file" "$work/$file"
done

members=$(for file in config.json model.safetensors tokenizer.json model-card.md provenance.json; do
  printf '%s\t%s\n' "$file" "$(sha256sum "$work/$file" | awk '{print $1}')"
done | jq -Rn '[inputs | split("\t") | {(.[0]): .[1]}] | add')

tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
  -C "$work" -cf - config.json model.safetensors tokenizer.json model-card.md provenance.json |
  gzip -n >"$output_dir/orion-release-risk.tar.gz"
package_sha=$(sha256sum "$output_dir/orion-release-risk.tar.gz" | awk '{print $1}')
public_key_sha=$(sha256sum "$signing_dir/package-signing.pub" | awk '{print $1}')
mlflow_run_id=$(jq -er '.model.mlflow_run_id | select(test("^[a-f0-9]{32}$"))' \
  "$candidate_dir/candidate.json")

jq -nS \
  --arg package_sha "$package_sha" \
  --arg mlflow_run_id "$mlflow_run_id" \
  --arg release_id "sha256:$release_id" \
  --arg public_key_sha "$public_key_sha" \
  --argjson members "$members" \
  '{schema:"keplerops.release-risk.package-manifest/v1",
    model_family:"release-risk",mlflow_run_id:$mlflow_run_id,
    release_id:$release_id,package_sha256:$package_sha,members:$members,
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
