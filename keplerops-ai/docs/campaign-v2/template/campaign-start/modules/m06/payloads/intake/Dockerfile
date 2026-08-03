FROM python:3.12.11-slim-bookworm
ARG TIKA_VERSION=3.2.2
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl default-jre-headless poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL "https://archive.apache.org/dist/tika/${TIKA_VERSION}/tika-app-${TIKA_VERSION}.jar" -o /opt/tika-app.jar \
    && curl -fsSL "https://archive.apache.org/dist/tika/${TIKA_VERSION}/tika-app-${TIKA_VERSION}.jar.sha512" -o /tmp/tika.sha512 \
    && printf '%s  %s\n' "$(awk '{print $1}' /tmp/tika.sha512)" /opt/tika-app.jar | sha512sum -c - \
    && rm /tmp/tika.sha512
RUN pip install --no-cache-dir fastapi==0.116.1 fastembed==0.7.1 httpx==0.28.1 \
      pydantic==2.11.7 python-multipart==0.0.20 uvicorn==0.35.0
WORKDIR /app
COPY intake/api.py /app/api.py
COPY common/checkpoints.py /app/checkpoints.py
RUN install -d -m 0770 -o 65532 -g 65532 /var/lib/partner-intake
USER 65532:65532
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
