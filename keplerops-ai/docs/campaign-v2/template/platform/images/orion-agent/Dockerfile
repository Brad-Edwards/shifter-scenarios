FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp \
    TMPDIR=/tmp

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY agent_service.py mcp_service.py campaign_m01.py vertex_proxy.py /app/

USER 65532:65532
EXPOSE 8080 8081 8082
CMD ["uvicorn", "agent_service:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
