FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates git iproute2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system git \
    && useradd --system --gid git --home-dir /var/lib/gitea --shell /usr/sbin/nologin git

COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/source.py /opt/fieldkest/source.py
COPY build/keplerops/runtime/source-entrypoint.sh /usr/local/bin/fieldkest-source-entrypoint
COPY assets/keplerops/opening/k-source-state.tar /tmp/k-source-state.tar
COPY assets/keplerops/policy-compiler/k-source-k11-state.tar /tmp/k-source-k11-state.tar

RUN mkdir -p /var/lib/gitea \
    && tar -xf /tmp/k-source-state.tar -C /var/lib/gitea \
    && tar -xf /tmp/k-source-k11-state.tar -C /var/lib/gitea \
    && rm /tmp/k-source-state.tar /tmp/k-source-k11-state.tar \
    && mkdir -p /var/lib/gitea/audit /var/lib/gitea/repositories \
    && chown -R git:git /var/lib/gitea \
    && chmod 0755 /usr/local/bin/fieldkest-source-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-source-entrypoint"]
