FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2320 arwc-process-evidence \
    && groupadd --system arwc-instruments \
    && useradd --system --gid arwc-instruments --groups arwc-process-evidence --home-dir /var/lib/arwc-instruments --shell /usr/sbin/nologin arwc-instruments \
    && install -d -o arwc-instruments -g arwc-instruments -m 0750 /opt/process-service/assets

COPY --chown=arwc-instruments:arwc-instruments --chmod=0640 \
  build/arwc/runtime/process_services.py /opt/process-service/process_services.py
COPY --chmod=0750 build/arwc/runtime/process-service-entrypoint.sh /usr/local/sbin/arwc-process-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-process-entrypoint"]
