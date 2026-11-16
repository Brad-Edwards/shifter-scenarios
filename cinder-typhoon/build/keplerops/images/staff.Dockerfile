FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 util-linux curl \
    && pip install --no-cache-dir pymysql==1.1.1 psycopg2-binary==2.9.10 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system fieldkest-staff \
    && useradd --system --gid fieldkest-staff --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-staff

COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/credentials.py /opt/fieldkest/credentials.py
COPY build/keplerops/runtime/staff.py /opt/fieldkest/service.py
COPY build/keplerops/runtime/client-references/staff.json /opt/fieldkest/client_documents.json
COPY build/keplerops/runtime/staff-entrypoint.sh /usr/local/bin/fieldkest-service-entrypoint
COPY assets/keplerops/staff/k-staff-state.tar /tmp/k-staff-state.tar

RUN chmod 0755 /usr/local/bin/fieldkest-service-entrypoint \
    && mkdir -p /var/lib/fieldkest-staff \
    && tar -xf /tmp/k-staff-state.tar -C /var/lib/fieldkest-staff \
    && mkdir -p /var/lib/fieldkest-staff/audit \
    && chown -R fieldkest-staff:fieldkest-staff /var/lib/fieldkest-staff \
    && rm /tmp/k-staff-state.tar \
    && mkdir -p /run/fieldkest-tls /run/fieldkest-staff

ENV FIELDKEST_STATE_ROOT=/var/lib/fieldkest-staff
EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-service-entrypoint"]
