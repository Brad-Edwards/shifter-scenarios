FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2290 arwc-handover \
    && groupadd --system --gid 2291 arwc-planning \
    && groupadd --system arwc-identity \
    && useradd --system --gid arwc-identity --groups arwc-handover,arwc-planning --home-dir /var/lib/arwc-identity --shell /usr/sbin/nologin arwc-identity \
    && install -d -o arwc-identity -g arwc-identity -m 0750 /opt/corporate-identity

COPY --chown=arwc-identity:arwc-identity --chmod=0640 \
  build/arwc/runtime/corporate_identity.py /opt/corporate-identity/corporate_identity.py
COPY --chmod=0750 build/arwc/runtime/identity-entrypoint.sh /usr/local/sbin/arwc-identity-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-identity-entrypoint"]
