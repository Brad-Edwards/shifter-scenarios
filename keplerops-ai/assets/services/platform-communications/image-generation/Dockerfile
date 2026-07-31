FROM python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689 AS model-fetch

COPY assets/services/platform-communications/image-generation/source-model-manifest.json /opt/build/source-model-manifest.json
COPY assets/services/platform-communications/image-generation/fetch_snapshot.py assets/services/platform-communications/image-generation/hash_tree.py /opt/build/
RUN python /opt/build/fetch_snapshot.py \
    && python /opt/build/hash_tree.py

FROM python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    IMAGE_MODEL_PATH=/opt/keplerops/model/flux1-schnell-int4-ov \
    IMAGE_MODEL_ID=OpenVINO/FLUX.1-schnell-int4-ov \
    IMAGE_MODEL_REVISION=67f2ca1b786f707a3c1a7a1f0ae179641249f0c2

COPY assets/services/platform-communications/image-generation/requirements.txt /opt/keplerops/requirements.txt
RUN python -m pip install --requirement /opt/keplerops/requirements.txt
COPY --from=model-fetch /model/flux1-schnell-int4-ov /opt/keplerops/model/flux1-schnell-int4-ov
COPY assets/services/platform-communications/image-generation/app.py assets/services/platform-communications/image-generation/adapters.py assets/services/platform-communications/image-generation/service.py assets/services/platform-communications/image-generation/schema.sql /opt/keplerops/

USER 65534:65534
WORKDIR /opt/keplerops
EXPOSE 8092
HEALTHCHECK --interval=15s --timeout=5s --start-period=600s --retries=12 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8092/healthz/ready', timeout=3)" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8092", "--workers", "1", "--no-access-log"]
