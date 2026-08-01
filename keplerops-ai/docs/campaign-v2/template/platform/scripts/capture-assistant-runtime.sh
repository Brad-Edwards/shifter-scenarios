#!/usr/bin/env bash
set -Eeuo pipefail
set +x
umask 027

readonly NAMESPACE="${ORION_PLATFORM_NAMESPACE:-orion-platform}"
readonly STATE_DIR="${PLATFORM_STATE_DIR:-/var/lib/keplerops-platform}"
readonly SIGNING_DIR="${PLATFORM_SIGNING_DIR:-${STATE_DIR}/signing}"
readonly OUTPUT_ROOT="${ASSISTANT_RELEASE_OUTPUT_DIR:-${STATE_DIR}/assistant-releases}"
readonly CURRENT_LINK="${STATE_DIR}/current-assistant-release"
readonly KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
readonly -a WORKLOADS=(vertex-openai-proxy litellm orion-agent orion-mcp)

export KUBECONFIG

fail() {
  printf 'capture-assistant-runtime: %s\n' "$*" >&2
  exit 1
}

digest_file() {
  sha256sum "$1" | awk '{print "sha256:" $1}'
}

canonical_digest() {
  local source=$1
  jq -cS . "${source}" | sha256sum | awk '{print "sha256:" $1}'
}

[[ ${EUID} -eq 0 ]] || fail 'must run as root on k3s01'
for command in awk chmod cmp cosign install jq kubectl ln mktemp mv rm sha256sum sort; do
  command -v "${command}" >/dev/null || fail "missing required command: ${command}"
done
for file in identity.json cosign.key cosign.pub cosign-password; do
  [[ -s ${SIGNING_DIR}/${file} ]] || fail "missing signing material: ${SIGNING_DIR}/${file}"
done

workdir="$(mktemp -d)"
staging=''
cleanup() {
  rm -rf "${workdir}"
  [[ -z ${staging} ]] || rm -rf "${staging}"
}
trap cleanup EXIT

printf '[]\n' >"${workdir}/workloads.json"
printf '[]\n' >"${workdir}/images.json"

for workload in "${WORKLOADS[@]}"; do
  deployment="${workdir}/${workload}.deployment.json"
  pods="${workdir}/${workload}.pods.json"

  kubectl -n "${NAMESPACE}" get deployment "${workload}" -o json >"${deployment}"
  jq -e '
    (.metadata.generation // 0) <= (.status.observedGeneration // -1) and
    (.spec.replicas // 1) > 0 and
    (.status.replicas // 0) == (.spec.replicas // 1) and
    (.status.updatedReplicas // 0) == (.spec.replicas // 1) and
    (.status.readyReplicas // 0) == (.spec.replicas // 1) and
    (.status.availableReplicas // 0) == (.spec.replicas // 1)
  ' "${deployment}" >/dev/null || fail "deployment ${workload} is not fully rolled out"

  selector="$(jq -er '
    .spec.selector.matchLabels | to_entries | sort_by(.key) |
    map("\(.key)=\(.value)") | join(",") | select(length > 0)
  ' "${deployment}")"
  kubectl -n "${NAMESPACE}" get pods -l "${selector}" -o json >"${pods}"
  jq -e --argjson expected "$(jq -r '.spec.replicas // 1' "${deployment}")" '
    (.items | length) == $expected and
    all(.items[];
      .status.phase == "Running" and
      any(.status.conditions[]?; .type == "Ready" and .status == "True") and
      (.status.containerStatuses | length) > 0 and
      all(.status.containerStatuses[]; .ready == true and (.imageID | length) > 0)
    )
  ' "${pods}" >/dev/null || fail "deployment ${workload} does not have exactly its ready running pods"

  spec_digest="$(jq -cS '.spec' "${deployment}" | sha256sum | awk '{print "sha256:" $1}')"
  jq -cn --arg name "${workload}" --arg digest "${spec_digest}" \
    '{name:$name, spec_digest:$digest}' >"${workdir}/workload-entry.json"
  jq -cS --slurpfile entry "${workdir}/workload-entry.json" \
    '. + $entry | sort_by(.name)' "${workdir}/workloads.json" >"${workdir}/workloads.next"
  mv "${workdir}/workloads.next" "${workdir}/workloads.json"

  jq -cS --arg workload "${workload}" '[
    .items[].status.containerStatuses[] |
    {workload:$workload, container:.name, declared_image:.image, running_image_id:.imageID}
  ] | unique_by([.workload, .container, .declared_image, .running_image_id])' \
    "${pods}" >"${workdir}/image-entries.json"
  jq -cS --slurpfile entries "${workdir}/image-entries.json" \
    '. + $entries[0] | sort_by(.workload, .container, .running_image_id)' \
    "${workdir}/images.json" >"${workdir}/images.next"
  mv "${workdir}/images.next" "${workdir}/images.json"
done

# Hash the canonical Kubernetes data representations. Secret values never enter
# the release record; the aggregate digest still binds their exact bytes.
kubectl -n "${NAMESPACE}" get configmap litellm-config -o json >"${workdir}/litellm-config.json"
kubectl -n "${NAMESPACE}" get secret litellm-runtime -o json >"${workdir}/litellm-secret.json"
jq -cS '.data // {}' "${workdir}/litellm-config.json" >"${workdir}/config-data.json"
jq -cS '.data // {}' "${workdir}/litellm-secret.json" >"${workdir}/secret-data.json"
configmap_digest="$(digest_file "${workdir}/config-data.json")"
secret_digest="$(digest_file "${workdir}/secret-data.json")"

secret_model="$(jq -er '.data.ORION_ASSISTANT_UPSTREAM_MODEL | @base64d | select(length > 0)' \
  "${workdir}/litellm-secret.json")"
secret_base_url="$(jq -er '.data.ORION_ASSISTANT_BASE_URL | @base64d | select(length > 0)' \
  "${workdir}/litellm-secret.json")"

# Read the environment of every live LiteLLM replica. This detects a Secret
# update that has not yet reached the running process without exposing values.
mapfile -t litellm_pods < <(jq -r '.items[].metadata.name' "${workdir}/litellm.pods.json" | sort)
for pod in "${litellm_pods[@]}"; do
  # These variables are expanded by the shell inside the LiteLLM container.
  # shellcheck disable=SC2016
  active_model="$(kubectl -n "${NAMESPACE}" exec "pod/${pod}" -c litellm -- \
    /bin/sh -c 'printf %s "$ORION_ASSISTANT_UPSTREAM_MODEL"')"
  # shellcheck disable=SC2016
  active_base_url="$(kubectl -n "${NAMESPACE}" exec "pod/${pod}" -c litellm -- \
    /bin/sh -c 'printf %s "$ORION_ASSISTANT_BASE_URL"')"
  [[ -n ${active_model} && -n ${active_base_url} ]] || fail 'active LiteLLM upstream identity is empty'
  [[ ${active_model} == "${secret_model}" && ${active_base_url} == "${secret_base_url}" ]] ||
    fail 'active LiteLLM upstream identity is stale relative to litellm-runtime'
done

routing_adapter='unspecified'
upstream_model="${secret_model}"
if [[ ${secret_model} == */* ]]; then
  routing_adapter="${secret_model%%/*}"
  upstream_model="${secret_model#*/}"
fi

provider="${routing_adapter}"
vertex_project=''
vertex_location=''
if [[ ${secret_base_url} == *vertex-openai-proxy* ]]; then
  provider='google-vertex-ai'
  vertex_project="$(jq -er '
    .spec.template.spec.containers[] | select(.name == "proxy") |
    .env[] | select(.name == "VERTEX_PROJECT") | .value | select(length > 0)
  ' "${workdir}/vertex-openai-proxy.deployment.json")"
  vertex_location="$(jq -er '
    .spec.template.spec.containers[] | select(.name == "proxy") |
    .env[] | select(.name == "VERTEX_LOCATION") | .value | select(length > 0)
  ' "${workdir}/vertex-openai-proxy.deployment.json")"
fi
endpoint_identity_digest="$(printf '%s' "${secret_base_url}" | sha256sum | awk '{print "sha256:" $1}')"

jq -nS \
  --arg provider "${provider}" \
  --arg routing_adapter "${routing_adapter}" \
  --arg model "${upstream_model}" \
  --arg configured_model "${secret_model}" \
  --arg endpoint_digest "${endpoint_identity_digest}" \
  --arg vertex_project "${vertex_project}" \
  --arg vertex_location "${vertex_location}" '
  {
    binding: "hosted-provider-model-identity",
    provider: $provider,
    routing_adapter: $routing_adapter,
    model: $model,
    configured_model: $configured_model,
    endpoint_identity_digest: $endpoint_digest
  }
  + if $vertex_project == "" then {} else {
      provider_scope: {project:$vertex_project, location:$vertex_location}
    } end
  ' >"${workdir}/model-identity.json"
model_identity_digest="$(canonical_digest "${workdir}/model-identity.json")"

kubectl -n "${NAMESPACE}" get networkpolicy -o json >"${workdir}/network-policies.raw.json"
jq -e '.items | length > 0' "${workdir}/network-policies.raw.json" >/dev/null ||
  fail "no NetworkPolicy protects namespace ${NAMESPACE}"
jq -cS '[.items[] | {name:.metadata.name, spec:.spec}] | sort_by(.name)' \
  "${workdir}/network-policies.raw.json" >"${workdir}/network-policies.json"

workload_spec_digest="$(canonical_digest "${workdir}/workloads.json")"
serving_image_digest="$(canonical_digest "${workdir}/images.json")"
policy_digest="$(canonical_digest "${workdir}/network-policies.json")"
jq -nS \
  --arg configmap "${configmap_digest}" \
  --arg secret "${secret_digest}" \
  '{configmap_digest:$configmap, secret_bytes_digest:$secret}' \
  >"${workdir}/configuration-digests.json"
config_digest="$(canonical_digest "${workdir}/configuration-digests.json")"
jq -nS \
  --arg workload "${workload_spec_digest}" \
  --arg config "${config_digest}" \
  --arg policy "${policy_digest}" \
  '{workload_spec_digest:$workload, config_digest:$config, policy_digest:$policy}' \
  >"${workdir}/policy-config.json"
policy_config_digest="$(canonical_digest "${workdir}/policy-config.json")"

signer_identity="$(jq -er '.identity | select(length > 0)' "${SIGNING_DIR}/identity.json")"
cosign_public_key_digest="$(digest_file "${SIGNING_DIR}/cosign.pub")"
declared_cosign_key_digest="$(jq -er '.cosign_public_key_digest | select(length > 0)' \
  "${SIGNING_DIR}/identity.json")"
[[ ${declared_cosign_key_digest} == "${cosign_public_key_digest}" ]] ||
  fail 'signer identity does not bind the active cosign public key'

jq -nS \
  --arg schema 'keplerops.assistant-runtime/v1' \
  --arg namespace "${NAMESPACE}" \
  --slurpfile model "${workdir}/model-identity.json" \
  --arg model_digest "${model_identity_digest}" \
  --slurpfile workloads "${workdir}/workloads.json" \
  --arg workload_digest "${workload_spec_digest}" \
  --slurpfile images "${workdir}/images.json" \
  --arg image_digest "${serving_image_digest}" \
  --arg configmap_digest "${configmap_digest}" \
  --arg secret_digest "${secret_digest}" \
  --arg config_digest "${config_digest}" \
  --slurpfile policies "${workdir}/network-policies.json" \
  --arg policy_digest "${policy_digest}" \
  --arg policy_config_digest "${policy_config_digest}" \
  --arg signer "${signer_identity}" \
  --arg cosign_key "${cosign_public_key_digest}" '
  {
    schema:$schema,
    namespace:$namespace,
    model_identity:($model[0] + {digest:$model_digest}),
    workloads:{items:$workloads[0], spec_digest:$workload_digest},
    serving_images:{items:$images[0], digest:$image_digest},
    configuration:{
      items:[
        {kind:"ConfigMap", name:"litellm-config", data_digest:$configmap_digest},
        {kind:"Secret", name:"litellm-runtime", secret_bytes_digest:$secret_digest}
      ],
      digest:$config_digest
    },
    policy:{kind:"NetworkPolicy", items:$policies[0], digest:$policy_digest},
    policy_config_digest:$policy_config_digest,
    signature:{
      signer_identity:$signer,
      cosign_public_key_digest:$cosign_key,
      transparency_status:"not-published"
    }
  }
  ' >"${workdir}/subject.json"
jq -cS . "${workdir}/subject.json" >"${workdir}/subject.canonical.json"
release_hex="$(sha256sum "${workdir}/subject.canonical.json" | awk '{print $1}')"
release_id="sha256:${release_hex}"
jq --arg release_id "${release_id}" '. + {release_id:$release_id}' \
  "${workdir}/subject.json" | jq -S . >"${workdir}/assistant-runtime.json"

jq -nS \
  --slurpfile predicate "${workdir}/assistant-runtime.json" \
  --arg release_sha "${release_hex}" \
  --arg model_sha "${model_identity_digest#sha256:}" \
  --arg image_sha "${serving_image_digest#sha256:}" '
  {
    _type:"https://in-toto.io/Statement/v1",
    subject:[
      {name:"keplerops-assistant-runtime", digest:{sha256:$release_sha}},
      {name:"hosted-assistant-model-identity", digest:{sha256:$model_sha}},
      {name:"assistant-serving-images", digest:{sha256:$image_sha}}
    ],
    predicateType:"https://keplerops.lab/attestations/assistant-runtime/v1",
    predicate:$predicate[0]
  }
  ' >"${workdir}/assistant-runtime.intoto.json"

install -d -m 0750 "${OUTPUT_ROOT}"
output="${OUTPUT_ROOT}/${release_hex}"
[[ ! -e ${output} || -d ${output} ]] || fail "release path is not a directory: ${output}"
if [[ -d ${output} ]]; then
  cmp -s "${workdir}/assistant-runtime.json" "${output}/assistant-runtime.json" ||
    fail "immutable release directory collision: ${output}"
  cmp -s "${workdir}/assistant-runtime.intoto.json" "${output}/assistant-runtime.intoto.json" ||
    fail "immutable attestation collision: ${output}"
  (cd "${output}" && sha256sum -c SHA256SUMS >/dev/null)
  cosign verify-blob --key "${output}/cosign.pub" --insecure-ignore-tlog \
    --bundle "${output}/assistant-runtime.sigstore.json" \
    "${output}/assistant-runtime.intoto.json" >/dev/null
else
  staging="$(mktemp -d "${OUTPUT_ROOT}/.${release_hex}.XXXXXX")"
  install -m 0644 "${workdir}/assistant-runtime.json" "${staging}/assistant-runtime.json"
  install -m 0644 "${workdir}/assistant-runtime.intoto.json" "${staging}/assistant-runtime.intoto.json"
  install -m 0644 "${SIGNING_DIR}/cosign.pub" "${staging}/cosign.pub"
  export COSIGN_PASSWORD
  COSIGN_PASSWORD="$(<"${SIGNING_DIR}/cosign-password")"
  cosign sign-blob --yes --tlog-upload=false \
    --key "${SIGNING_DIR}/cosign.key" \
    --bundle "${staging}/assistant-runtime.sigstore.json" \
    "${staging}/assistant-runtime.intoto.json" >/dev/null
  cosign verify-blob --key "${staging}/cosign.pub" --insecure-ignore-tlog \
    --bundle "${staging}/assistant-runtime.sigstore.json" \
    "${staging}/assistant-runtime.intoto.json" >/dev/null
  (
    cd "${staging}"
    sha256sum assistant-runtime.json assistant-runtime.intoto.json \
      assistant-runtime.sigstore.json cosign.pub >SHA256SUMS
    sha256sum -c SHA256SUMS >/dev/null
  )
  chmod 0644 "${staging}/assistant-runtime.sigstore.json" "${staging}/SHA256SUMS"
  mv "${staging}" "${output}"
  staging=''
fi

[[ ! -e ${CURRENT_LINK} || -L ${CURRENT_LINK} ]] ||
  fail "current assistant release path is not a symlink: ${CURRENT_LINK}"
ln -sfn "assistant-releases/${release_hex}" "${CURRENT_LINK}"

printf 'release_id=%s\n' "${release_id}"
printf 'model_identity_digest=%s\n' "${model_identity_digest}"
printf 'serving_image_digest=%s\n' "${serving_image_digest}"
printf 'policy_digest=%s\n' "${policy_digest}"
printf 'config_digest=%s\n' "${config_digest}"
printf 'policy_config_digest=%s\n' "${policy_config_digest}"
