ARG RESEARCH_BASE_IMAGE=keplerops/orion-preview:campaign-v2
FROM ${RESEARCH_BASE_IMAGE}

USER root
RUN pip install --no-cache-dir redis==6.2.0
USER 10001:10001
