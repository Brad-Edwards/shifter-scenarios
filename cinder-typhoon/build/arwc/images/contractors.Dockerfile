FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2310 arwc-field-session \
    && groupadd --system arwc-contractors \
    && useradd --system --gid arwc-contractors --groups arwc-field-session --home-dir /var/lib/arwc-contractors --shell /usr/sbin/nologin arwc-contractors \
    && install -d -o arwc-contractors -g arwc-contractors -m 0750 /opt/contractor-portal

COPY --chown=arwc-contractors:arwc-contractors --chmod=0640 \
  build/arwc/runtime/contractor_portal.py /opt/contractor-portal/contractor_portal.py
COPY --chmod=0750 build/arwc/runtime/contractors-entrypoint.sh /usr/local/sbin/arwc-contractors-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-contractors-entrypoint"]
