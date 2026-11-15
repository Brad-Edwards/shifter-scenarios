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
aws_client() {
  docker run --rm --network cinder-keplerops-foundation-data --read-only \
    --user 0:0 --cap-drop ALL --security-opt no-new-privileges:true --tmpfs /tmp \
    --env AWS_SHARED_CREDENTIALS_FILE=/run/aws/credentials --env AWS_DEFAULT_REGION=us-east-1 \
    --mount "type=bind,source=$operator/native-platform/aws-admin,target=/run/aws/credentials,readonly" \
    --mount "type=bind,source=$exports,target=/exports,readonly" \
    --mount "type=bind,source=$collections,target=/collections,readonly" \
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
touch "$marker"
echo 'Native company backup and retained collection stored in S3.'
