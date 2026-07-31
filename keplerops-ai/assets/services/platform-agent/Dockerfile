ARG BASE_IMAGE=python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANGCHAIN_TRACING_V2=false \
    LANGSMITH_TRACING=false \
    PLATFORM_AGENT_DATA_ROOT=/var/lib/keplerops-platform-agent \
    PLATFORM_AGENT_DOCKER_SOCKET=unix:///run/keplerops-worker/docker.sock \
    PLATFORM_AGENT_WORKER_IMAGE=python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689

RUN groupadd --system --gid 65532 keplerops \
    && useradd --system --uid 65532 --gid keplerops --home-dir /nonexistent keplerops \
    && install -d -o keplerops -g keplerops -m 0700 /var/lib/keplerops-platform-agent

WORKDIR /opt/keplerops/platform-agent
COPY assets/services/platform-agent/requirements.txt ./requirements.txt
RUN python3 -m pip install --no-cache-dir --requirement requirements.txt
COPY assets/services/platform-agent/app.py ./app.py
COPY assets/services/platform-agent/runtime.py ./runtime.py
COPY assets/services/platform-agent/state.py ./state.py
COPY assets/services/platform-agent/workers.py ./workers.py

USER 65532:65532
EXPOSE 8470
HEALTHCHECK --interval=10s --timeout=3s --retries=6 \
  CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8470/readyz', timeout=2).read()"]
ENTRYPOINT ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8470", "--no-access-log", "--no-proxy-headers"]
