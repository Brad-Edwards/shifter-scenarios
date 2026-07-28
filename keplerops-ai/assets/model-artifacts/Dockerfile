ARG BASE_IMAGE=vllm/vllm-openai@sha256:d731ee65c044ae0977421eed3d93f931d4b7d79614394184c939db35b8f28fc2
FROM ${BASE_IMAGE}

COPY assets/model-artifacts/model.yaml /opt/keplerops/model.yaml
COPY assets/model-artifacts/fetch_model.py /opt/keplerops/fetch_model.py
COPY assets/model-artifacts/register_model.py /opt/keplerops/register_model.py
RUN python3 -m pip install --no-cache-dir boto3==1.40.20 \
    && python3 /opt/keplerops/fetch_model.py --manifest /opt/keplerops/model.yaml --output /models/teacher \
    && groupadd --system --gid 65532 keplerops \
    && useradd --system --uid 65532 --gid keplerops --home-dir /nonexistent keplerops \
    && chown -R 65532:65532 /models

ENV HOME=/tmp HF_HOME=/tmp/.cache
USER 65532:65532
ENTRYPOINT ["python3", "-m", "vllm.entrypoints.openai.api_server"]
CMD ["--model", "/models/teacher", "--served-model-name", "keplerops-teacher", "--host", "0.0.0.0", "--port", "8000"]
