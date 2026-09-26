#!/bin/sh
set -eu
ip route replace 10.77.50.0/24 via 10.77.51.254
ip route replace 10.77.52.0/24 via 10.77.51.254
ip route replace 10.77.53.0/24 via 10.77.51.254
ip route replace 10.77.60.0/24 via 10.77.51.254
install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
install -m 0444 /run/fieldkest-auth/worker-hmac.key /tmp/worker-hmac.key
export HOME=/var/lib/gitea/data
setpriv --reuid=git --regid=git --init-groups sh -c '
  if [ ! -s /var/lib/gitea/data/app.ini ]; then
    install -m 0600 /etc/gitea/app.ini /var/lib/gitea/data/app.ini
  fi
  exec /usr/local/bin/gitea web --config /var/lib/gitea/data/app.ini
' >/tmp/gitea.log 2>&1 &
gitea_pid=$!
setpriv --reuid=git --regid=git --init-groups python3 /opt/fieldkest/source.py &
api_pid=$!
trap 'kill "$api_pid" "$gitea_pid" 2>/dev/null || true' INT TERM EXIT
wait "$api_pid"
