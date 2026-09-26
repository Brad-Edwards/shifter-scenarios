FROM python:3.12.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates gcc iproute2 krb5-admin-server krb5-kdc krb5-user libkrb5-dev util-linux \
    && pip install --no-cache-dir cryptography==46.0.5 gssapi==1.10.1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system fieldkest-identity \
    && useradd --system --gid fieldkest-identity --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-identity

COPY build/keplerops/config/krb5.conf /etc/krb5.conf
COPY build/keplerops/config/kdc.conf /etc/krb5kdc/kdc.conf
COPY build/keplerops/config/kadm5.acl /etc/krb5kdc/kadm5.acl
COPY build/keplerops/runtime/provision-kerberos.sh /usr/local/sbin/fieldkest-provision-kerberos
COPY build/keplerops/runtime/http_support.py /opt/keplerops-identity/http_support.py
COPY build/keplerops/runtime/platform_service.py /opt/keplerops-identity/platform_service.py
COPY build/keplerops/runtime/platform-entrypoint.sh /usr/local/bin/fieldkest-platform-entrypoint

RUN chmod 0755 /usr/local/sbin/fieldkest-provision-kerberos /usr/local/bin/fieldkest-platform-entrypoint \
    && /usr/local/sbin/fieldkest-provision-kerberos \
    && chown -R fieldkest-identity:fieldkest-identity /var/lib/keplerops-identity /opt/keplerops-identity \
    && chown root:fieldkest-identity /var/lib/keplerops-identity \
    && chmod 0770 /var/lib/keplerops-identity \
    && chown -R root:root /var/lib/keplerops-identity/krb5kdc \
    && chmod 0700 /var/lib/keplerops-identity/krb5kdc

EXPOSE 443 88/tcp 88/udp
ENTRYPOINT ["/usr/local/bin/fieldkest-platform-entrypoint"]
