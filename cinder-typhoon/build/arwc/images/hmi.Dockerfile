FROM python:3.12.11-slim-bookworm AS narrative
COPY assets/narrative/generated/packages/arwc-documents.json /tmp/arwc-documents.json
COPY build/arwc/runtime/extract_document.py /usr/local/bin/extract-document
RUN python3 /usr/local/bin/extract-document /tmp/arwc-documents.json me-engineering-note-01-1 /tmp/me-engineering-note-01-1.md \
    && python3 /usr/local/bin/extract-document /tmp/arwc-documents.json me-commissioning-01 /tmp/me-commissioning-01.md \
    && python3 /usr/local/bin/extract-document /tmp/arwc-documents.json service-meter-guide /tmp/service-meter-guide.md

FROM python:3.12.11-slim-bookworm
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2320 arwc-process-evidence \
    && groupadd --system arwc-hmi \
    && useradd --system --gid arwc-hmi --groups arwc-process-evidence --home-dir /var/lib/arwc-hmi --shell /usr/sbin/nologin arwc-hmi \
    && install -d -o arwc-hmi -g arwc-hmi -m 0750 /opt/process-service/assets
COPY --chown=arwc-hmi:arwc-hmi --chmod=0640 build/arwc/runtime/process_services.py /opt/process-service/process_services.py
COPY --chown=arwc-hmi:arwc-hmi --chmod=0640 build/arwc/runtime/schedule33.py /opt/process-service/schedule33.py
COPY --from=narrative --chown=arwc-hmi:arwc-hmi --chmod=0640 /tmp/me-engineering-note-01-1.md /opt/process-service/assets/me-engineering-note-01-1.md
COPY --from=narrative --chown=arwc-hmi:arwc-hmi --chmod=0640 /tmp/me-commissioning-01.md /opt/process-service/assets/me-commissioning-01.md
COPY --from=narrative --chown=arwc-hmi:arwc-hmi --chmod=0640 /tmp/service-meter-guide.md /opt/process-service/assets/service-meter-guide.md
COPY --chmod=0750 build/arwc/runtime/process-service-entrypoint.sh /usr/local/sbin/arwc-process-entrypoint
EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-process-entrypoint"]
