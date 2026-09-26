FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir cryptography==46.0.5 \
    && groupadd --system fieldkest-registry \
    && useradd --system --gid fieldkest-registry --home-dir /var/lib/fieldkest-registry --shell /usr/sbin/nologin fieldkest-registry

COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/registry.py /opt/fieldkest/registry.py
COPY build/keplerops/runtime/registry-entrypoint.sh /usr/local/bin/fieldkest-registry-entrypoint
COPY assets/keplerops/registry/k-registry-state.tar /tmp/k-registry-state.tar

RUN mkdir -p /var/lib/fieldkest-registry \
    && tar -xf /tmp/k-registry-state.tar -C /var/lib/fieldkest-registry \
    && rm /tmp/k-registry-state.tar \
    && mkdir -p /var/lib/fieldkest-registry/audit /var/lib/fieldkest-registry/results /var/lib/fieldkest-registry/published \
    && chown -R fieldkest-registry:fieldkest-registry /var/lib/fieldkest-registry \
    && chmod 0755 /usr/local/bin/fieldkest-registry-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-registry-entrypoint"]
