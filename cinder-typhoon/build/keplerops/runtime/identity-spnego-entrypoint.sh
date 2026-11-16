#!/bin/sh
set -eu

install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
export FIELDKEST_TLS_CERT=/tmp/fieldkest.crt
export FIELDKEST_TLS_KEY=/tmp/fieldkest.key
# KRB5_KTNAME points to the service keytab for SPNEGO acceptance
export KRB5_KTNAME=/run/fieldkest-identity/identity.keytab
# KRB5RCACHEDIR points to writable tmpfs for Kerberos replay cache
export KRB5RCACHEDIR=/tmp
exec python3 /opt/fieldkest/service.py
