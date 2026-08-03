ARG ORION_AGENT_BASE=registry.keplerops.lab/orion-internal/orion-agent:release-runtime-2026.08
FROM ${ORION_AGENT_BASE}

USER 0:0
RUN install -d -m 0755 /etc/orion/config
COPY agent.yaml /etc/orion/config/agent.yaml
RUN chmod 0444 /etc/orion/config/agent.yaml
USER 65532:65532

ENV ORION_RUNTIME_CONFIG=/etc/orion/config/agent.yaml
CMD ["uvicorn", "release_assistant_extensions:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
