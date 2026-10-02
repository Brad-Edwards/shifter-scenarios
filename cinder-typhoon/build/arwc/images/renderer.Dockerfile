FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2310 arwc-field-session \
    && groupadd --system --gid 2311 arwc-approval-evidence \
    && groupadd --system --gid 2312 arwc-renderer-evidence \
    && groupadd --system arwc-renderer \
    && useradd --system --gid arwc-renderer --groups arwc-field-session,arwc-approval-evidence,arwc-renderer-evidence --home-dir /var/lib/arwc-renderer --shell /usr/sbin/nologin arwc-renderer \
    && install -d -o arwc-renderer -g arwc-renderer -m 0750 /opt/maintenance-renderer

RUN pip install --no-cache-dir cryptography==42.0.8

COPY --chown=arwc-renderer:arwc-renderer --chmod=0640 \
  build/arwc/runtime/maintenance_renderer.py /opt/maintenance-renderer/maintenance_renderer.py
COPY --chmod=0750 build/arwc/runtime/renderer-entrypoint.sh /usr/local/sbin/arwc-renderer-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-renderer-entrypoint"]
