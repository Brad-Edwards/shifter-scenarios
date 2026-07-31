ARG BASE_IMAGE=python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PLATFORM_CAMERA_STATE_ROOT=/var/lib/keplerops-platform-camera \
    PLATFORM_CAMERA_ML_BASE_URL=http://platform-ml:8470 \
    PLATFORM_CAMERA_TLS_CERT_FILE=/run/tls/tls.crt \
    PLATFORM_CAMERA_TLS_KEY_FILE=/run/tls/tls.key \
    PLATFORM_CAMERA_TLS_SERVER_NAME=platform-camera \
    PLATFORM_CAMERA_ALLOW_PLAINTEXT=0

RUN groupadd --system --gid 65532 keplerops \
    && useradd --system --uid 65532 --gid keplerops --home-dir /nonexistent keplerops \
    && install -d -o keplerops -g keplerops -m 0700 /var/lib/keplerops-platform-camera

WORKDIR /opt/keplerops/platform-camera
COPY assets/services/platform-camera/requirements.txt ./requirements.txt
RUN python3 -m pip install --no-cache-dir --requirement requirements.txt
COPY --chown=0:0 assets/services/platform-camera/app.py ./app.py
COPY --chown=0:0 assets/services/platform-camera/storage.py ./storage.py
COPY --chown=0:0 assets/services/platform-camera/webrtc.py ./webrtc.py
COPY --chown=0:0 assets/services/platform-camera/reset.py ./reset.py
COPY --chown=0:0 assets/services/platform-camera/reset.sh ./reset.sh
COPY --chown=0:0 assets/services/platform-camera/entrypoint.sh ./entrypoint.sh
COPY --chown=0:0 assets/services/platform-camera/healthcheck.py ./healthcheck.py
COPY --chown=0:0 assets/services/platform-camera/static ./static
RUN chmod 0755 ./reset.sh ./entrypoint.sh

USER 65532:65532
EXPOSE 8480/tcp
VOLUME ["/var/lib/keplerops-platform-camera"]
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
  CMD ["python3", "./healthcheck.py"]
ENTRYPOINT ["./entrypoint.sh"]
