FROM python:3.12.11-slim-bookworm
RUN pip install --no-cache-dir fastapi==0.116.1 httpx==0.28.1 pydantic==2.11.7 uvicorn==0.35.0
WORKDIR /app
COPY developer/api.py /app/api.py
COPY common/checkpoints.py /app/checkpoints.py
USER 65532:65532
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
