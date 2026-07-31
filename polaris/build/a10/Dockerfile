FROM python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df
RUN pip install --no-cache-dir pymodbus==3.12.1
# server.py lives in A10-tail-controller/ per content-dir convention;
# build context is the parent mechag/ dir.
COPY A10-tail-controller/server.py /app/server.py
WORKDIR /app
# Production port 502
CMD ["python3", "server.py"]
