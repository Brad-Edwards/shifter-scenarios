#!/bin/sh
set -eu

install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
install -m 0444 /run/fieldkest-staff/support_db_password /tmp/fieldkest-db-pass
export SUPPORT_DB_PASSWORD_FILE=/tmp/fieldkest-db-pass
install -m 0444 /run/fieldkest-staff/kanboard_db_password /tmp/fieldkest-kb-pass
export KANBOARD_DB_PASSWORD_FILE=/tmp/fieldkest-kb-pass
install -m 0444 /run/fieldkest-staff/kerberos-users.json /tmp/fieldkest-krb-users.json
export KERBEROS_USERS_FILE=/tmp/fieldkest-krb-users.json
exec setpriv --reuid=fieldkest-staff --regid=fieldkest-staff --init-groups \
  python3 /opt/fieldkest/service.py
