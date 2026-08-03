ARG ORION_AGENT_BASE=registry.keplerops.lab/orion-internal/orion-agent:release-runtime-2026.08
FROM ${ORION_AGENT_BASE}

USER 0:0
RUN install -d -m 0755 /etc/orion-tools
COPY tool/release-source.json /etc/orion-tools/release-source.json
RUN chmod 0444 /etc/orion-tools/release-source.json /app/release_source_service.py
USER 65532:65532

CMD ["python", "/app/release_source_service.py"]
