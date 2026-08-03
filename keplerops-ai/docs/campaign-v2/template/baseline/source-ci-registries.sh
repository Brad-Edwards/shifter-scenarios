#!/usr/bin/env bash

set -Eeuo pipefail

readonly FORGEJO_URL="${FORGEJO_URL:-http://10.61.40.20:3000}"
readonly FORGEJO_API_URL="${FORGEJO_URL}/api/v1"
readonly FORGEJO_AUTH="${FORGEJO_AUTH:-range-admin:KeplerV2-Training-Forgejo-Admin}"
readonly BUILD_REPOSITORY=keplerops/orion-build
readonly PUBLIC_REPOSITORY=keplerops/orion-public
readonly WORKFLOW=orion-public-release.yml
readonly VERSION=1.0.0
readonly TAG="v${VERSION}"
readonly ANDROID_SDK_IMAGE=ghcr.io/cirruslabs/android-sdk@sha256:54e4ef10f19c211052851736dfb783ee26935a089b06bb1f9019a311cdc38af0

for command in awk base64 cmp curl docker find git grep head jq mktemp openssl \
  python3 seq sha256sum sleep sort stat tail unzip; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done

api() {
  local method=$1
  local path=$2
  shift 2
  curl --silent --show-error --fail-with-body \
    --user "${FORGEJO_AUTH}" --request "${method}" "$@" \
    "${FORGEJO_API_URL}${path}"
}

download_forgejo_asset() {
  local url=$1
  local output=$2
  case "${url}" in
    https://git.keplerops.lab/*)
      url="${FORGEJO_URL%/}/${url#https://git.keplerops.lab/}"
      ;;
  esac
  curl -fsS --user "${FORGEJO_AUTH}" "${url}" -o "${output}"
}

branch_revision() {
  api GET "/repos/$1/branches/main" | jq -er '.commit.id'
}

build_revision="$(branch_revision "${BUILD_REPOSITORY}")"
public_revision="$(branch_revision "${PUBLIC_REPOSITORY}")"

latest_matching_run() {
  api GET "/repos/${BUILD_REPOSITORY}/actions/tasks?limit=50" | jq -c \
    --arg workflow "${WORKFLOW}" \
    --arg revision "${build_revision}" '
      [.workflow_runs[]
        | select(.workflow_id == $workflow and .head_sha == $revision)]
      | max_by(.id) // empty
    '
}

run="$(latest_matching_run)"
if [[ -z ${run} ]] || ! jq -e '.status == "success"' <<<"${run}" >/dev/null; then
  if [[ -z ${run} ]] || jq -e '.status | IN("failure", "cancelled", "skipped")' \
      <<<"${run}" >/dev/null; then
    dispatch="$(api POST "/repos/${BUILD_REPOSITORY}/actions/workflows/${WORKFLOW}/dispatches" \
      --header 'Content-Type: application/json' \
      --data '{"ref":"main","inputs":{},"return_run_info":true}')"
    jq -e '.id > 0 and (.jobs | index("release")) != null' <<<"${dispatch}" >/dev/null
  fi

  for _ in $(seq 1 240); do
    sleep 5
    run="$(latest_matching_run)"
    [[ -n ${run} ]] || continue
    status="$(jq -er '.status' <<<"${run}")"
    [[ ${status} == success ]] && break
    if [[ ${status} == failure || ${status} == cancelled || ${status} == skipped ]]; then
      printf 'Orion public release workflow ended with status %s\n' "${status}" >&2
      exit 2
    fi
  done
fi

if [[ -z ${run} ]] || ! jq -e \
    --arg revision "${build_revision}" \
    --arg workflow "${WORKFLOW}" '
      .status == "success"
      and .head_branch == "main"
      and .head_sha == $revision
      and .workflow_id == $workflow
    ' <<<"${run}" >/dev/null; then
    printf 'Orion public release workflow did not complete successfully\n' >&2
    exit 2
fi
run_number="$(jq -er '.run_number' <<<"${run}")"

release="$(api GET "/repos/${PUBLIC_REPOSITORY}/releases/tags/${TAG}")"
[[ $(jq -er '.tag_name' <<<"${release}") == "${TAG}" ]] || {
  printf 'unexpected Orion release tag\n' >&2
  exit 3
}

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT
while IFS=$'\t' read -r name url; do
  [[ ${name} =~ ^[A-Za-z0-9._-]+$ ]] || {
    printf 'unsafe release asset name: %s\n' "${name}" >&2
    exit 3
  }
  download_forgejo_asset "${url}" "${workdir}/${name}"
done < <(jq -r '.assets[] | [.name,.browser_download_url] | @tsv' <<<"${release}")

expected_assets="$({
  printf '%s\n' \
    LICENSE \
    MODEL_CARD.md \
    RELEASE_NOTES.md \
    TECHNICAL_REPORT.md \
    com.keplerops.orion.yml \
    cosign.pub \
    "orion-mobile-${VERSION}.apk" \
    "orion-mobile-${VERSION}.cdx.json" \
    orion-mobile-signing-cert.pem \
    orion-release-risk-evidence.json \
    release-manifest.json \
    release-manifest.sig
} | sort)"
actual_assets="$(find "${workdir}" -mindepth 1 -maxdepth 1 -type f -printf '%f\n' | sort)"
[[ ${actual_assets} == "${expected_assets}" ]] || {
  printf 'Orion release asset set differs from the publication contract\n' >&2
  exit 3
}

manifest="${workdir}/release-manifest.json"
evidence="${workdir}/orion-release-risk-evidence.json"
jq -e \
  --arg source_revision "${public_revision}" \
  --arg workflow_revision "${build_revision}" \
  --slurpfile evidence "${evidence}" '
    .schema == "keplerops.orion-public-release/v2"
    and .version == "1.0.0"
    and .source.repository == "keplerops/orion-public"
    and .source.revision == $source_revision
    and .workflow.repository == "keplerops/orion-build"
    and .workflow.revision == $workflow_revision
    and .product == {
      api_origin:"https://preview.keplerops.lab/",
      api_path:"/api/analyze",
      classes:["ReleaseApprove","ReleaseHold","PartnerIntake",
        "EntitlementReview","SecurityAdvisory","SupportEscalation",
        "ResearchReview","PrivacySafety"],
      model_family:"release-risk",
      name:"Orion Release Risk",
      runtime:"onnxruntime-cpu",
      service:"orion-release-risk"
    }
    and .model == $evidence[0].model
    and .evaluation == $evidence[0].evaluation
    and (.build.package == "com.keplerops.orion")
    and (.build.android_api == 35)
    and (.build.minimum_android_api == 26)
    and (.artifacts | length == 9)
    and any(.artifacts[]; .name == "orion-release-risk-evidence.json"
      and .role == "model-release-evidence")
  ' "${manifest}" >/dev/null

jq -e '
  .schema == "keplerops.orion-release-risk.evidence/v1"
  and (.generated_at | type == "string" and length > 0)
  and (.source.revision | test("^[0-9a-f]{40}([0-9a-f]{24})?$"))
  and .service == {
    classes:["ReleaseApprove","ReleaseHold","PartnerIntake",
      "EntitlementReview","SecurityAdvisory","SupportEscalation",
      "ResearchReview","PrivacySafety"],
    model_family:"release-risk",
    name:"orion-release-risk",
    runtime:"onnxruntime-cpu"
  }
  and (.model.platform_release_id | test("^sha256:[0-9a-f]{64}$"))
  and (.model.runtime_revision | type == "string" and length > 0)
  and (.model.mlflow_run_id | type == "string" and length > 0)
  and (.model.mlflow_model_version | type == "string" and length > 0)
  and all([
    .model.onnx_sha256,
    .model.tokenizer_sha256,
    .model.label_schema_sha256,
    .model.serving_image_sha256,
    .evaluation.suite_sha256,
    .evaluation.report_sha256
  ][]; test("^sha256:[0-9a-f]{64}$"))
  and (.evaluation.records | type == "number" and floor == . and . > 0)
  and (.evaluation.correct | type == "number" and floor == . and . >= 0)
  and .evaluation.correct <= .evaluation.records
  and .evaluation.accuracy == (.evaluation.correct / .evaluation.records)
  and .evaluation.accuracy >= .evaluation.minimum_accuracy
  and .evaluation.decision == "accepted"
  and (.evaluation.per_class_accuracy | keys) == [
    "EntitlementReview","PartnerIntake","PrivacySafety","ReleaseApprove",
    "ReleaseHold","ResearchReview","SecurityAdvisory","SupportEscalation"
  ]
  and all(.evaluation.per_class_accuracy[]; type == "number" and . >= 0 and . <= 1)
' "${evidence}" >/dev/null

while IFS=$'\t' read -r name expected size; do
  [[ -f ${workdir}/${name} ]] || { printf 'manifest artifact is absent: %s\n' "${name}" >&2; exit 4; }
  actual="$(sha256sum "${workdir}/${name}" | awk '{print $1}')"
  [[ ${actual} == "${expected}" ]] || { printf 'artifact digest mismatch: %s\n' "${name}" >&2; exit 4; }
  [[ $(stat -c %s "${workdir}/${name}") == "${size}" ]] || {
    printf 'artifact size mismatch: %s\n' "${name}" >&2
    exit 4
  }
done < <(jq -r '.artifacts[] | [.name,.sha256,.size] | @tsv' "${manifest}")

base64 -d <"${workdir}/release-manifest.sig" >"${workdir}/release-manifest.signature.bin"
openssl dgst -sha256 -verify "${workdir}/cosign.pub" \
  -signature "${workdir}/release-manifest.signature.bin" "${manifest}" >/dev/null

cert_digest="$(openssl x509 -in "${workdir}/orion-mobile-signing-cert.pem" \
  -outform DER | sha256sum | awk '{print $1}')"
[[ ${cert_digest} == "$(jq -er '.android_signing.certificate_sha256' "${manifest}")" ]] || {
  printf 'Android signing certificate is not bound by the manifest\n' >&2
  exit 5
}
apk_verify="$(docker run --rm -v "${workdir}:/release:ro" "${ANDROID_SDK_IMAGE}" \
  /opt/android-sdk-linux/build-tools/35.0.0/apksigner verify \
  --verbose --print-certs "/release/orion-mobile-${VERSION}.apk")"
grep -q '^Verified using v2 scheme (APK Signature Scheme v2): true$' <<<"${apk_verify}"
grep -q '^Verified using v3 scheme (APK Signature Scheme v3): true$' <<<"${apk_verify}"
grep -qi "certificate SHA-256 digest: ${cert_digest}" <<<"${apk_verify}"

sbom="${workdir}/orion-mobile-${VERSION}.cdx.json"
jq -e \
  --arg revision "${public_revision}" '
    .bomFormat == "CycloneDX"
    and .specVersion == "1.6"
    and .metadata.component.name == "Orion Release Risk Mobile"
    and .metadata.component.version == "1.0.0"
    and any(.metadata.component.properties[];
      .name == "keplerops:source-revision" and .value == $revision)
    and (.components | length > 5)
    and all(.components[];
      .type == "file" and (.hashes | length == 1)
      and .hashes[0].alg == "SHA-256"
      and (.hashes[0].content | test("^[0-9a-f]{64}$")))
  ' "${sbom}" >/dev/null

grep -q '^# Orion Release Risk Model Card$' "${workdir}/MODEL_CARD.md"
grep -q '^# Orion Release Risk Mobile: Public Client And Release Evidence$' \
  "${workdir}/TECHNICAL_REPORT.md"
grep -q '^License: Apache-2.0$' "${workdir}/com.keplerops.orion.yml"
for value in \
  "$(jq -er '.model.runtime_revision' "${evidence}")" \
  "$(jq -er '.model.mlflow_model_version' "${evidence}")" \
  "$(jq -er '.model.onnx_sha256' "${evidence}")" \
  "$(jq -er '.evaluation.report_sha256' "${evidence}")"; do
  grep -Fq "${value}" "${workdir}/MODEL_CARD.md"
  grep -Fq "${value}" "${workdir}/TECHNICAL_REPORT.md"
done
for value in \
  "$(jq -er '.model.runtime_revision' "${evidence}")" \
  "$(jq -er '.model.mlflow_model_version' "${evidence}")" \
  "$(jq -er '.model.onnx_sha256' "${evidence}")"; do
  grep -Fq "${value}" "${workdir}/RELEASE_NOTES.md"
done
for file in MODEL_CARD.md RELEASE_NOTES.md TECHNICAL_REPORT.md; do
  grep -Fq "\`onnxruntime-cpu\`" "${workdir}/${file}"
  grep -Fq "\`PrivacySafety\`" "${workdir}/${file}"
done

runtime_metadata="$(curl -fsS \
  http://192.168.78.30:30083/v1/models/orion-release-risk)"
jq -e --argjson runtime "${runtime_metadata}" '
  def bare: sub("^sha256:"; "");
  $runtime.name == "orion-release-risk"
  and $runtime.ready == true
  and $runtime.model_family == "release-risk"
  and $runtime.runtime == "onnxruntime-cpu"
  and $runtime.class_count == 8
  and ($runtime.labels | sort) == (.service.classes | sort)
  and $runtime.model_sha256 == (.model.onnx_sha256 | bare)
  and $runtime.tokenizer_sha256 == (.model.tokenizer_sha256 | bare)
  and $runtime.mlflow_run_id == .model.mlflow_run_id
  and $runtime.mlflow_model_version == .model.mlflow_model_version
' "${evidence}" >/dev/null

git -C "${workdir}" init source >/dev/null
git -C "${workdir}/source" remote add origin \
  "http://${FORGEJO_AUTH}@10.61.40.20:3000/${PUBLIC_REPOSITORY}.git"
git -C "${workdir}/source" fetch --quiet --depth 1 origin "${public_revision}"
git -C "${workdir}/source" checkout --quiet --detach FETCH_HEAD
python3 "${workdir}/source/ci/prepare-client.py" \
  --root "${workdir}/source" \
  --source-revision "${public_revision}" \
  --source-tag "${TAG}"
cmp "${workdir}/source/com.keplerops.orion-1.0.0.cdx.json" "${sbom}"
rebuilt_unsigned="$(docker run --rm \
  -v "${workdir}/source:/workspace:ro" \
  "${ANDROID_SDK_IMAGE}" \
  bash /workspace/client/build.sh /tmp/orion-build /tmp/orion-dist | tail -n1)"
recorded_unsigned="$(jq -er '.build.unsigned_apk_sha256' "${manifest}")"
if [[ ${rebuilt_unsigned} != "${recorded_unsigned}" ]]; then
  printf 'warning: public source unsigned APK digest differs from recorded release metadata: rebuilt=%s recorded=%s\n' \
    "${rebuilt_unsigned}" "${recorded_unsigned}" >&2
fi
grep -q 'https://preview.keplerops.lab/' \
  "${workdir}/source/client/src/com/keplerops/orion/MainActivity.java"
grep -q 'MODEL_FAMILY = "release-risk"' \
  "${workdir}/source/client/src/com/keplerops/orion/MainActivity.java"
grep -q 'MODEL_SERVICE = "orion-release-risk"' \
  "${workdir}/source/client/src/com/keplerops/orion/MainActivity.java"
grep -q 'setJavaScriptEnabled(true)' \
  "${workdir}/source/client/src/com/keplerops/orion/MainActivity.java"
grep -q '"preview.keplerops.lab".equals(uri.getHost())' \
  "${workdir}/source/client/src/com/keplerops/orion/MainActivity.java"
unzip -p "${workdir}/orion-mobile-${VERSION}.apk" \
  assets/provenance/release.json >"${workdir}/apk-release-provenance.json"
jq -e \
  --arg revision "${public_revision}" \
  --arg sbom_digest "$(sha256sum "${sbom}" | awk '{print $1}')" '
    .schema == "keplerops.orion-mobile.provenance/v1"
    and .source.repository == "keplerops/orion-public"
    and .source.revision == $revision
    and .source.tag == "v1.0.0"
    and .api_origin == "https://preview.keplerops.lab/"
    and .api_path == "/api/analyze"
    and .sbom.format == "CycloneDX 1.6"
    and .sbom.name == "com.keplerops.orion-1.0.0.cdx.json"
    and .sbom.sha256 == $sbom_digest
  ' "${workdir}/apk-release-provenance.json" >/dev/null

printf 'Orion public release passed: run=%s workflow=%s source=%s apk=%s\n' \
  "${run_number}" "${build_revision}" "${public_revision}" \
  "$(sha256sum "${workdir}/orion-mobile-${VERSION}.apk" | awk '{print $1}')"
