FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir cryptography==50.0.2 \
    && groupadd --system fieldkest-support \
    && useradd --system --gid fieldkest-support --home-dir /var/lib/fieldkest-support --shell /usr/sbin/nologin fieldkest-support

COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/credentials.py /opt/fieldkest/credentials.py
COPY build/keplerops/native-workplace/support-client.json /opt/fieldkest/client_documents.json
COPY build/keplerops/runtime/support.py /opt/fieldkest/support.py
COPY build/keplerops/runtime/support-entrypoint.sh /usr/local/bin/fieldkest-support-entrypoint

RUN mkdir -p /var/lib/fieldkest-support/audit /var/lib/fieldkest-handover \
    && ln -s /opt/fieldkest /opt/fieldkest-support \
    && chown -R fieldkest-support:fieldkest-support /var/lib/fieldkest-support /var/lib/fieldkest-handover \
    && chmod 0750 /var/lib/fieldkest-support \
    && chmod 0755 /usr/local/bin/fieldkest-support-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-support-entrypoint"]
