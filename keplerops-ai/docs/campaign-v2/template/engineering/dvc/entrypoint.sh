#!/usr/bin/env sh
set -eu

if [ ! -d .dvc ]; then
  dvc init --no-scm
fi

dvc remote add --force --default lakefs s3://orion/main/dvc
dvc remote modify lakefs endpointurl "${DVC_LAKEFS_ENDPOINT:-http://lakefs:8000}"
dvc remote modify lakefs access_key_id "${LAKEFS_ACCESS_KEY_ID}"
dvc remote modify lakefs secret_access_key "${LAKEFS_SECRET_ACCESS_KEY}"

exec "$@"
