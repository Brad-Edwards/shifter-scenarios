FROM debian:bookworm-slim AS builder
RUN apt-get update \
    && apt-get install --no-install-recommends -y gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
COPY build/keplerops/runtime/bundle_indexer.c /src/bundle_indexer.c
RUN gcc -std=c11 -O2 -fPIE -pie -Wl,-z,relro,-z,now -D_FORTIFY_SOURCE=2 \
    -o /fieldkest-bundle-indexer /src/bundle_indexer.c \
    && strip --strip-all /fieldkest-bundle-indexer

FROM python:3.12.11-slim-bookworm
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system fieldkest-indexer \
    && useradd --system --gid fieldkest-indexer --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-indexer \
    && mkdir -p /var/lib/fieldkest-indexer/audit \
    && chown -R fieldkest-indexer:fieldkest-indexer /var/lib/fieldkest-indexer
COPY --from=builder /fieldkest-bundle-indexer /usr/local/bin/fieldkest-bundle-indexer
COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/platform_service.py /opt/fieldkest/platform_service.py
COPY build/keplerops/runtime/platform-entrypoint.sh /usr/local/bin/fieldkest-platform-entrypoint
RUN mkdir -p /opt/fieldkest-indexer/bin \
    && ln -s /usr/local/bin/fieldkest-bundle-indexer /opt/fieldkest-indexer/bin/fieldkest-bundle-indexer \
    && chmod 0555 /usr/local/bin/fieldkest-bundle-indexer /usr/local/bin/fieldkest-platform-entrypoint
EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-platform-entrypoint"]
