ARG BASE_IMAGE=python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    PLATFORM_ML_STATE_ROOT=/var/lib/keplerops-platform-ml

RUN groupadd --system --gid 65532 keplerops \
    && useradd --system --uid 65532 --gid keplerops --home-dir /nonexistent keplerops \
    && install -d -o keplerops -g keplerops -m 0700 /var/lib/keplerops-platform-ml

WORKDIR /opt/keplerops/platform-ml
COPY assets/services/platform-ml/requirements.txt ./requirements.txt
RUN python3 -m pip install --no-cache-dir --requirement requirements.txt
COPY --chown=0:0 assets/services/platform-ml/app.py ./app.py
COPY --chown=0:0 assets/services/platform-ml/events.py ./events.py
COPY --chown=0:0 assets/services/platform-ml/models.py ./models.py
COPY --chown=0:0 assets/services/platform-ml/reset.py ./reset.py
COPY --chown=0:0 assets/services/platform-ml/reset.sh ./reset.sh
COPY --chown=0:0 assets/services/platform-ml/seed ./seed
RUN chmod 0755 ./reset.sh

USER 65532:65532
EXPOSE 8470
VOLUME ["/var/lib/keplerops-platform-ml"]
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=9 \
  CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8470/readyz', timeout=2).read()"]
ENTRYPOINT ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8470", "--workers", "1", "--no-access-log", "--no-proxy-headers"]
