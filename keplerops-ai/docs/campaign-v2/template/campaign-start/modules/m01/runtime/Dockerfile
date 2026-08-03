ARG ORION_AGENT_IMAGE=keplerops/orion-agent:0.1.0
FROM ${ORION_AGENT_IMAGE}

USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates openssl python3-venv \
    && pip install --no-cache-dir pika==1.3.2 requests==2.32.4 \
    && apt-get clean \
    && find /var/lib/apt/lists -mindepth 1 -delete
COPY review_workers.py /app/review_workers.py
USER 65532:65532
CMD ["python", "/app/review_workers.py", "dispatcher"]
