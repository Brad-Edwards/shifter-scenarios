FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y python3 python3-gssapi krb5-user ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system fieldkest-staff-spnego \
    && useradd --system --gid fieldkest-staff-spnego --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-staff-spnego

COPY build/keplerops/runtime/staff_spnego.py /opt/fieldkest/service.py
COPY build/keplerops/runtime/staff-spnego-entrypoint.sh /usr/local/bin/fieldkest-service-entrypoint
COPY build/keplerops/config/krb5.conf /etc/krb5.conf

RUN chmod 0755 /usr/local/bin/fieldkest-service-entrypoint \
    && mkdir -p /run/fieldkest-tls /run/fieldkest-staff

ENV FIELDKEST_UPSTREAM=https://k-staff:443
EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-service-entrypoint"]
