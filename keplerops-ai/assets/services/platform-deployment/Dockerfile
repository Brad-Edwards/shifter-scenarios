ARG BASE_IMAGE=python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PLATFORM_DEPLOYMENT_STATE_ROOT=/var/lib/keplerops-platform-deployment \
    PLATFORM_DEPLOYMENT_POLICY=/run/keplerops/deployment-policy.json \
    PLATFORM_DEPLOYMENT_TOKEN_FILE=/run/keplerops/platform-deployment-token \
    PLATFORM_DEPLOYMENT_REGISTRY_TOKEN_FILE=/run/keplerops/gitea-registry-token \
    PLATFORM_DEPLOYMENT_SIGNING_KEY_FILE=/run/keplerops/reputation-signing-key \
    PLATFORM_DEPLOYMENT_CA_FILE=/run/tls/ca.crt

RUN groupadd --system --gid 65532 keplerops \
    && useradd --system --uid 65532 --gid keplerops --home-dir /nonexistent keplerops \
    && install -d -o keplerops -g keplerops -m 0700 /var/lib/keplerops-platform-deployment

WORKDIR /opt/keplerops/platform-deployment
COPY assets/services/platform-deployment/requirements.txt ./requirements.txt
RUN python3 -m pip install --no-cache-dir --requirement requirements.txt
COPY --chown=0:0 assets/services/platform-deployment/*.py ./
COPY --chown=0:0 assets/services/platform-deployment/policy-template.json ./policy-template.json
COPY --chown=0:0 assets/services/platform-deployment/entrypoint.sh ./entrypoint.sh
RUN chmod 0755 ./entrypoint.sh

USER 65532:65532
EXPOSE 8490
VOLUME ["/var/lib/keplerops-platform-deployment"]
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
  CMD ["python3", "/opt/keplerops/platform-deployment/healthcheck.py"]
ENTRYPOINT ["/opt/keplerops/platform-deployment/entrypoint.sh"]
CMD ["api"]
