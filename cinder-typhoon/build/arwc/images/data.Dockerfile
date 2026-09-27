FROM postgres:16.4-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates python3 python3-psycopg2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2291 arwc-planning \
    && groupadd --system arwc-data \
    && useradd --system --gid arwc-data --groups arwc-planning --home-dir /var/lib/arwc-data --shell /usr/sbin/nologin arwc-data \
    && install -d -o arwc-data -g arwc-data -m 0750 /opt/planning-data

COPY --chown=arwc-data:arwc-data --chmod=0640 \
  build/arwc/runtime/planning_data.py /opt/planning-data/planning_data.py
COPY --chmod=0750 build/arwc/runtime/data-entrypoint.sh /usr/local/sbin/arwc-data-entrypoint

EXPOSE 443 5432
ENTRYPOINT ["/usr/local/sbin/arwc-data-entrypoint"]
