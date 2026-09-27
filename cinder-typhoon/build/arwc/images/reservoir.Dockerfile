FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2320 arwc-process-evidence \
    && groupadd --system --gid 2330 arwc-control-authority \
    && groupadd --system arwc-reservoir \
    && useradd --system --gid arwc-reservoir --groups arwc-process-evidence,arwc-control-authority --home-dir /var/lib/arwc-reservoir --shell /usr/sbin/nologin arwc-reservoir \
    && install -d -o arwc-reservoir -g arwc-reservoir -m 0750 /opt/reservoir-controller

COPY --chown=arwc-reservoir:arwc-reservoir --chmod=0640 \
  build/arwc/runtime/reservoir_controller.py /opt/reservoir-controller/reservoir_controller.py
COPY --chown=arwc-reservoir:arwc-reservoir --chmod=0640 \
  build/arwc/runtime/schedule33.py /opt/reservoir-controller/schedule33.py
COPY --chmod=0750 build/arwc/runtime/reservoir-entrypoint.sh /usr/local/sbin/arwc-reservoir-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-reservoir-entrypoint"]
