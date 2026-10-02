FROM python:3.12.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates gcc iproute2 krb5-admin-server krb5-kdc krb5-user libkrb5-dev util-linux \
    && pip install --no-cache-dir cryptography==46.0.5 gssapi==1.10.1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system keplerops-identity \
    && useradd --system --gid keplerops-identity --home-dir /nonexistent --shell /usr/sbin/nologin keplerops-identity

COPY build/keplerops/config/krb5.conf /etc/krb5.conf
COPY build/keplerops/config/kdc.conf /etc/krb5kdc/kdc.conf
COPY build/keplerops/config/kadm5.acl /etc/krb5kdc/kadm5.acl
COPY build/keplerops/runtime/provision-kerberos.sh /usr/local/sbin/fieldkest-provision-kerberos
COPY build/keplerops/runtime/http_support.py /opt/keplerops-identity/http_support.py
COPY build/keplerops/runtime/platform_service.py /opt/keplerops-identity/platform_service.py
COPY build/keplerops/runtime/platform-entrypoint.sh /usr/local/bin/fieldkest-platform-entrypoint

RUN chmod 0755 /usr/local/sbin/fieldkest-provision-kerberos /usr/local/bin/fieldkest-platform-entrypoint \
    && /usr/local/sbin/fieldkest-provision-kerberos \
    && chmod 0755 /etc/krb5kdc \
    && chmod 0444 /etc/krb5kdc/kdc.conf /etc/krb5kdc/kadm5.acl \
    && chown -R keplerops-identity:keplerops-identity /var/lib/keplerops-identity /opt/keplerops-identity \
    && chmod 0700 /var/lib/keplerops-identity \
    && chmod 0700 /var/lib/keplerops-identity/krb5kdc

EXPOSE 443 88/tcp 88/udp
ENTRYPOINT ["/usr/local/bin/fieldkest-platform-entrypoint"]
