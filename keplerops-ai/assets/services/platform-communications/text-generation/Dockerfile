FROM python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689 AS model-fetch

COPY assets/services/platform-communications/text-generation/model-manifest.json /opt/build/model-manifest.json
COPY assets/services/platform-communications/text-generation/fetch_model.py /opt/build/fetch_model.py
RUN python /opt/build/fetch_model.py

FROM ghcr.io/ggml-org/llama.cpp@sha256:b832a7b7252a90a79a1e8d23d9be3ac5261a33224f60682dff0cade412fa55d3

COPY --from=model-fetch --chown=65534:65534 /models /models
USER 65534:65534
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=4s --start-period=60s --retries=12 \
  CMD curl --fail --silent --show-error http://127.0.0.1:8080/health || exit 1

CMD ["--model", "/models/Qwen3-0.6B-Q8_0.gguf", "--host", "0.0.0.0", "--port", "8080", "--ctx-size", "4096", "--n-predict", "512", "--parallel", "1", "--jinja", "--reasoning", "off"]
