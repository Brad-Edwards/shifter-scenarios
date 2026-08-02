ARG LABGRID_BASE_IMAGE=python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7
FROM ${LABGRID_BASE_IMAGE} AS labgrid-runtime

ARG LABGRID_VERSION
ARG LABGRID_WHEEL_SHA256
ARG LABGRID_CONSTRAINTS_SHA256

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

COPY labgrid.constraints.txt /tmp/labgrid.constraints.txt

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      gstreamer1.0-plugins-base \
      gstreamer1.0-plugins-good \
      gstreamer1.0-tools \
      jq \
      microcom \
      openssh-client \
      rsync \
      ser2net \
      sispmctl \
      socat \
      udev \
      usbutils \
      v4l-utils \
      zbar-tools; \
    printf '%s  %s\n' \
      "${LABGRID_CONSTRAINTS_SHA256}" \
      "/tmp/labgrid.constraints.txt" \
      | sha256sum -c -; \
    python -m pip download \
      --disable-pip-version-check \
      --no-deps \
      --only-binary=:all: \
      --dest /tmp/labgrid-wheel \
      "labgrid==${LABGRID_VERSION}"; \
    printf '%s  %s\n' \
      "${LABGRID_WHEEL_SHA256}" \
      "/tmp/labgrid-wheel/labgrid-${LABGRID_VERSION}-py3-none-any.whl" \
      | sha256sum -c -; \
    python -m pip install \
      --disable-pip-version-check \
      --no-cache-dir \
      --constraint /tmp/labgrid.constraints.txt \
      "/tmp/labgrid-wheel/labgrid-${LABGRID_VERSION}-py3-none-any.whl"; \
    python -c 'from labgrid.util import labgrid_version; print(labgrid_version())' \
      | grep -Fx "${LABGRID_VERSION}"; \
    rm -r /tmp/labgrid-wheel /tmp/labgrid.constraints.txt /var/lib/apt/lists/*

FROM labgrid-runtime AS labgrid-coordinator
WORKDIR /opt/coordinator
EXPOSE 20408
CMD ["labgrid-coordinator", "--listen", "0.0.0.0:20408"]

FROM labgrid-runtime AS labgrid-client
CMD ["sleep", "infinity"]

FROM labgrid-runtime AS labgrid-exporter
VOLUME ["/var/cache/labgrid"]
CMD ["labgrid-exporter", "--help"]
