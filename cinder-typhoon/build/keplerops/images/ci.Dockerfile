FROM node:22.19.0-bookworm-slim AS node-tools

FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl iproute2 util-linux \
    && pip install --no-cache-dir cryptography==50.0.2 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 2100 fieldkest-ci \
    && useradd --uid 2100 --gid fieldkest-ci --home-dir /var/lib/fieldkest-ci --shell /usr/sbin/nologin fieldkest-ci \
    && groupadd --system fieldkest-runner \
    && useradd --system --gid fieldkest-runner --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-runner \
    && usermod --append --groups fieldkest-runner fieldkest-ci \
    && groupadd --system fieldkest-consumer \
    && useradd --system --gid fieldkest-consumer --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-consumer

COPY --from=node-tools /usr/local/bin/node /usr/local/bin/node
COPY --from=node-tools /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/credentials.py /opt/fieldkest/credentials.py
COPY build/keplerops/native-ci/review-client.json /opt/fieldkest/client_documents.json
COPY build/keplerops/runtime/ci.py /opt/fieldkest/ci.py
COPY build/keplerops/runtime/package_delivery.py /opt/fieldkest/package_delivery.py
COPY build/keplerops/runtime/ci-entrypoint.sh /usr/local/bin/fieldkest-ci-entrypoint
COPY assets/keplerops/opening/k-ci-state.tar /tmp/k-ci-state.tar
COPY assets/keplerops/release-lineage/k-ci-release-lineage-state.tar /tmp/k-ci-release-lineage-state.tar
COPY assets/keplerops/build-operations/k-ci-runner-state.tar /tmp/k-ci-runner-state.tar
COPY assets/keplerops/build-operations/diagnostic-request-reference.md /tmp/diagnostic-request-reference.md
COPY assets/keplerops/build-operations/runner-operations.md /tmp/runner-operations.md

RUN mkdir -p /var/lib/fieldkest-ci \
    && tar -xf /tmp/k-ci-state.tar -C /var/lib/fieldkest-ci \
    && tar -xf /tmp/k-ci-release-lineage-state.tar -C /var/lib/fieldkest-ci \
    && tar -xf /tmp/k-ci-runner-state.tar -C /var/lib/fieldkest-ci \
    && mkdir -p /srv/fieldlink-ci/runner \
    && cp /tmp/diagnostic-request-reference.md /srv/fieldlink-ci/diagnostic-request-reference.md \
    && cp /tmp/runner-operations.md /srv/fieldlink-ci/runner/runner-operations.md \
    && rm /tmp/k-ci-state.tar /tmp/k-ci-release-lineage-state.tar /tmp/k-ci-runner-state.tar /tmp/diagnostic-request-reference.md /tmp/runner-operations.md \
    && mkdir -p /var/lib/fieldkest-ci/audit /var/lib/fieldkest-ci/results /var/lib/fieldkest-ci/workspaces/rowan /var/lib/fieldkest-handover \
    && mkdir -p /var/lib/fieldkest-ci/consumer-state \
    && ln -s /opt/fieldkest /opt/fieldkest-ci \
    && chown -R fieldkest-ci:fieldkest-ci /var/lib/fieldkest-ci /var/lib/fieldkest-handover \
    && chown fieldkest-runner:fieldkest-runner /var/lib/fieldkest-ci/workspaces \
    && chmod 0710 /var/lib/fieldkest-ci/workspaces \
    && chown fieldkest-consumer:fieldkest-consumer /var/lib/fieldkest-ci/consumer-state \
    && chmod 0700 /var/lib/fieldkest-ci/consumer-state \
    && chmod 0750 /var/lib/fieldkest-ci \
    && chmod 0755 /usr/local/bin/fieldkest-ci-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-ci-entrypoint"]
