#!/bin/sh
set -eu

install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
export FIELDKEST_TLS_CERT=/tmp/fieldkest.crt
export FIELDKEST_TLS_KEY=/tmp/fieldkest.key
export KRB5_KTNAME=/run/fieldkest-staff/staff.keytab
export KRB5RCACHEDIR=/tmp
exec python3 /opt/fieldkest/service.py
