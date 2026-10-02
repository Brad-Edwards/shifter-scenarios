FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y iproute2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir cryptography==42.0.8 \
    && groupadd --system fieldkest-relay \
    && useradd --system --gid fieldkest-relay --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-relay

COPY --chown=fieldkest-relay:fieldkest-relay --chmod=0550 \
  build/keplerops/runtime/customer_relay.py /opt/fieldkest/customer_relay.py
COPY --chmod=0550 build/keplerops/runtime/customer-relay-entrypoint.sh /usr/local/sbin/customer-relay-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/customer-relay-entrypoint"]
