ARG RUNNER_IMAGE=keplerops/forgejo-runner:campaign-v2-clean
FROM ${RUNNER_IMAGE}
USER root
RUN apt-get update \
    && apt-get install --yes --no-install-recommends poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
RUN /opt/kepler-ci/bin/pip install --no-cache-dir \
      labgrid==25.0 \
      minio==7.2.15 \
      numpy==2.1.3 \
      onnxruntime==1.20.1 \
      pyyaml==6.0.2 \
      tokenizers==0.21.0 \
      qdrant-client==1.12.1
