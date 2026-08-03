FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp \
    TMPDIR=/tmp \
    MODEL_DIR=/models

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY artifacts/ /models/
COPY app.py /app/app.py

RUN python -c 'import json, onnxruntime as ort; from pathlib import Path; root=Path("/models"); assert len(json.loads((root/"label-map.json").read_text())) == 8; ort.InferenceSession(str(root/"orion-release-risk.onnx"), providers=["CPUExecutionProvider"])'

USER 65532:65532
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
