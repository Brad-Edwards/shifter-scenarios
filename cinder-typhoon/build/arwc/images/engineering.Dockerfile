FROM python:3.12.11-slim-bookworm AS narrative
COPY assets/narrative/generated/packages/arwc-documents.json /tmp/arwc-documents.json
COPY build/arwc/runtime/extract_document.py /usr/local/bin/extract-document
RUN python3 /usr/local/bin/extract-document /tmp/arwc-documents.json me-project-handover-01 /tmp/me-project-handover-01.md

FROM python:3.12.11-slim-bookworm
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2320 arwc-process-evidence \
    && groupadd --system arwc-engineering \
    && useradd --system --gid arwc-engineering --groups arwc-process-evidence --home-dir /var/lib/arwc-engineering --shell /usr/sbin/nologin arwc-engineering \
    && install -d -o arwc-engineering -g arwc-engineering -m 0750 /opt/process-service/assets
COPY --chown=arwc-engineering:arwc-engineering --chmod=0640 build/arwc/runtime/process_services.py /opt/process-service/process_services.py
COPY --from=narrative --chown=arwc-engineering:arwc-engineering --chmod=0640 /tmp/me-project-handover-01.md /opt/process-service/assets/me-project-handover-01.md
COPY --chmod=0750 build/arwc/runtime/process-service-entrypoint.sh /usr/local/sbin/arwc-process-entrypoint
EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-process-entrypoint"]
