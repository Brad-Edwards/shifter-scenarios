FROM python:3.12.11-slim-bookworm AS narrative

COPY assets/narrative/generated/packages/arwc-documents.json /tmp/arwc-documents.json
COPY build/arwc/runtime/extract_document.py /usr/local/bin/extract-document
RUN python3 /usr/local/bin/extract-document \
      /tmp/arwc-documents.json \
      pl-arwc-plan-method-01-method \
      /tmp/pl-arwc-plan-method-01-method.md

FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl jq openssl util-linux xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system fieldlink \
    && useradd --system --gid fieldlink --home-dir /var/lib/fieldlink-connector --shell /usr/sbin/nologin fieldlink \
    && groupadd --system arwc-connector \
    && useradd --system --gid arwc-connector --home-dir /var/lib/arwc-connector --shell /usr/sbin/nologin arwc-connector \
    && install -d -o arwc-connector -g arwc-connector -m 0750 /opt/customer-handover/assets

RUN pip install --no-cache-dir cryptography==42.0.8

RUN curl -fsSL https://www.7-zip.org/a/7z2301-linux-x64.tar.xz -o /tmp/7zip.tar.xz \
    && echo '23babcab045b78016e443f862363e4ab63c77d75bc715c0b3463f6134cbcf318  /tmp/7zip.tar.xz' | sha256sum -c - \
    && tar -xJf /tmp/7zip.tar.xz -C /usr/local/bin 7zz \
    && chmod 0755 /usr/local/bin/7zz

COPY --chown=arwc-connector:arwc-connector --chmod=0640 \
  build/arwc/runtime/customer_handover.py /opt/customer-handover/customer_handover.py
COPY --from=narrative --chown=arwc-connector:arwc-connector --chmod=0640 \
  /tmp/pl-arwc-plan-method-01-method.md /opt/customer-handover/assets/pl-arwc-plan-method-01-method.md
COPY --chmod=0750 build/arwc/runtime/connector-entrypoint.sh /usr/local/sbin/arwc-connector-entrypoint

EXPOSE 8443
ENTRYPOINT ["/usr/local/sbin/arwc-connector-entrypoint"]
