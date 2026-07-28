#!/bin/sh
set -e
# Stage the per-range splice-relay public key. The range provisioner
# passes it via A9_AUTHORIZED_KEY (set in docker-compose.override). This key,
# whose private half is staged on a14-kali, is the only path to the Bunker OT
# controllers (password auth is disabled). Written on every start so a
# --force-recreate preserves it. Empty/unset value = skip.
if [ -n "${A9_AUTHORIZED_KEY:-}" ]; then
    mkdir -p /root/.ssh && chmod 700 /root/.ssh
    printf '%s\n' "$A9_AUTHORIZED_KEY" > /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
fi
exec /usr/sbin/sshd -D
