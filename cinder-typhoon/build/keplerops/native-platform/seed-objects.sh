#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
operator=$(realpath "${KEPLEROPS_OPERATOR_DIR:-./.operator}")
marker="$operator/native-platform/objects-company-seeded-v2"
if [[ -e $marker ]]; then
  echo 'Native company object state retained.'
  exit 0
fi
exports="$operator/native-platform/exports"
collections="$ROOT/../../assets/keplerops/opening/k-dev"
mkdir -p "$exports"
if [[ ! -f $exports/company-history.dump ]]; then
  docker compose exec -T fieldlink-postgres sh -ec \
    'exec pg_dump -U "$POSTGRES_USER" --dbname=fieldlink_data --schema=support --format=custom' \
    >"$exports/company-history.dump.part"
  mv "$exports/company-history.dump.part" "$exports/company-history.dump"
fi
workspaces="$ROOT/../../assets/keplerops/registry/workspaces"
aws_client() {
  docker run --rm --network cinder-keplerops-foundation-data --read-only \
    --user 0:0 --cap-drop ALL --security-opt no-new-privileges:true --tmpfs /tmp \
    --env AWS_SHARED_CREDENTIALS_FILE=/run/aws/credentials --env AWS_DEFAULT_REGION=us-east-1 \
    --mount "type=bind,source=$operator/native-platform/aws-admin,target=/run/aws/credentials,readonly" \
    --mount "type=bind,source=$exports,target=/exports,readonly" \
    --mount "type=bind,source=$collections,target=/collections,readonly" \
    --mount "type=bind,source=$workspaces,target=/workspaces,readonly" \
    --entrypoint aws cinder-keplerops/k-dev:hand-build \
    --endpoint-url http://fieldlink-objects:8333 "$@"
}
if ! aws_client s3api head-bucket --bucket fieldlink-exports >/dev/null 2>&1; then
  aws_client s3api create-bucket --bucket fieldlink-exports >/dev/null
fi
aws_client s3api put-bucket-versioning --bucket fieldlink-exports --versioning-configuration Status=Enabled
aws_client s3 cp /exports/company-history.dump s3://fieldlink-exports/backups/company-history.dump >/dev/null
if ! aws_client s3api head-bucket --bucket fieldlink-collections >/dev/null 2>&1; then
  aws_client s3api create-bucket --bucket fieldlink-collections >/dev/null
fi
aws_client s3 cp /collections/FKCOL-2841.json s3://fieldlink-collections/callbacks/CB-17/FKCOL-2841.json >/dev/null
# K13.1: seed fieldkest-workspaces with an over-broad anonymous read ACL.
# The notebook key has two versions: v1 contains the TEN-ARWC customer reference
# (K13.2), v2 is the corrected current version. The handover.json (K13.3) is in
# a separate prefix. The anonymous ACL (from s3.json) is the K13.1 vulnerability.
if ! aws_client s3api head-bucket --bucket fieldkest-workspaces >/dev/null 2>&1; then
  aws_client s3api create-bucket --bucket fieldkest-workspaces >/dev/null
fi
aws_client s3api put-bucket-versioning --bucket fieldkest-workspaces \
  --versioning-configuration Status=Enabled >/dev/null
# Seed v1 of the notebook (the superseded version containing TEN-ARWC customer note)
aws_client s3 cp /workspaces/deploy-2026-09-v1.json \
  s3://fieldkest-workspaces/notebooks/deploy-2026-09.json >/dev/null
# Seed v2 of the notebook (the corrected current version)
aws_client s3 cp /workspaces/deploy-2026-09-v2.json \
  s3://fieldkest-workspaces/notebooks/deploy-2026-09.json >/dev/null
# Seed the handover object
aws_client s3 cp /workspaces/handover.json \
  s3://fieldkest-workspaces/exports/EXP-2841/handover.json >/dev/null
touch "$marker"
echo 'Native company backup and retained collection stored in S3.'
