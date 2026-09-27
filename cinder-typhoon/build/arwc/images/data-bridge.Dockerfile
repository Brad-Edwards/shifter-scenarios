FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2293 arwc-integration \
    && groupadd --system arwc-data-bridge \
    && useradd --system --gid arwc-data-bridge --groups arwc-integration --home-dir /var/lib/arwc-data-bridge --shell /usr/sbin/nologin arwc-data-bridge \
    && install -d -o arwc-data-bridge -g arwc-data-bridge -m 0750 /opt/integration-gateway

COPY --chown=arwc-data-bridge:arwc-data-bridge --chmod=0640 \
  build/arwc/runtime/integration_gateway.py /opt/integration-gateway/integration_gateway.py
COPY --chmod=0750 build/arwc/runtime/data-bridge-entrypoint.sh /usr/local/sbin/arwc-data-bridge-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-data-bridge-entrypoint"]
