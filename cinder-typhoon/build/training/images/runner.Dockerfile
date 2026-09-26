FROM docker:29-cli@sha256:018edbc908e08fcc9dbf029c812c34251e9b4719e6f71ca0e5eae2a987d014ca AS docker-cli
FROM python:3.12.11-slim-bookworm

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

COPY build/training/runtime/runner_controller.py /opt/cinder-runner/runner_controller.py
RUN mkdir -p /run/cinder-runner && chmod 0777 /run/cinder-runner

ENTRYPOINT ["python3", "/opt/cinder-runner/runner_controller.py"]
