FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 2100 fieldkest-ci \
    && useradd --uid 2100 --gid fieldkest-ci --home-dir /var/lib/fieldkest-ci --shell /usr/sbin/nologin fieldkest-ci

COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/ci.py /opt/fieldkest/ci.py
COPY build/keplerops/runtime/ci-entrypoint.sh /usr/local/bin/fieldkest-ci-entrypoint
COPY assets/keplerops/opening/k-ci-state.tar /tmp/k-ci-state.tar
COPY assets/keplerops/build-operations/k-ci-k09-state.tar /tmp/k-ci-k09-state.tar
COPY assets/keplerops/build-operations/diagnostic-request-reference.md /srv/fieldlink-ci/reviews/diagnostic-request-reference.md

RUN mkdir -p /var/lib/fieldkest-ci \
    && tar -xf /tmp/k-ci-state.tar -C /var/lib/fieldkest-ci \
    && tar -xf /tmp/k-ci-k09-state.tar -C /var/lib/fieldkest-ci \
    && rm /tmp/k-ci-state.tar /tmp/k-ci-k09-state.tar \
    && mkdir -p /var/lib/fieldkest-ci/audit /var/lib/fieldkest-ci/results /var/lib/fieldkest-ci/workspaces/rowan /var/lib/fieldkest-handover \
    && chown -R fieldkest-ci:fieldkest-ci /var/lib/fieldkest-ci /var/lib/fieldkest-handover \
    && chmod 0444 /srv/fieldlink-ci/reviews/diagnostic-request-reference.md \
    && chmod 0755 /usr/local/bin/fieldkest-ci-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-ci-entrypoint"]
