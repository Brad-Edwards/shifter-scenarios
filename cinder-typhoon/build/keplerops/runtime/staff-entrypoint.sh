#!/bin/sh
set -eu

install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
exec setpriv --reuid=fieldkest-staff --regid=fieldkest-staff --init-groups \
  python3 /opt/fieldkest/service.py
