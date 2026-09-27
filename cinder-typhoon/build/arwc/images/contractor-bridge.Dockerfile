FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2310 arwc-field-session \
    && groupadd --system arwc-contractor-bridge \
    && useradd --system --gid arwc-contractor-bridge --groups arwc-field-session --home-dir /var/lib/arwc-contractor-bridge --shell /usr/sbin/nologin arwc-contractor-bridge \
    && install -d -o arwc-contractor-bridge -g arwc-contractor-bridge -m 0750 /opt/field-gateway

COPY --chown=arwc-contractor-bridge:arwc-contractor-bridge --chmod=0640 \
  build/arwc/runtime/field_gateway.py /opt/field-gateway/field_gateway.py
COPY --chmod=0750 build/arwc/runtime/contractor-bridge-entrypoint.sh /usr/local/sbin/arwc-contractor-bridge-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-contractor-bridge-entrypoint"]
