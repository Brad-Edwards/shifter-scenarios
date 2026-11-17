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
setpriv --reuid=git --regid=git --init-groups python3 /opt/fieldkest/seed-gitea.py --configure
setpriv --reuid=git --regid=git --init-groups sh -c '
  exec /usr/local/bin/gitea web --config /var/lib/gitea/data/app.ini
' >/tmp/gitea.log 2>&1 &
gitea_pid=$!
# A cold range VM can take longer than 30 seconds to start Gitea.
for attempt in $(seq 1 180); do
  if curl -sS --fail --cacert /run/fieldkest-tls/ca.crt https://source.keplerops.test/user/login >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$gitea_pid" 2>/dev/null; then
    echo "source service exited during startup" >&2
    exit 1
  fi
  if [ "$attempt" -eq 180 ]; then
    echo "source service did not become ready" >&2
    exit 1
  fi
  sleep 1
done
setpriv --reuid=git --regid=git --init-groups python3 /opt/fieldkest/seed-gitea.py
setpriv --reuid=git --regid=git --init-groups python3 /opt/fieldkest/source.py &
api_pid=$!
trap 'kill "$api_pid" "$gitea_pid" 2>/dev/null || true' INT TERM EXIT
wait "$gitea_pid"
