FROM python:3.12-slim-bookworm@sha256:2a20c6af4bf8af8499f84d87eb21e35119c343ff0e06b317ba064f474734f5e9
RUN python -m pip install --no-cache-dir fastapi==0.115.6 httpx==0.28.1 uvicorn==0.34.0
COPY api.py /opt/partner-intake/api.py
WORKDIR /opt/partner-intake
EXPOSE 8080
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
