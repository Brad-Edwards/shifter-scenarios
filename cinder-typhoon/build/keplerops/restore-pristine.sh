#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
[[ $EUID == 0 && $(hostname) == cinder-fieldlink-dev && $ROOT == /opt/cinder-typhoon/build/keplerops ]] || {
  echo 'Native reset is restricted to the isolated FieldLink development VM.' >&2
  exit 1
}
project=$(curl --fail --silent --show-error --header 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/project/project-id)
[[ $project == prod-mgau4w ]] || { echo 'Unexpected development project.' >&2; exit 1; }
# Reuse the development peer binding even for direct invocation or a caller
# environment override. Never fall back to the preserved golden peer.
export ARWC_CARRIER_ADDRESS=10.77.59.11
operator=${KEPLEROPS_OPERATOR_DIR:-"$ROOT/.operator"}
# A verified private backup and a released QA window are prerequisites. This
# explicit reset destroys application volumes; ordinary startup never does.
docker compose down --volumes --remove-orphans
rm -f -- "$operator/native-platform/assistant-company-seeded" \
  "$operator/native-platform/assistant-k21-seeded" \
  "$operator/native-platform/assistant-k21-config.json" \
  "$operator/native-ci/k06-ci-seeded" \
  "$operator/native-platform/objects-company-seeded" \
  "$operator/native-platform/objects-company-seeded-v2" \
  "$operator/native-platform/exports/company-history.dump" \
  "$operator/native-platform/exports/company-history.dump.part" \
  "$operator/native-platform/kubernetes/rowan.yaml" \
  "$operator/native-platform/kubernetes/cluster-identity"
if [[ -d $operator/native-platform/assistant-documents ]]; then
  find "$operator/native-platform/assistant-documents" -mindepth 1 -maxdepth 1 -type f -delete
fi
bash generate-operator-material.sh
bash native-platform/fetch-kubernetes-images.sh
# Initialize databases before dependent applications, and native workspace
# credentials before the missing-only desktop profile seed is started.
docker compose up -d --no-deps --wait --wait-timeout 120 router fieldlink-dns fieldlink-edge fieldlink-postgres
python3 native-platform/host-routing.py
bash native-workplace/bootstrap-databases.sh
bash native-platform/bootstrap-data.sh
bash native-platform/bootstrap-kubernetes.sh
docker compose up -d --no-deps --wait --wait-timeout 180 \
  runner k-source k-registry k-ci fieldlink-review k-preview k-support k-indexer \
  k-identity fieldlink-keycloak k-cert fieldlink-objects fieldlink-ollama a-connector
docker inspect --format '{{range .HostConfig.ExtraHosts}}{{println .}}{{end}}' cinder-keplerops-connector | grep -Fxq 'fieldlink.arwc.test:10.77.59.11'
bash native-workplace/bootstrap-staff.sh
bash native-workplace/bootstrap-support.sh
docker compose up -d --wait --wait-timeout 180 fieldlink-assistant
bash native-platform/import-model.sh
bash native-platform/cache-embedder.sh
python3 native-platform/seed-assistant.py --operator-dir "$operator"
python3 native-platform/seed-k21-assistant.py --operator-dir "$operator"
python3 native-ci/seed-k06-ci.py --operator-dir "$operator"
bash native-platform/seed-objects.sh
docker compose up --no-deps --force-recreate k-dev-seed
docker compose up -d --no-deps k-dev
python3 ../development-ranges/guest/fieldlink-desktop-login.py

docker compose exec -T --user fieldkest-support k-support python3 -c \
  'import json; from pathlib import Path; p=Path("/var/lib/fieldkest-support/audit/extended-state.json"); assert not p.exists() or json.loads(p.read_text()).get("diagnostics") == {}'
echo 'Native FieldLink application state initialized.'
