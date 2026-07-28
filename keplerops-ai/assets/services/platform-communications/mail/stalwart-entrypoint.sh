#!/bin/sh
set -eu

state_directory=/var/lib/stalwart
seed_marker="${state_directory}/.keplerops-seeded-v1"
recovery_user=bootstrap-admin
recovery_password='KeplerOps-Recovery-2026!' # NOSONAR - committed synthetic range credential

for required_file in /etc/keplerops/pki/ca.crt /etc/keplerops/pki/mail.crt /etc/keplerops/pki/mail.key; do
    if [ ! -r "${required_file}" ]; then
        echo "required Stalwart TLS material is not readable: ${required_file}" >&2
        exit 1
    fi
done

export STALWART_RECOVERY_MODE=1
export STALWART_RECOVERY_ADMIN="${recovery_user}:${recovery_password}"
export STALWART_URL=http://127.0.0.1:8080
export STALWART_USER="${recovery_user}"
export STALWART_PASSWORD="${recovery_password}"
export COMPANY_MAIL_CONNECT_HOST=127.0.0.1
export COMPANY_MAIL_TLS_NAME=mail-server-01.keplerops.lab

/usr/local/bin/stalwart "$@" &
recovery_pid=$!
trap 'kill "${recovery_pid}" 2>/dev/null || true; wait "${recovery_pid}" 2>/dev/null || true' EXIT INT TERM

attempt=0
until python - <<'PY'
import sys
import urllib.request

try:
    with urllib.request.urlopen("http://127.0.0.1:8080/healthz/live", timeout=2) as response:
        raise SystemExit(0 if 200 <= response.status < 300 else 1)
except Exception:
    raise SystemExit(1)
PY
do
    attempt=$((attempt + 1))
    if [ "${attempt}" -ge 60 ]; then
        echo "Stalwart recovery API did not become ready" >&2
        exit 1
    fi
    sleep 1
done

if [ ! -f "${seed_marker}" ]; then
    stalwart-cli apply --file /opt/keplerops/seed.ndjson --json
    touch "${seed_marker}"
fi

python /opt/keplerops/company_state_mail.py accounts

kill "${recovery_pid}" 2>/dev/null || true
wait "${recovery_pid}" 2>/dev/null || true
trap - EXIT INT TERM

unset STALWART_RECOVERY_MODE STALWART_RECOVERY_ADMIN STALWART_URL
unset STALWART_USER STALWART_PASSWORD

/usr/local/bin/stalwart "$@" &
verification_pid=$!
trap 'kill "${verification_pid}" 2>/dev/null || true; wait "${verification_pid}" 2>/dev/null || true' EXIT INT TERM

python - <<'PY'
import socket
import time

deadline = time.monotonic() + 60
for port in (587, 993):
    while True:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                break
        except OSError:
            if time.monotonic() >= deadline:
                raise SystemExit(f"Stalwart listener {port} did not become ready")
            time.sleep(1)
PY

python /opt/keplerops/company_state_mail.py messages

kill "${verification_pid}" 2>/dev/null || true
wait "${verification_pid}" 2>/dev/null || true
trap - EXIT INT TERM

unset COMPANY_MAIL_CONNECT_HOST COMPANY_MAIL_TLS_NAME

exec /usr/local/bin/stalwart "$@"
