ARG BASE_IMAGE=python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLATFORM_IMPACT_DATA_ROOT=/var/lib/keplerops-platform-impact

RUN groupadd --system --gid 65532 keplerops \
    && useradd --system --uid 65532 --gid keplerops --home-dir /nonexistent keplerops \
    && install -d -o keplerops -g keplerops -m 0700 /var/lib/keplerops-platform-impact

WORKDIR /opt/keplerops/platform-impact
COPY assets/services/platform-impact/requirements.txt ./requirements.txt
RUN python3 -m pip install --no-cache-dir --requirement requirements.txt
COPY assets/services/platform-impact/app.py ./app.py
COPY assets/services/platform-impact/database.py ./database.py
COPY assets/services/platform-impact/engines.py ./engines.py

USER 65532:65532
EXPOSE 8460
HEALTHCHECK --interval=10s --timeout=3s --retries=6 \
  CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8460/readyz', timeout=2).read()"]
ENTRYPOINT ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8460", "--no-access-log", "--no-proxy-headers"]
