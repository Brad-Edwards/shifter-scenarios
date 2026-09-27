FROM python:3.12.11-slim-bookworm AS narrative
COPY assets/narrative/generated/packages/arwc-documents.json /tmp/arwc-documents.json
COPY build/arwc/runtime/extract_document.py /usr/local/bin/extract-document
RUN python3 /usr/local/bin/extract-document /tmp/arwc-documents.json \
      pl-arwc-plan-method-01-method /tmp/pl-arwc-plan-method-01-method.md

FROM postgres:16.4-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates python3 python3-psycopg2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2291 arwc-planning \
    && groupadd --system --gid 2292 arwc-archive-source \
    && groupadd --system --gid 2293 arwc-integration \
    && groupadd --system --gid 2294 arwc-relation \
    && groupadd --system --gid 2320 arwc-process-evidence \
    && groupadd --system --gid 2321 arwc-ot-read \
    && groupadd --system arwc-data \
    && useradd --system --gid arwc-data --groups arwc-planning,arwc-archive-source,arwc-integration,arwc-relation,arwc-process-evidence,arwc-ot-read --home-dir /var/lib/arwc-data --shell /usr/sbin/nologin arwc-data \
    && install -d -o arwc-data -g arwc-data -m 0750 /opt/planning-data/assets

COPY --chown=arwc-data:arwc-data --chmod=0640 \
  build/arwc/runtime/planning_data.py /opt/planning-data/planning_data.py
COPY --chown=arwc-data:arwc-data --chmod=0640 \
  build/arwc/runtime/schedule33.py /opt/planning-data/schedule33.py
COPY --from=narrative --chown=arwc-data:arwc-data --chmod=0640 \
  /tmp/pl-arwc-plan-method-01-method.md /opt/planning-data/assets/pl-arwc-plan-method-01-method.md
COPY --chmod=0750 build/arwc/runtime/data-entrypoint.sh /usr/local/sbin/arwc-data-entrypoint

EXPOSE 443 5432
ENTRYPOINT ["/usr/local/sbin/arwc-data-entrypoint"]
