#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT
readonly TARGET="${ROOT}/state/campaign-start/airflow-dags"

install -d -m 0755 "${TARGET}"
find "${TARGET}" -mindepth 1 -maxdepth 1 -type f -name '*.py' -delete
find "${ROOT}/engineering/airflow/dags" -mindepth 1 -maxdepth 1 -type f -name '*.py' \
  -exec cp --preserve=mode,timestamps {} "${TARGET}/" \;
find "${ROOT}/campaign-start/modules" -mindepth 3 -maxdepth 3 -type f \
  -path '*/dags/*.py' -exec cp --preserve=mode,timestamps {} "${TARGET}/" \;

while IFS= read -r source; do
  [[ -f ${ROOT}/${source#./} ]] || {
    printf 'campaign Airflow DAG source is unavailable: %s\n' "${source}" >&2
    exit 1
  }
  cp --preserve=mode,timestamps "${ROOT}/${source#./}" "${TARGET}/"
done < <(
  awk -F: '
    /:\/opt\/airflow\/dags\/[^:]+:ro$/ {
      source=$1
      sub(/^[[:space:]]*-[[:space:]]*/, "", source)
      print source
    }
  ' "${ROOT}"/campaign-start/modules/m??/compose.overlay.yaml | sort -u
)

find "${TARGET}" -mindepth 1 -maxdepth 1 -type f -name '*.py' -exec chmod 0644 {} +
