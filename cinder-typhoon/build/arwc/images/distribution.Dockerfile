FROM python:3.12.11-slim-bookworm
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system arwc-distribution \
    && useradd --system --gid arwc-distribution --home-dir /var/lib/arwc-distribution --shell /usr/sbin/nologin arwc-distribution \
    && install -d -o arwc-distribution -g arwc-distribution -m 0750 /opt/distribution-rehearsal
COPY --chown=arwc-distribution:arwc-distribution --chmod=0640 \
  build/arwc/runtime/distribution_controller.py build/arwc/runtime/schedule33.py /opt/distribution-rehearsal/
COPY --chmod=0750 build/arwc/runtime/distribution-entrypoint.sh /usr/local/sbin/arwc-distribution-entrypoint
EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-distribution-entrypoint"]
