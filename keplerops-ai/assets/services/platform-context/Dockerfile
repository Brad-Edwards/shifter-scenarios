ARG BASE_IMAGE=python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PLATFORM_CONTEXT_STATE_ROOT=/var/lib/keplerops-platform-context \
    PLATFORM_CONTEXT_CONFIG=/opt/keplerops/platform-context/config/context-v1.json

RUN groupadd --system --gid 65532 keplerops \
    && useradd --system --uid 65532 --gid keplerops --home-dir /nonexistent keplerops \
    && install -d -o keplerops -g keplerops -m 0700 /var/lib/keplerops-platform-context

WORKDIR /opt/keplerops/platform-context
COPY assets/services/platform-context/requirements.txt ./requirements.txt
RUN python3 -m pip install --no-cache-dir --requirement requirements.txt
COPY --chown=0:0 assets/services/platform-context/api.py ./app.py
COPY --chown=0:0 assets/services/platform-context/entrypoint.sh ./entrypoint.sh
COPY --chown=0:0 assets/services/platform-context/file_worker.py ./file_worker.py
COPY --chown=0:0 assets/services/platform-context/healthcheck.py ./healthcheck.py
COPY --chown=0:0 assets/services/platform-context/reset.py ./reset.py
COPY --chown=0:0 assets/services/platform-context/reset.sh ./reset.sh
COPY --chown=0:0 assets/services/platform-context/security.py ./security.py
COPY --chown=0:0 assets/services/platform-context/store.py ./store.py
COPY --chown=0:0 assets/services/platform-context/sync_worker.py ./sync_worker.py
COPY --chown=0:0 assets/services/platform-context/upstreams.py ./upstreams.py
COPY --chown=0:0 assets/services/platform-context/config ./config
RUN chmod 0755 ./entrypoint.sh ./reset.sh

USER 65532:65532
EXPOSE 8480
VOLUME ["/var/lib/keplerops-platform-context"]
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
  CMD ["python3", "/opt/keplerops/platform-context/healthcheck.py"]
ENTRYPOINT ["/opt/keplerops/platform-context/entrypoint.sh"]
CMD ["api"]
