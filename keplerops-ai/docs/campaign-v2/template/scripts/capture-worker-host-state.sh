#!/usr/bin/env bash
set -Eeuo pipefail

readonly KEY=${KEPLEROPS_V2_SSH_KEY:-/root/.ssh/keplerops-v2}
readonly SSH=(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
readonly DC01=${KEPLEROPS_DC01_ADDRESS:-192.168.78.10}
readonly K3S01=${KEPLEROPS_K3S01_ADDRESS:-192.168.78.30}

for command in jq sha256sum ssh; do
  command -v "$command" >/dev/null || {
    printf 'missing required command: %s\n' "$command" >&2
    exit 2
  }
done
[[ -r $KEY ]] || { printf 'SSH key is unreadable: %s\n' "$KEY" >&2; exit 2; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

timeout 90 "${SSH[@]}" "kepler@${DC01}" sudo bash -s >"$work/directory" <<'REMOTE'
set -Eeuo pipefail
mapfile -t users < <(samba-tool user list | grep -Ev '\$$' | LC_ALL=C sort)
for user in "${users[@]}"; do
  printf 'user:%s\n' "$user"
  samba-tool user show "$user" | awk -F ': ' '
    $1 == "dn" || $1 == "objectGUID" || $1 == "objectSid" ||
    $1 == "sAMAccountName" || $1 == "primaryGroupID" || $1 == "memberOf" {
      print tolower($1) "=" $2
    }
  ' | LC_ALL=C sort
done
mapfile -t groups < <(samba-tool group list | LC_ALL=C sort)
for group in "${groups[@]}"; do
  printf 'group:%s\n' "$group"
  samba-tool group listmembers "$group" | LC_ALL=C sort
done
REMOTE
directory_sha=$(sha256sum "$work/directory" | awk '{print $1}')

timeout 60 "${SSH[@]}" "kepler@${K3S01}" \
  'sudo k3s kubectl -n argocd get application orion-canary -o json' \
  >"$work/argocd.json"
timeout 60 "${SSH[@]}" "kepler@${K3S01}" \
  'sudo k3s kubectl -n orion-runtime get inferenceservice orion-release-risk -o json' \
  >"$work/runtime.json"
timeout 90 "${SSH[@]}" "kepler@${K3S01}" sudo bash -s >"$work/releases" <<'REMOTE'
set -Eeuo pipefail
root=/var/lib/keplerops-platform/releases
[[ -d $root ]]
find "$root" -mindepth 2 -type f -print0 |
  LC_ALL=C sort -z |
  while IFS= read -r -d '' file; do
    printf '%s  %s\n' "$(sha256sum "$file" | awk '{print $1}')" "${file#"$root"/}"
  done
REMOTE
[[ -s $work/releases ]] || {
  echo 'no immutable Orion release bundle is present on k3s01' >&2
  exit 3
}
release_bundle_sha=$(sha256sum "$work/releases" | awk '{print $1}')

jq -n \
  --arg directory_sha256 "$directory_sha" \
  --arg release_bundle_sha256 "$release_bundle_sha" \
  --slurpfile argocd "$work/argocd.json" \
  --slurpfile runtime "$work/runtime.json" '
  def required($value; $name):
    if ($value == null or $value == "") then error("missing " + $name) else $value end;
  {
    directory_sha256: $directory_sha256,
    gitops: {
      repository: required($argocd[0].spec.source.repoURL; "Argo repository"),
      path: required($argocd[0].spec.source.path; "Argo path"),
      target_revision: required($argocd[0].spec.source.targetRevision; "Argo target revision"),
      configured_revision: required(
        $argocd[0].metadata.annotations["keplerops.lab/configured-revision"];
        "Argo configured revision"
      ),
      synced_revision: required($argocd[0].status.sync.revision; "Argo synced revision")
    },
    runtime: {
      release_id: required(
        $runtime[0].metadata.annotations["keplerops.lab/release-revision"];
        "runtime release ID"
      ),
      model_digest: required(
        $runtime[0].metadata.annotations["keplerops.lab/model-digest"];
        "runtime model digest"
      ),
      image: required(
        $runtime[0].spec.predictor.containers[0].image;
        "runtime image"
      )
    },
    release_bundle_sha256: $release_bundle_sha256
  }
  | select(.gitops.target_revision == .gitops.configured_revision)
  | select(.gitops.target_revision == .gitops.synced_revision)
  | select(.gitops.target_revision | test("^[a-fA-F0-9]{40}([a-fA-F0-9]{24})?$"))
  | select(.runtime.release_id | test("^sha256:[a-f0-9]{64}$"))
  | select(.runtime.model_digest | test("^sha256:[a-f0-9]{64}$"))
  | select(.runtime.image | test("@sha256:[a-f0-9]{64}$"))
  ' | jq -eS .
