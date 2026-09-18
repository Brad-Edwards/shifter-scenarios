# Python 3.12 slim; reviewed wheels are the entire build input.
FROM python@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf
LABEL org.opencontainers.image.source="https://github.com/PaloAltoNetworks/shifter-scenarios"
COPY wheels/ /wheels/
RUN python -m pip install --no-cache-dir --no-index --require-hashes -r /wheels/requirements.txt \
    && python -m pip check
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 65532:65532
ENTRYPOINT ["python", "-m", "shifter_adapter_sdk.worker"]
