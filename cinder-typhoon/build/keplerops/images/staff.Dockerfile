FROM python:3.12.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl gcc iproute2 krb5-admin-server krb5-kdc krb5-user libkrb5-dev util-linux \
    && pip install --no-cache-dir gssapi==1.10.1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system keplerops-staff \
    && useradd --system --gid keplerops-staff --home-dir /nonexistent --shell /usr/sbin/nologin keplerops-staff

COPY build/keplerops/config/krb5.conf /etc/krb5.conf
COPY build/keplerops/config/kdc.conf /etc/krb5kdc/kdc.conf
COPY build/keplerops/config/kadm5.acl /etc/krb5kdc/kadm5.acl
COPY build/keplerops/runtime/provision-kerberos.sh /usr/local/sbin/fieldkest-provision-kerberos
COPY build/keplerops/runtime/http_support.py /opt/keplerops-staff/http_support.py
COPY build/keplerops/runtime/platform_service.py /opt/keplerops-staff/platform_service.py
COPY build/keplerops/runtime/platform-entrypoint.sh /usr/local/bin/fieldkest-platform-entrypoint

RUN chmod 0755 /usr/local/sbin/fieldkest-provision-kerberos /usr/local/bin/fieldkest-platform-entrypoint \
    && /usr/local/sbin/fieldkest-provision-kerberos \
    && mkdir -p /opt/keplerops-staff/keytabs /var/lib/keplerops-staff/audit \
    && cp /opt/keplerops-identity/keytabs/staff.keytab /opt/keplerops-staff/keytabs/staff.keytab \
    && cp /opt/keplerops-identity/keytabs/evan.keytab /opt/keplerops-staff/keytabs/evan.keytab \
    && rm -rf /var/lib/keplerops-identity /opt/keplerops-identity \
    && chown -R keplerops-staff:keplerops-staff /var/lib/keplerops-staff /opt/keplerops-staff \
    && chmod 0700 /var/lib/keplerops-staff /opt/keplerops-staff/keytabs \
    && chmod 0400 /opt/keplerops-staff/keytabs/*.keytab

EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-platform-entrypoint"]
