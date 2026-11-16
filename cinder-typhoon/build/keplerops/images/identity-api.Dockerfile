FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 util-linux curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system fieldkest-identity-api \
    && useradd --system --gid fieldkest-identity-api --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-identity-api

COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/credentials.py /opt/fieldkest/credentials.py
COPY build/keplerops/runtime/identity_api.py /opt/fieldkest/service.py
COPY build/keplerops/runtime/identity-api-entrypoint.sh /usr/local/bin/fieldkest-service-entrypoint
COPY assets/keplerops/identity-api/k-identity-api-state.tar /tmp/k-identity-api-state.tar

RUN chmod 0755 /usr/local/bin/fieldkest-service-entrypoint \
    && mkdir -p /var/lib/fieldkest-identity-api \
    && tar -xf /tmp/k-identity-api-state.tar -C /var/lib/fieldkest-identity-api \
    && mkdir -p /var/lib/fieldkest-identity-api/audit \
    && chown -R fieldkest-identity-api:fieldkest-identity-api /var/lib/fieldkest-identity-api \
    && rm /tmp/k-identity-api-state.tar \
    && mkdir -p /run/fieldkest-tls

ENV FIELDKEST_STATE_ROOT=/var/lib/fieldkest-identity-api
EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-service-entrypoint"]
