FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
       python3 python3-gssapi krb5-user ca-certificates iproute2 util-linux curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system fieldkest-identity-spnego \
    && useradd --system --gid fieldkest-identity-spnego --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-identity-spnego

COPY build/keplerops/runtime/identity_spnego.py /opt/fieldkest/service.py
COPY build/keplerops/runtime/identity-spnego-entrypoint.sh /usr/local/bin/fieldkest-service-entrypoint
COPY build/keplerops/config/krb5.conf /etc/krb5.conf
COPY assets/keplerops/identity-spnego/k-identity-spnego-state.tar /tmp/k-identity-spnego-state.tar

RUN chmod 0755 /usr/local/bin/fieldkest-service-entrypoint \
    && mkdir -p /var/lib/fieldkest-identity-spnego \
    && tar -xf /tmp/k-identity-spnego-state.tar -C /var/lib/fieldkest-identity-spnego \
    && chown -R fieldkest-identity-spnego:fieldkest-identity-spnego /var/lib/fieldkest-identity-spnego \
    && chmod -R 644 /var/lib/fieldkest-identity-spnego \
    && rm /tmp/k-identity-spnego-state.tar \
    && mkdir -p /run/fieldkest-tls /run/fieldkest-identity

ENV FIELDKEST_STATE_ROOT=/var/lib/fieldkest-identity-spnego
EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-service-entrypoint"]
