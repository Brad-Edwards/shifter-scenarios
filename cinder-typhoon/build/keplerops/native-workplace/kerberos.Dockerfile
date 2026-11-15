FROM python:3.12.11-slim-bookworm
RUN apt-get update \
    && apt-get install --no-install-recommends -y iproute2 krb5-admin-server krb5-kdc krb5-user util-linux \
    && apt-get clean \
    && groupadd --gid 999 keplerops-identity \
    && useradd --uid 999 --gid 999 --system --home-dir /nonexistent --shell /usr/sbin/nologin keplerops-identity
COPY build/keplerops/config/krb5.conf /etc/krb5.conf
COPY build/keplerops/config/kdc.conf /etc/krb5kdc/kdc.conf
COPY build/keplerops/config/kadm5.acl /etc/krb5kdc/kadm5.acl
COPY build/keplerops/native-workplace/initialize-kdc.py /usr/local/libexec/fieldlink-initialize-kdc.py
COPY build/keplerops/native-workplace/kerberos-entrypoint.sh /usr/local/bin/fieldlink-kerberos
RUN chmod 0555 /usr/local/bin/fieldlink-kerberos \
    && mkdir -p /var/lib/keplerops-identity/krb5kdc /var/lib/keplerops-identity/keytabs \
    && chmod 0755 /etc/krb5kdc \
    && chmod 0444 /etc/krb5kdc/kdc.conf /etc/krb5kdc/kadm5.acl \
    && chown -R keplerops-identity:keplerops-identity /var/lib/keplerops-identity \
    && chmod 0700 /var/lib/keplerops-identity /var/lib/keplerops-identity/krb5kdc
EXPOSE 88/tcp 88/udp
ENTRYPOINT ["/usr/local/bin/fieldlink-kerberos"]
