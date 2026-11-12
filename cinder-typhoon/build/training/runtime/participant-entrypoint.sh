#!/bin/bash
set -euo pipefail

mkdir -p /run/xrdp
touch /var/log/xrdp.log /var/log/xrdp-sesman.log
chown xrdp:xrdp /var/log/xrdp.log /var/log/xrdp-sesman.log

xrdp-sesman --nodaemon &
sleep 1
exec xrdp --nodaemon
