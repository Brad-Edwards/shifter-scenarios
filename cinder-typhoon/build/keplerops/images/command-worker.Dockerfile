FROM debian:bookworm-slim

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
       ca-certificates curl git iproute2 jq openssl python3 strace \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 2100 fieldkest-worker \
    && useradd --uid 2100 --gid fieldkest-worker --home-dir /workspace --shell /bin/sh fieldkest-worker \
    && groupadd --gid 2200 assistant-completion \
    && useradd --uid 2200 --gid assistant-completion --home-dir /nonexistent --shell /usr/sbin/nologin svc-assistant-completion \
    && groupadd --gid 2201 support-export \
    && useradd --uid 2201 --gid support-export --home-dir /nonexistent --shell /usr/sbin/nologin svc-support-export \
    && groupadd --gid 2202 fieldlink-maintenance \
    && useradd --uid 2202 --gid fieldlink-maintenance --home-dir /nonexistent --shell /usr/sbin/nologin svc-fieldlink-maintenance

COPY build/keplerops/runtime/command_worker.py /usr/local/lib/fieldkest/command_worker.py
COPY assets/keplerops/build-operations/runner-operations.md /srv/fieldlink-ci/runner/runner-operations.md

RUN chmod 0555 /usr/local/lib/fieldkest/command_worker.py \
    && chmod 0444 /srv/fieldlink-ci/runner/runner-operations.md

ENTRYPOINT ["python3", "/usr/local/lib/fieldkest/command_worker.py"]
