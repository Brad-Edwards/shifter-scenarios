FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system fieldkest-cloud \
    && useradd --system --gid fieldkest-cloud --home-dir /var/lib/fieldkest-cloud-api --shell /usr/sbin/nologin fieldkest-cloud

COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/cloud_api.py /opt/fieldkest/cloud_api.py
COPY build/keplerops/runtime/cloud-api-entrypoint.sh /usr/local/bin/fieldkest-cloud-api-entrypoint
COPY assets/keplerops/build-operations/k-cloud-api-k09-state.tar /tmp/k-cloud-api-k09-state.tar

RUN mkdir -p /var/lib/fieldkest-cloud-api \
    && tar -xf /tmp/k-cloud-api-k09-state.tar -C /var/lib/fieldkest-cloud-api \
    && rm /tmp/k-cloud-api-k09-state.tar \
    && mkdir -p /var/lib/fieldkest-cloud-api/audit \
    && ln -s /opt/fieldkest /opt/fieldkest-cloud-api \
    && chown -R fieldkest-cloud:fieldkest-cloud /var/lib/fieldkest-cloud-api \
    && chmod 0755 /usr/local/bin/fieldkest-cloud-api-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-cloud-api-entrypoint"]
