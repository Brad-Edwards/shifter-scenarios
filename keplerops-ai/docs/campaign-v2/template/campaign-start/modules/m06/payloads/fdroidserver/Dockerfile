FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

ARG FDROIDSERVER_VERSION=2.2.1-1
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      apksigner "fdroidserver=${FDROIDSERVER_VERSION}" openjdk-17-jre-headless \
    && test "$(dpkg-query -W -f='${Version}' fdroidserver)" = "${FDROIDSERVER_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/fdroid
ENTRYPOINT ["fdroid"]
