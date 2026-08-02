FROM python:3.12.11-slim-bookworm
ARG COSIGN_VERSION=2.5.3
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl ffmpeg proot skopeo umoci \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-amd64" -o /usr/local/bin/cosign \
    && chmod 0755 /usr/local/bin/cosign
RUN pip install --no-cache-dir adversarial-robustness-toolbox==1.20.1 fastapi==0.116.1 \
      httpx==0.28.1 numpy==2.1.3 onnxruntime==1.22.1 pydantic==2.11.7 \
      PyYAML==6.0.2 scikit-learn==1.6.1 tokenizers==0.21.4 uvicorn==0.35.0
WORKDIR /app
COPY release-registry/api.py /app/api.py
COPY common/checkpoints.py /app/checkpoints.py
RUN install -d -m 0770 -o 65532 -g 65532 /var/lib/cinder-release-registry
USER 65532:65532
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
