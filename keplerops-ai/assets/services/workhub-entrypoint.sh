#!/bin/sh
set -eu
umask 077
export GITEA_WORK_DIR=/data/gitea
export HOME=/data/gitea/home
SECRET_KEY_BASE="$(printf '%s' 'keplerops-workhub-synthetic-356' | sha256sum | awk '{print $1}')"
export SECRET_KEY_BASE
export SCHEMA=/usr/src/redmine/sqlite/schema.rb
mkdir -p "$HOME"
cat >/data/gitea/conf/app.ini <<'EOF'
[server]
HTTP_ADDR = 127.0.0.1
HTTP_PORT = 3000
ROOT_URL = https://repo-ticket-01.keplerops.lab/git/
DISABLE_SSH = true
[database]
DB_TYPE = sqlite3
PATH = /data/gitea/gitea.db
[security]
INSTALL_LOCK = true
EOF
/usr/local/bin/gitea migrate --config /data/gitea/conf/app.ini
if [ ! -s /data/gitea/seed-complete ]; then
  if ! /usr/local/bin/gitea admin user list --config /data/gitea/conf/app.ini | awk 'NR > 1 && $2 == "seed-admin" { found=1 } END { exit !found }'; then
    /usr/local/bin/gitea admin user create --config /data/gitea/conf/app.ini --username seed-admin --random-password --random-password-length 48 --email seed-admin@keplerops.lab --admin --must-change-password=false >/dev/null
  fi
  BOOTSTRAP_TOKEN_NAME="company-state-bootstrap-$(date +%s)-$$"
  /usr/local/bin/gitea admin user generate-access-token --config /data/gitea/conf/app.ini --username seed-admin --token-name "$BOOTSTRAP_TOKEN_NAME" --raw >/data/gitea/seed-admin.txt
  chmod 0600 /data/gitea/seed-admin.txt
fi
/usr/local/bin/gitea web --config /data/gitea/conf/app.ini &
if [ -s /data/gitea/seed-admin.txt ]; then
  /usr/local/bin/seed-workhub /data/gitea/seed-admin.txt
  rm -f /data/gitea/seed-admin.txt
else
  /usr/local/bin/seed-workhub
fi
: >/data/gitea/seed-complete
chmod 0600 /data/gitea/seed-complete
/usr/local/bin/seed-context-access
/usr/local/bin/seed-agent-expansion
bundle exec rake db:migrate RAILS_ENV=production
REDMINE_LANG=en bundle exec rake redmine:load_default_data RAILS_ENV=production >/dev/null
bundle exec rails runner -e production /opt/keplerops/seed-redmine.rb materialize
bundle exec rails server -b 127.0.0.1 -p 3001 -e production &
attempt=0
until ruby -rnet/http -e 'response = Net::HTTP.get_response(URI("http://127.0.0.1:3001/")); exit(response.is_a?(Net::HTTPSuccess) ? 0 : 1)' 2>/dev/null
do
  attempt=$((attempt + 1))
  if [ "${attempt}" -ge 60 ]; then
    echo "Redmine API did not become ready" >&2
    exit 1
  fi
  sleep 1
done
bundle exec rails runner -e production /opt/keplerops/seed-redmine.rb readback
exec /usr/local/bin/envoy -c /etc/keplerops/envoy.yaml --log-level warn
