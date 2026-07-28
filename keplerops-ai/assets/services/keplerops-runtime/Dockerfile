ARG BASE_IMAGE=python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    KEPLEROPS_CONFIG=/etc/keplerops/runtime.yaml

RUN apt-get update \
    && apt-get install --yes --no-install-recommends python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 65532 keplerops \
    && useradd --system --uid 65532 --gid keplerops --home-dir /nonexistent keplerops

WORKDIR /opt/keplerops
COPY assets/services/keplerops-runtime/requirements.txt ./requirements.txt
RUN python3 -m pip install --break-system-packages --no-cache-dir --requirement requirements.txt
COPY assets/services/keplerops-runtime/app.py ./app.py
COPY assets/services/keplerops-runtime/keplerops_runtime ./keplerops_runtime
COPY assets/services/keplerops-runtime/green_activity ./green_activity
COPY assets/services/keplerops-runtime/agent_persistence.py ./agent_persistence.py
COPY assets/services/keplerops-runtime/adversarial_input.py ./adversarial_input.py
COPY assets/services/keplerops-runtime/training_poisoning.py ./training_poisoning.py
COPY assets/services/keplerops-runtime/model_extraction.py ./model_extraction.py
COPY assets/services/keplerops-runtime/agent_control.py ./agent_control.py
COPY assets/services/keplerops-runtime/model_evasion.py ./model_evasion.py
COPY assets/services/keplerops-runtime/model_supply.py ./model_supply.py
COPY assets/services/keplerops-runtime/workhub_credentials.py ./workhub_credentials.py
COPY assets/services/keplerops-runtime/context_poisoning.py ./context_poisoning.py
COPY assets/services/keplerops-runtime/context_expansion.py ./context_expansion.py
COPY assets/services/keplerops-runtime/model_secrets.py ./model_secrets.py
COPY assets/services/keplerops-runtime/model_secrets_expansion.py ./model_secrets_expansion.py
COPY assets/services/keplerops-runtime/agent_persistence_expansion.py ./agent_persistence_expansion.py
COPY assets/services/keplerops-runtime/domain.py ./domain.py
COPY assets/services/keplerops-runtime/oracle_domain.py ./oracle_domain.py
COPY assets/services/keplerops-runtime/research_domain.py ./research_domain.py
COPY assets/services/keplerops-runtime/research.py ./research.py
COPY assets/services/keplerops-runtime/research_readback.py ./research_readback.py
COPY assets/services/keplerops-runtime/instrumentation.py ./instrumentation.py
COPY aces_contract.py ./aces_contract.py
COPY ctfd/plugins/keplerops_oracle_flags/receipt.py ./receipt.py
COPY telemetry/data-dictionary.md /opt/keplerops/telemetry/data-dictionary.md
COPY sdl/ /opt/keplerops/sdl/
COPY assets/content/datasets/context.jsonl /opt/keplerops/environment/context.jsonl
COPY assets/content/datasets/distillation.jsonl /opt/keplerops/environment/distillation.jsonl

USER 65532:65532
EXPOSE 8443
ENTRYPOINT ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8443", "--no-access-log", "--no-proxy-headers"]
