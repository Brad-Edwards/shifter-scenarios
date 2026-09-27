FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2320 arwc-process-evidence \
    && groupadd --system --gid 2321 arwc-ot-read \
    && groupadd --system arwc-historian \
    && useradd --system --gid arwc-historian --groups arwc-process-evidence,arwc-ot-read --home-dir /var/lib/arwc-historian --shell /usr/sbin/nologin arwc-historian \
    && install -d -o arwc-historian -g arwc-historian -m 0750 /opt/process-service/assets

COPY --chown=arwc-historian:arwc-historian --chmod=0640 \
  build/arwc/runtime/process_services.py /opt/process-service/process_services.py
COPY --chmod=0750 build/arwc/runtime/process-service-entrypoint.sh /usr/local/sbin/arwc-process-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-process-entrypoint"]
