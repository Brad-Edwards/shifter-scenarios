FROM python:3.12.11-slim-bookworm

ARG SERVICE
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system "fieldkest-$SERVICE" \
    && useradd --system --gid "fieldkest-$SERVICE" --home-dir /nonexistent --shell /usr/sbin/nologin "fieldkest-$SERVICE" \
    && mkdir -p "/var/lib/fieldkest-$SERVICE/audit" \
    && chown -R "fieldkest-$SERVICE:fieldkest-$SERVICE" "/var/lib/fieldkest-$SERVICE"

COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/platform_service.py /opt/fieldkest/platform_service.py
COPY build/keplerops/runtime/platform-entrypoint.sh /usr/local/bin/fieldkest-platform-entrypoint

RUN case "$SERVICE" in \
      workload) ln -s /opt/fieldkest /opt/fieldkest-workloads ;; \
      cert) ln -s /opt/fieldkest /opt/keplerops-cert \
        && mkdir -p /var/lib/keplerops-cert/audit \
        && chown -R fieldkest-cert:fieldkest-cert /var/lib/keplerops-cert ;; \
      *) true ;; \
    esac \
    && chmod 0755 /usr/local/bin/fieldkest-platform-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-platform-entrypoint"]
