ARG PREVIEW_BASE_IMAGE=python:3.12.11-slim-bookworm
FROM ${PREVIEW_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/orion-preview
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --requirement requirements.txt \
    && addgroup --system --gid 10001 keplerops \
    && adduser --system --uid 10001 --ingroup keplerops keplerops \
    && install -d -o 10001 -g 10001 -m 0755 /var/lib/orion-preview/audit

COPY app ./app
USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
