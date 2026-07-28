ARG BASE_IMAGE=docker:29.6.1-dind-rootless@sha256:371962f4344295a1eb185f1c9e62064bf4503a7beb8c6e73be3405500041784b
FROM ${BASE_IMAGE}

ENV DOCKER_HOST=unix:///run/user/1000/docker.sock \
    DOCKER_TLS_CERTDIR=

VOLUME ["/run/user/1000"]
HEALTHCHECK --interval=10s --timeout=3s --retries=12 \
  CMD ["docker", "--host=unix:///run/user/1000/docker.sock", "info"]
CMD ["--host=unix:///run/user/1000/docker.sock", "--label", "keplerops.engine.role=bounded-workers"]
