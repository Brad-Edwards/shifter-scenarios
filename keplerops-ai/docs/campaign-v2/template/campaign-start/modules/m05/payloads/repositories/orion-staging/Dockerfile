FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

RUN pip install --no-cache-dir fastapi==0.116.1 uvicorn==0.35.0
COPY app.py /app/app.py
COPY model/orion-model.pkl /models/orion-model.pkl
USER 65532:65532
CMD ["uvicorn", "app:app", "--app-dir", "/app", "--host", "0.0.0.0", "--port", "8080"]
