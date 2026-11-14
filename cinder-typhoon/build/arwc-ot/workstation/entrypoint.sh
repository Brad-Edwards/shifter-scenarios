#!/bin/bash
set -euo pipefail
mkdir -p /run/xrdp /var/log
install -d -m 0755 /run/dbus
dbus-uuidgen --ensure=/etc/machine-id
ln -sf /etc/machine-id /var/lib/dbus/machine-id
rm -f /run/dbus/system_bus_socket
dbus-daemon --system --fork --nopidfile
if [[ ! -s /etc/ssl/private/ssl-cert-snakeoil.key ]]; then
  umask 077
  openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 30 \
    -subj /CN=arwc-ot-engineering \
    -keyout /etc/ssl/private/ssl-cert-snakeoil.key \
    -out /etc/ssl/certs/ssl-cert-snakeoil.pem >/dev/null 2>&1
  chown root:ssl-cert /etc/ssl/private/ssl-cert-snakeoil.key
  chmod 0640 /etc/ssl/private/ssl-cert-snakeoil.key
  chmod 0644 /etc/ssl/certs/ssl-cert-snakeoil.pem
fi
ln -sf /etc/ssl/private/ssl-cert-snakeoil.key /etc/xrdp/key.pem
ln -sf /etc/ssl/certs/ssl-cert-snakeoil.pem /etc/xrdp/cert.pem
touch /var/log/xrdp.log /var/log/xrdp-sesman.log
chown xrdp:xrdp /var/log/xrdp.log /var/log/xrdp-sesman.log
xrdp-sesman --nodaemon &
sleep 1
exec xrdp --nodaemon
