ARG ORION_AGENT_IMAGE=keplerops/orion-agent:0.1.0
FROM ${ORION_AGENT_IMAGE}

USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      bubblewrap ca-certificates python3-venv \
    && apt-get clean \
    && find /var/lib/apt/lists -mindepth 1 -delete
COPY campaign_service.py /app/campaign_service.py
USER 65532:65532
CMD ["uvicorn", "campaign_service:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
