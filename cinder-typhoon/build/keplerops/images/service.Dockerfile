FROM python:3.12.11-slim-bookworm

ARG SERVICE
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 util-linux \
    && if [ "$SERVICE" = source ]; then apt-get install --no-install-recommends -y git; fi \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system "fieldkest-$SERVICE" \
    && useradd --system --gid "fieldkest-$SERVICE" --home-dir /nonexistent --shell /usr/sbin/nologin "fieldkest-$SERVICE"

COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/${SERVICE}.py /opt/fieldkest/service.py
COPY build/keplerops/runtime/service-entrypoint.sh /usr/local/bin/fieldkest-service-entrypoint

RUN chmod 0755 /usr/local/bin/fieldkest-service-entrypoint \
    && mkdir -p /run/fieldkest-tls

EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-service-entrypoint"]

