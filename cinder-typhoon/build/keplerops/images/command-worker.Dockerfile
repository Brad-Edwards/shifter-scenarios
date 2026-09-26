FROM debian:bookworm-slim

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
       ca-certificates curl git iproute2 jq openssl python3 strace \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 2100 fieldkest-worker \
    && useradd --uid 2100 --gid fieldkest-worker --home-dir /workspace --shell /bin/sh fieldkest-worker

COPY build/keplerops/runtime/command_worker.py /usr/local/lib/fieldkest/command_worker.py
COPY assets/keplerops/build-operations/runner-operations.md /srv/fieldlink-ci/runner/runner-operations.md

RUN chmod 0555 /usr/local/lib/fieldkest/command_worker.py \
    && chmod 0444 /srv/fieldlink-ci/runner/runner-operations.md

ENTRYPOINT ["python3", "/usr/local/lib/fieldkest/command_worker.py"]
