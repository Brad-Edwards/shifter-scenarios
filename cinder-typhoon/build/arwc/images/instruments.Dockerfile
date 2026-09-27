FROM python:3.12.11-slim-bookworm AS artifacts
COPY build/arwc/runtime/generate_process_artifacts.py /tmp/generate_process_artifacts.py
RUN python3 /tmp/generate_process_artifacts.py flash /tmp/IMG-FIT-204-R6.bin

FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2320 arwc-process-evidence \
    && groupadd --system arwc-instruments \
    && useradd --system --gid arwc-instruments --groups arwc-process-evidence --home-dir /var/lib/arwc-instruments --shell /usr/sbin/nologin arwc-instruments \
    && install -d -o arwc-instruments -g arwc-instruments -m 0750 \
      /opt/process-service/assets /opt/process-service/artifacts

COPY --chown=arwc-instruments:arwc-instruments --chmod=0640 \
  build/arwc/runtime/process_services.py /opt/process-service/process_services.py
COPY --from=artifacts --chown=arwc-instruments:arwc-instruments --chmod=0640 \
  /tmp/IMG-FIT-204-R6.bin /tmp/IMG-FIT-204-R6.json /opt/process-service/artifacts/
COPY --chmod=0750 build/arwc/runtime/process-service-entrypoint.sh /usr/local/sbin/arwc-process-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-process-entrypoint"]
