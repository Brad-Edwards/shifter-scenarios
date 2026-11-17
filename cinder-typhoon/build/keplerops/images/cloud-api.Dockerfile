FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 util-linux curl python3-psycopg2 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system fieldkest-cloud-api \
    && useradd --system --gid fieldkest-cloud-api --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-cloud-api

COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/credentials.py /opt/fieldkest/credentials.py
COPY build/keplerops/runtime/cloud-api.py /opt/fieldkest/service.py
COPY build/keplerops/runtime/client-references/cloud-api.json /opt/fieldkest/client_documents.json
COPY build/keplerops/runtime/cloud-api-entrypoint.sh /usr/local/bin/fieldkest-service-entrypoint
COPY assets/keplerops/cloud-api/k-cloud-api-state.tar /tmp/k-cloud-api-state.tar

RUN chmod 0755 /usr/local/bin/fieldkest-service-entrypoint \
    && mkdir -p /var/lib/fieldkest-cloud-api \
    && tar -xf /tmp/k-cloud-api-state.tar -C /var/lib/fieldkest-cloud-api \
    && mkdir -p /var/lib/fieldkest-cloud-api/audit /var/lib/fieldkest-cloud-api/results \
    && chown -R fieldkest-cloud-api:fieldkest-cloud-api /var/lib/fieldkest-cloud-api \
    && rm /tmp/k-cloud-api-state.tar \
    && mkdir -p /run/fieldkest-tls /etc/cloud-api \
    && ln -s /opt/fieldkest /opt/fieldkest-cloud-api

ENV FIELDKEST_STATE_ROOT=/var/lib/fieldkest-cloud-api
EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-service-entrypoint"]
