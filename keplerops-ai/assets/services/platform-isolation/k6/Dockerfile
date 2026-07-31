ARG BASE_IMAGE=grafana/k6:2.0.0@sha256:a33a0cfdc4d2483d6b7a3a22e726a499ff2831a671a49239104cd34a9937523c
FROM ${BASE_IMAGE}

USER root
RUN mkdir -p /opt/keplerops-k6 /var/lib/keplerops-k6 \
    && chown -R 12345:12345 /opt/keplerops-k6 /var/lib/keplerops-k6
COPY --chown=12345:12345 assets/services/platform-isolation/k6/client.js /opt/keplerops-k6/client.js

ENV K6_NO_USAGE_REPORT=true \
    K6_OUT=json=/var/lib/keplerops-k6/metrics.ndjson \
    K6_LOG_OUTPUT=file=/var/lib/keplerops-k6/responses.ndjson \
    K6_LOG_FORMAT=raw
USER 12345:12345
WORKDIR /opt/keplerops-k6
ENTRYPOINT ["k6"]
CMD ["run", "/opt/keplerops-k6/client.js"]
