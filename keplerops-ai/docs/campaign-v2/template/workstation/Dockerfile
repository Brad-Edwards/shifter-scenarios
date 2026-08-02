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

ARG LABGRID_VERSION
ARG LABGRID_WHEEL_SHA256
ARG LABGRID_CONSTRAINTS_SHA256

COPY --from=opencode /out/opencode /usr/local/bin/opencode
COPY --from=minio-client /usr/bin/mc /usr/local/bin/mc
COPY config/opencode/opencode.json /etc/opencode/opencode.json
COPY hardware/labgrid.constraints.txt /tmp/labgrid.constraints.txt
COPY hardware/participant-remote.yaml /etc/labgrid/participant-remote.yaml

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      jq \
      apktool \
      ffmpeg \
      imagemagick \
      libimage-exiftool-perl \
      mitmproxy \
      nmap \
      pipx \
      python3-venv \
      s3cmd \
      swaks \
      unzip \
      zbar-tools \
    && python3 -m venv /opt/labgrid-client \
    && printf '%s  %s\n' "${LABGRID_CONSTRAINTS_SHA256}" /tmp/labgrid.constraints.txt \
      | sha256sum -c - \
    && /opt/labgrid-client/bin/pip download \
      --disable-pip-version-check --no-deps --only-binary=:all: \
      --dest /tmp/labgrid-wheel "labgrid==${LABGRID_VERSION}" \
    && printf '%s  %s\n' "${LABGRID_WHEEL_SHA256}" \
      "/tmp/labgrid-wheel/labgrid-${LABGRID_VERSION}-py3-none-any.whl" \
      | sha256sum -c - \
    && /opt/labgrid-client/bin/pip install \
      --disable-pip-version-check --no-cache-dir \
      --constraint /tmp/labgrid.constraints.txt \
      "/tmp/labgrid-wheel/labgrid-${LABGRID_VERSION}-py3-none-any.whl" \
    && ln -s /opt/labgrid-client/bin/labgrid-client /usr/local/bin/labgrid-client \
    && apt-get clean \
    && find /var/lib/apt/lists -mindepth 1 -delete \
    && find /tmp/labgrid-wheel -mindepth 1 -delete \
    && rmdir /tmp/labgrid-wheel \
    && rm /tmp/labgrid.constraints.txt \
    && chmod 0644 /etc/opencode/opencode.json

COPY --chmod=0755 workstation/startup.sh /usr/local/bin/keplerops-v2-workstation-startup
COPY --chmod=0644 workstation/chromium.desktop /usr/local/share/keplerops/chromium.desktop
