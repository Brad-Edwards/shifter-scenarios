#!/bin/bash
set -euo pipefail
[[ $(hostname) == cinder-arwc-dev || $(hostname) == cinder-arwc-golden ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
desktop=cinder-arwc-ot-engineering
case ${1:-prepare} in
  prepare)
    docker exec --user fieldlink "$desktop" sh -ec '
      umask 077
      mkdir -p /home/fieldlink/.ssh
      if [ ! -s /home/fieldlink/.ssh/arwc-corporate ]; then
        ssh-keygen -q -t ed25519 -N "" -f /home/fieldlink/.ssh/arwc-corporate
      fi'
    docker exec --user fieldlink "$desktop" cat /home/fieldlink/.ssh/arwc-corporate.pub > .operator/corporate-user.pub
    chmod 0644 .operator/corporate-user.pub
    ;;
  trust)
    hostkey=$(docker exec cinder-arwc-native-workplace-1 cat /var/lib/arwc-workplace/ssh/ssh_host_ed25519_key.pub)
    printf '%s %s\n' workplace.arwc.test "$hostkey" | docker exec -i --user fieldlink "$desktop" sh -ec '
      touch /home/fieldlink/.ssh/known_hosts
      ssh-keygen -R workplace.arwc.test -f /home/fieldlink/.ssh/known_hosts >/dev/null 2>&1 || true
      cat >> /home/fieldlink/.ssh/known_hosts'
    ;;
  *) echo 'Usage: corporate-access.sh prepare|trust' >&2; exit 2 ;;
esac
