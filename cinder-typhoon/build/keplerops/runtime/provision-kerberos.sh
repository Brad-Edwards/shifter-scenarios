#!/bin/sh
set -eu

export KRB5_CONFIG=/etc/krb5.conf
export KRB5_KDC_PROFILE=/etc/krb5kdc/kdc.conf
realm=KEPLEROPS.TEST
database=/var/lib/keplerops-identity/krb5kdc
keytabs=/opt/keplerops-identity/keytabs

mkdir -p "$database" "$keytabs"
kdb5_util create -s -r "$realm" -P 'FieldKest-Realm-Master-2026'
kadmin.local -r "$realm" -q "addprinc -pw Evan-Archive-2026 evan.calderoux@$realm"
kadmin.local -r "$realm" -q "addprinc -pw Identity-HTTP-2026 HTTP/identity.keplerops.test@$realm"
kadmin.local -r "$realm" -q "addprinc -pw Staff-HTTP-2026 HTTP/staff.keplerops.test@$realm"
kadmin.local -r "$realm" -q "ktadd -norandkey -k $keytabs/identity.keytab HTTP/identity.keplerops.test@$realm"
kadmin.local -r "$realm" -q "ktadd -norandkey -k $keytabs/staff.keytab HTTP/staff.keplerops.test@$realm"
kadmin.local -r "$realm" -q "ktadd -norandkey -k $keytabs/evan.keytab evan.calderoux@$realm"
chmod 0600 "$keytabs"/*.keytab
