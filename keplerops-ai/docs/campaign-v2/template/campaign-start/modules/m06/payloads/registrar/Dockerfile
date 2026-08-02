FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b
RUN python -m pip install --no-cache-dir fastapi==0.115.6 uvicorn==0.34.0
COPY api.py /app/api.py
WORKDIR /app
EXPOSE 8080
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
