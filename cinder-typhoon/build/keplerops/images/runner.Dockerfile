FROM docker:29-cli@sha256:018edbc908e08fcc9dbf029c812c34251e9b4719e6f71ca0e5eae2a987d014ca AS docker-cli
FROM python:3.12.11-slim-bookworm

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY build/keplerops/runtime/report_runner.py /opt/fieldkest-runner/report_runner.py
RUN mkdir -p /run/fieldkest-runner && chmod 0777 /run/fieldkest-runner
ENTRYPOINT ["python3", "/opt/fieldkest-runner/report_runner.py"]
