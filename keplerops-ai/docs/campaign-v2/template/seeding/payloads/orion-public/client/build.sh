#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT
readonly BUILD_DIR="${1:-${ROOT}/build}"
readonly DIST_DIR="${2:-${ROOT}/dist}"
readonly VERSION=1.0.0
readonly VERSION_CODE=10000

: "${ANDROID_HOME:?ANDROID_HOME must name an Android SDK installation}"

build_tools="$(find "${ANDROID_HOME}/build-tools" -mindepth 1 -maxdepth 1 \
  -type d -printf '%f\n' | sort -V | tail -n1)"
[[ -n ${build_tools} ]] || { printf 'Android build tools are unavailable\n' >&2; exit 2; }
readonly TOOLS="${ANDROID_HOME}/build-tools/${build_tools}"
readonly ANDROID_JAR="${ANDROID_HOME}/platforms/android-35/android.jar"

for command in jar javac sha256sum; do
  command -v "${command}" >/dev/null || { printf 'missing command: %s\n' "${command}" >&2; exit 2; }
done
for command in aapt2 apksigner d8 zipalign; do
  [[ -x ${TOOLS}/${command} ]] || { printf 'missing Android tool: %s\n' "${command}" >&2; exit 2; }
done
[[ -r ${ANDROID_JAR} ]] || { printf 'missing Android API 35 platform\n' >&2; exit 2; }

rm -rf "${BUILD_DIR}" "${DIST_DIR}"
install -d "${BUILD_DIR}/classes" "${BUILD_DIR}/dex" "${DIST_DIR}"

mapfile -t java_sources < <(find "${ROOT}/client/src" -name '*.java' -type f | sort)
((${#java_sources[@]} > 0)) || { printf 'no Java sources found\n' >&2; exit 2; }

javac -encoding UTF-8 -source 11 -target 11 \
  -classpath "${ANDROID_JAR}" -d "${BUILD_DIR}/classes" \
  "${java_sources[@]}"
mapfile -t class_files < <(find "${BUILD_DIR}/classes" -name '*.class' -type f | sort)
"${TOOLS}/d8" --lib "${ANDROID_JAR}" --min-api 26 \
  --output "${BUILD_DIR}/dex" "${class_files[@]}"
touch --date='2026-07-15 00:00:00 UTC' "${BUILD_DIR}/dex/classes.dex"

"${TOOLS}/aapt2" link \
  -I "${ANDROID_JAR}" \
  --manifest "${ROOT}/client/AndroidManifest.xml" \
  --min-sdk-version 26 \
  --target-sdk-version 35 \
  --version-code "${VERSION_CODE}" \
  --version-name "${VERSION}" \
  -o "${BUILD_DIR}/orion-mobile-unaligned.apk"
jar uf "${BUILD_DIR}/orion-mobile-unaligned.apk" \
  -C "${BUILD_DIR}/dex" classes.dex
if [[ -d ${ROOT}/client/assets ]]; then
  jar uf "${BUILD_DIR}/orion-mobile-unaligned.apk" \
    -C "${ROOT}/client" assets
fi
"${TOOLS}/zipalign" -f 4 \
  "${BUILD_DIR}/orion-mobile-unaligned.apk" \
  "${BUILD_DIR}/orion-mobile-${VERSION}-unsigned.apk"

if [[ -n ${ORION_ANDROID_SIGNING_KEY:-} && -n ${ORION_ANDROID_SIGNING_CERT:-} ]]; then
  "${TOOLS}/apksigner" sign \
    --key "${ORION_ANDROID_SIGNING_KEY}" \
    --cert "${ORION_ANDROID_SIGNING_CERT}" \
    --min-sdk-version 26 \
    --v4-signing-enabled false \
    --out "${DIST_DIR}/orion-mobile-${VERSION}.apk" \
    "${BUILD_DIR}/orion-mobile-${VERSION}-unsigned.apk"
  "${TOOLS}/apksigner" verify --verbose --print-certs \
    "${DIST_DIR}/orion-mobile-${VERSION}.apk" >/dev/null
else
  cp "${BUILD_DIR}/orion-mobile-${VERSION}-unsigned.apk" \
    "${DIST_DIR}/orion-mobile-${VERSION}.apk"
fi

sha256sum "${BUILD_DIR}/orion-mobile-${VERSION}-unsigned.apk" | awk '{print $1}'
