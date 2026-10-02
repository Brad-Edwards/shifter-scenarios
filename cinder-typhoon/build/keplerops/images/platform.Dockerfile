FROM python:3.12.11-slim-bookworm

ARG SERVICE
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && case "$SERVICE" in \
         cert) service_user=keplerops-cert; state_dir=/var/lib/keplerops-cert; state_mode=0700 ;; \
         workload) service_user=fieldkest-scheduler; state_dir=/var/lib/fieldkest-workloads; state_mode=0750 ;; \
         *) service_user="fieldkest-$SERVICE"; state_dir="/var/lib/fieldkest-$SERVICE"; state_mode=0700 ;; \
       esac \
    && groupadd --system "$service_user" \
    && useradd --system --gid "$service_user" --home-dir /nonexistent --shell /usr/sbin/nologin "$service_user" \
    && if [ "$SERVICE" = workload ]; then \
         groupadd --system support-export \
         && useradd --system --gid support-export --home-dir /nonexistent --shell /usr/sbin/nologin svc-support-export \
         && groupadd --system fieldlink-maintenance \
         && useradd --system --gid fieldlink-maintenance --home-dir /nonexistent --shell /usr/sbin/nologin svc-fieldlink-maintenance; \
       fi \
    && mkdir -p "$state_dir/audit" \
    && chown -R "$service_user:$service_user" "$state_dir" \
    && chmod "$state_mode" "$state_dir"

COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/platform_service.py /opt/fieldkest/platform_service.py
COPY build/keplerops/runtime/platform-entrypoint.sh /usr/local/bin/fieldkest-platform-entrypoint

RUN case "$SERVICE" in \
      workload) ln -s /opt/fieldkest /opt/fieldkest-workloads ;; \
      cert) ln -s /opt/fieldkest /opt/keplerops-cert ;; \
      *) true ;; \
    esac \
    && chmod 0755 /usr/local/bin/fieldkest-platform-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-platform-entrypoint"]
