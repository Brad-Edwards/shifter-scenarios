FROM node:22.19.0-bookworm-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 python3 python3-cryptography util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --prefix /opt/verdaccio --omit=dev --no-audit --no-fund verdaccio@6.1.6 \
    && groupadd --system verdaccio \
    && useradd --system --gid verdaccio --home-dir /var/lib/verdaccio --shell /usr/sbin/nologin verdaccio \
    && groupadd --system fieldkest-registry \
    && useradd --system --gid fieldkest-registry --home-dir /var/lib/fieldkest-registry --shell /usr/sbin/nologin fieldkest-registry

COPY build/keplerops/runtime/http_support.py /opt/fieldkest-registry/http_support.py
COPY build/keplerops/runtime/registry.py /opt/fieldkest-registry/registry.py
COPY build/keplerops/runtime/registry-entrypoint.sh /usr/local/bin/fieldkest-registry-entrypoint
COPY build/keplerops/config/verdaccio.yaml /etc/verdaccio/config.yaml
COPY assets/keplerops/registry/k-registry-state.tar /tmp/k-registry-state.tar
COPY assets/keplerops/release-lineage/k-registry-k29-state.tar /tmp/k-registry-k29-state.tar

RUN mkdir -p /var/lib/fieldkest-registry /var/lib/verdaccio/storage \
    && tar -xf /tmp/k-registry-state.tar -C /var/lib/fieldkest-registry \
    && tar -xf /tmp/k-registry-k29-state.tar -C /var/lib/fieldkest-registry \
    && rm /tmp/k-registry-state.tar /tmp/k-registry-k29-state.tar \
    && mkdir -p /var/lib/fieldkest-registry/audit /var/lib/fieldkest-registry/results /var/lib/fieldkest-registry/published \
    && touch /var/lib/verdaccio/htpasswd \
    && chown -R fieldkest-registry:fieldkest-registry /var/lib/fieldkest-registry \
    && chown -R verdaccio:verdaccio /var/lib/verdaccio \
    && chmod 0700 /var/lib/fieldkest-registry \
    && chmod 0750 /var/lib/verdaccio \
    && chmod 0755 /usr/local/bin/fieldkest-registry-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-registry-entrypoint"]
