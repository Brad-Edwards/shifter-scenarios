FROM python:3.12.11-slim-bookworm
RUN pip install --no-cache-dir fastapi==0.116.1 httpx==0.28.1 pydantic==2.11.7 uvicorn==0.35.0
WORKDIR /app
COPY api.py /app/api.py
RUN install -d -m 0770 -o 65532 -g 65532 /var/lib/cinder-bridge
USER 65532:65532
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
