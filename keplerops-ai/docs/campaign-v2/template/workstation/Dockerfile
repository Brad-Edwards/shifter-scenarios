ARG OPENCODE_BUILDER_IMAGE=node:22.18-bookworm-slim@sha256:752ea8a2f758c34002a0461bd9f1cee4f9a3c36d48494586f60ffce1fc708e0e
ARG MINIO_CLIENT_IMAGE=minio/mc:RELEASE.2025-07-21T05-28-08Z
ARG KALI_WORKSTATION_IMAGE=europe-west4-docker.pkg.dev/prod-ksqdkj/keplerops-555-a/keplerops/kali-browser-terminal:fbc140f08fec-r13@sha256:b0abddb29e02a363a7ead954eac7020da1d9212c5cb75c85ee2ab66957bdb879

FROM ${OPENCODE_BUILDER_IMAGE} AS opencode

ARG OPENCODE_VERSION
RUN npm install -g "opencode-ai@${OPENCODE_VERSION}" \
    && install -D -m 0755 "$(readlink -f "$(command -v opencode)")" /out/opencode

FROM ${MINIO_CLIENT_IMAGE} AS minio-client

FROM ${KALI_WORKSTATION_IMAGE}

USER root

COPY --from=opencode /out/opencode /usr/local/bin/opencode
COPY --from=minio-client /usr/bin/mc /usr/local/bin/mc
COPY config/opencode/opencode.json /etc/opencode/opencode.json

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      jq \
      pipx \
      python3-venv \
      s3cmd \
      swaks \
    && apt-get clean \
    && find /var/lib/apt/lists -mindepth 1 -delete \
    && chmod 0644 /etc/opencode/opencode.json
