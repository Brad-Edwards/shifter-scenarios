#!/bin/sh
set -eu
umask 077
install -d -m 0700 /var/lib/arwc-workplace/ssh
install -d -m 0755 /run/sshd
if [ ! -s /var/lib/arwc-workplace/ssh/ssh_host_ed25519_key ]; then
  ssh-keygen -q -t ed25519 -N '' -f /var/lib/arwc-workplace/ssh/ssh_host_ed25519_key
fi
cat /etc/ssl/certs/ca-certificates.crt /run/public-ca/native.crt \
  /run/public-ca/customer.crt > /tmp/arwc-public-ca.pem
chmod 0644 /tmp/arwc-public-ca.pem
exec /usr/sbin/sshd -D -e
