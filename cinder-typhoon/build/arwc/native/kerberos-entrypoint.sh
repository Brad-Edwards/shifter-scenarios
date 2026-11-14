#!/bin/sh
set -eu
umask 077
export KRB5_KDC_PROFILE=/etc/krb5kdc/kdc.conf
if [ ! -f /var/lib/krb5kdc/principal ]; then
  master=$(cat /run/secrets/kerberos_master)
  kdb5_util create -s -r ARWC.TEST -P "$master" >/dev/null
  unset master
  workforce=$(cat /run/secrets/workforce_password)
  kadmin.local -r ARWC.TEST -q "addprinc -pw $workforce morgan.reid@ARWC.TEST" >/dev/null
  unset workforce
fi
exec krb5kdc -n -r ARWC.TEST
