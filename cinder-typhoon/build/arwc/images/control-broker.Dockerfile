FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2310 arwc-field-session \
    && groupadd --system --gid 2311 arwc-approval-evidence \
    && groupadd --system --gid 2312 arwc-renderer-evidence \
    && groupadd --system --gid 2330 arwc-control-authority \
    && groupadd --system arwc-control-broker \
    && useradd --system --gid arwc-control-broker --groups arwc-field-session,arwc-approval-evidence,arwc-renderer-evidence,arwc-control-authority --home-dir /var/lib/arwc-control-broker --shell /usr/sbin/nologin arwc-control-broker \
    && install -d -o arwc-control-broker -g arwc-control-broker -m 0750 /opt/control-broker

RUN pip install --no-cache-dir cryptography==42.0.8

COPY --chown=arwc-control-broker:arwc-control-broker --chmod=0640 \
  build/arwc/runtime/control_broker.py /opt/control-broker/control_broker.py
COPY --chmod=0750 build/arwc/runtime/control-broker-entrypoint.sh /usr/local/sbin/arwc-control-broker-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-control-broker-entrypoint"]
