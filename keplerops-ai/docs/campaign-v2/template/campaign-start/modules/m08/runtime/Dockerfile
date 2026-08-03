ARG AIRFLOW_IMAGE=keplerops/airflow:campaign-v2-clean
FROM ${AIRFLOW_IMAGE}

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends bubblewrap openssl \
    && rm -rf /var/lib/apt/lists/*
USER airflow

RUN python -m pip install --no-cache-dir --no-deps \
      lpips==0.1.4 \
      pillow==11.3.0 \
    && python -m pip install --no-cache-dir --no-deps \
      --index-url https://download.pytorch.org/whl/cpu \
      torchvision==0.23.0+cpu

RUN python -c 'import lpips; lpips.LPIPS(net="alex")'
