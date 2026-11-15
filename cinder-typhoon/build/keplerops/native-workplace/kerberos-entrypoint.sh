#!/bin/sh
set -eu
ip route replace 10.77.51.0/24 via 10.77.50.254
ip route replace 10.77.52.0/24 via 10.77.50.254
ip route replace 10.77.53.0/24 via 10.77.50.254
exec setpriv --reuid=keplerops-identity --regid=keplerops-identity --init-groups \
  krb5kdc -n -r KEPLEROPS.TEST -d /var/lib/keplerops-identity/krb5kdc/principal -P /tmp/krb5kdc.pid
