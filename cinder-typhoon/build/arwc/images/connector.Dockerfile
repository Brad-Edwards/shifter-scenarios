FROM python:3.12.11-slim-bookworm AS narrative

COPY assets/narrative/generated/packages/arwc-documents.json /tmp/arwc-documents.json
COPY build/arwc/runtime/extract_document.py /usr/local/bin/extract-document
RUN python3 /usr/local/bin/extract-document \
      /tmp/arwc-documents.json \
      pl-arwc-plan-method-01-method \
      /tmp/pl-arwc-plan-method-01-method.md

FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl jq openssl util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system fieldlink \
    && useradd --system --gid fieldlink --home-dir /var/lib/fieldlink-connector --shell /usr/sbin/nologin fieldlink \
    && groupadd --system arwc-connector \
    && useradd --system --gid arwc-connector --home-dir /var/lib/arwc-connector --shell /usr/sbin/nologin arwc-connector \
    && install -d -o arwc-connector -g arwc-connector -m 0750 /opt/customer-handover/assets

COPY --chown=arwc-connector:arwc-connector --chmod=0640 \
  build/arwc/runtime/customer_handover.py /opt/customer-handover/customer_handover.py
COPY --from=narrative --chown=arwc-connector:arwc-connector --chmod=0640 \
  /tmp/pl-arwc-plan-method-01-method.md /opt/customer-handover/assets/pl-arwc-plan-method-01-method.md
COPY --chmod=0750 build/arwc/runtime/connector-entrypoint.sh /usr/local/sbin/arwc-connector-entrypoint

EXPOSE 8443
ENTRYPOINT ["/usr/local/sbin/arwc-connector-entrypoint"]
