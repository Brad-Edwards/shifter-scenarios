FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 util-linux curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system fieldkest-assistant-api \
    && useradd --system --gid fieldkest-assistant-api --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-assistant-api

COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/credentials.py /opt/fieldkest/credentials.py
COPY build/keplerops/runtime/assistant_api.py /opt/fieldkest/service.py
COPY build/keplerops/runtime/support-review-completion.py /opt/fieldkest/support-review-completion.py
COPY build/keplerops/runtime/assistant-api-entrypoint.sh /usr/local/bin/fieldkest-service-entrypoint
COPY assets/keplerops/assistant-api/k-assistant-api-state.tar /tmp/k-assistant-api-state.tar

RUN chmod 0755 /usr/local/bin/fieldkest-service-entrypoint \
    && mkdir -p /var/lib/fieldkest-assistant-api/audit \
    && tar -xf /tmp/k-assistant-api-state.tar -C /var/lib/fieldkest-assistant-api \
    && chown -R fieldkest-assistant-api:fieldkest-assistant-api /var/lib/fieldkest-assistant-api \
    && rm /tmp/k-assistant-api-state.tar \
    && mkdir -p /run/fieldkest-tls

ENV FIELDKEST_STATE_ROOT=/var/lib/fieldkest-assistant-api
EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-service-entrypoint"]
