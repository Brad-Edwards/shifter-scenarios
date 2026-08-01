#!/usr/bin/env bash
set -euo pipefail

readonly CONTAINER=kep-v2-stalwart
readonly ADMIN_USER=range-admin
readonly ADMIN_SECRET_HASH='$6$keplerops$03o.soEaGTag6lmbqkXBqPyYP.yoXaeYpEA1s3WaOQfwbdlmFvzwYD.AZ5Lw4Eqco4E5SLJr9BaG2Leejt6CX.'

deadline=$((SECONDS + 120))
until docker exec "$CONTAINER" test -f /opt/stalwart/etc/config.toml 2>/dev/null; do
  if ((SECONDS >= deadline)); then
    echo "Stalwart did not initialize its configuration" >&2
    exit 1
  fi
  sleep 2
done

current_user=$(docker exec "$CONTAINER" awk '
  /^\[authentication\.fallback-admin\]$/ { found=1; next }
  found && /^user = / { gsub(/^user = "|"$/, ""); print; exit }
' /opt/stalwart/etc/config.toml)
current_secret=$(docker exec "$CONTAINER" awk '
  /^\[authentication\.fallback-admin\]$/ { found=1; next }
  found && /^secret = / { gsub(/^secret = "|"$/, ""); print; exit }
' /opt/stalwart/etc/config.toml)

if [[ $current_user == "$ADMIN_USER" && $current_secret == "$ADMIN_SECRET_HASH" ]]; then
  echo "Stalwart fallback administrator already reconciled"
  exit 0
fi

source_config=$(mktemp)
updated_config=$(mktemp)
trap 'rm -f "$source_config" "$updated_config"' EXIT
docker cp "$CONTAINER:/opt/stalwart/etc/config.toml" "$source_config"

awk -v admin_user="$ADMIN_USER" -v admin_secret="$ADMIN_SECRET_HASH" '
  /^\[authentication\.fallback-admin\]$/ { section=1; print; next }
  section && /^user = / { print "user = \"" admin_user "\""; next }
  section && /^secret = / {
    print "secret = \"" admin_secret "\""
    section=0
    next
  }
  { print }
' "$source_config" >"$updated_config"

docker cp "$updated_config" "$CONTAINER:/opt/stalwart/etc/config.toml"
docker restart "$CONTAINER" >/dev/null
echo "Stalwart fallback administrator reconciled"
