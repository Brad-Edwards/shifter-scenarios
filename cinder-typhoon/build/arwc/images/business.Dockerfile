FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2292 arwc-archive-source \
    && groupadd --system --gid 2293 arwc-integration \
    && groupadd --system --gid 2294 arwc-relation \
    && groupadd --system arwc-business \
    && useradd --system --gid arwc-business --groups arwc-archive-source,arwc-integration,arwc-relation --home-dir /var/lib/arwc-business --shell /usr/sbin/nologin arwc-business \
    && install -d -o arwc-business -g arwc-business -m 0750 /opt/business-workplace

COPY --chown=arwc-business:arwc-business --chmod=0640 \
  build/arwc/runtime/business_workplace.py /opt/business-workplace/business_workplace.py
COPY --chmod=0750 build/arwc/runtime/business-entrypoint.sh /usr/local/sbin/arwc-business-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-business-entrypoint"]
