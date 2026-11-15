#!/bin/sh
set -eu
umask 077
install -d -m 0700 /var/lib/arwc-workplace/ssh
install -d -m 0755 /run/sshd
if [ ! -s /var/lib/arwc-workplace/ssh/ssh_host_ed25519_key ]; then
  ssh-keygen -q -t ed25519 -N '' -f /var/lib/arwc-workplace/ssh/ssh_host_ed25519_key
fi
install -m 0644 /run/public-ca/native.crt /usr/local/share/ca-certificates/arwc-native.crt
install -m 0644 /run/public-ca/customer.crt /usr/local/share/ca-certificates/arwc-customer.crt
update-ca-certificates >/dev/null
exec /usr/sbin/sshd -D -e
