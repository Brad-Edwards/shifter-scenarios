ARG AIRFLOW_IMAGE=keplerops/airflow:campaign-v2-clean
FROM ${AIRFLOW_IMAGE}

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*
USER airflow

RUN python -m pip install --no-cache-dir \
      lpips==0.1.4 \
      pillow==11.3.0

RUN python -c 'import lpips; lpips.LPIPS(net="alex")'
