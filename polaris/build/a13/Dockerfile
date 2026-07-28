FROM python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df
COPY A13-brain/server.py /app/server.py
WORKDIR /app
EXPOSE 9100
CMD ["python3", "server.py"]
