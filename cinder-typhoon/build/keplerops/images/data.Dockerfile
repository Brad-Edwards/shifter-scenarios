FROM postgres:16.4-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 python3 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system fieldkest-data \
    && useradd --system --gid fieldkest-data --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-data \
    && mkdir -p /var/lib/fieldkest-data/audit /var/lib/fieldkest-data/backups /var/lib/postgresql/16/fieldkest-history \
    && chown -R fieldkest-data:fieldkest-data /var/lib/fieldkest-data \
    && chmod 0700 /var/lib/fieldkest-data/backups \
    && chown -R postgres:postgres /var/lib/postgresql/16/fieldkest-history

COPY build/keplerops/runtime/http_support.py /opt/fieldkest-data/http_support.py
COPY build/keplerops/runtime/platform_service.py /opt/fieldkest-data/platform_service.py
COPY build/keplerops/runtime/data-entrypoint.sh /usr/local/bin/fieldkest-data-entrypoint
RUN chmod 0755 /usr/local/bin/fieldkest-data-entrypoint

EXPOSE 443 5432
ENTRYPOINT ["/usr/local/bin/fieldkest-data-entrypoint"]
