FROM python:3.9-slim-bookworm@sha256:a02e9c5406c416c504d6c9a1a306ff4080c3173f1008d192f953bd20382a2d5c

ARG OPENVOICE_REVISION=74a1d147b17a8c3092dd5430504bd83ef6c7eb23
ARG MELOTTS_REVISION=209145371cff8fc3bd60d7be902ea69cbdb7965a
ARG OPENVOICE_MODEL_REVISION=fd981100305a0e4291f93a9ad169c6d9f7bed54a

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential curl ffmpeg libavcodec-dev libavdevice-dev libavfilter-dev \
      libavformat-dev libavutil-dev libsndfile1 libswresample-dev libswscale-dev \
      mecab libmecab-dev mecab-ipadic-utf8 pkg-config \
    && rm -rf /var/lib/apt/lists/*
RUN install -d /opt/openvoice /opt/melotts /opt/openvoice/checkpoints_v2 \
    && curl -fsSL "https://github.com/myshell-ai/OpenVoice/archive/${OPENVOICE_REVISION}.tar.gz" \
      | tar -xz --strip-components=1 -C /opt/openvoice \
    && curl -fsSL "https://github.com/myshell-ai/MeloTTS/archive/${MELOTTS_REVISION}.tar.gz" \
      | tar -xz --strip-components=1 -C /opt/melotts
RUN python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
      torch==2.2.2+cpu torchaudio==2.2.2+cpu \
    && python -m pip install --no-cache-dir \
      huggingface-hub==0.27.1 \
      fastapi==0.116.1 faster-whisper==1.2.0 httpx==0.28.1 uvicorn==0.35.0 python-multipart==0.0.20 \
    && python -m pip install --no-cache-dir Cython==0.29.37 \
    && python -m pip install --no-cache-dir --no-build-isolation av==10.0.0 \
    && python -m pip install --no-cache-dir -e /opt/openvoice -e /opt/melotts \
    && python -m nltk.downloader -d /usr/local/share/nltk_data \
      averaged_perceptron_tagger averaged_perceptron_tagger_eng cmudict \
    && python -m unidic download
RUN python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="myshell-ai/OpenVoiceV2",
    revision="fd981100305a0e4291f93a9ad169c6d9f7bed54a",
    local_dir="/opt/openvoice/checkpoints_v2",
)
from faster_whisper import WhisperModel
WhisperModel("small.en", device="cpu", compute_type="int8", download_root="/opt/whisper")
PY

COPY openvoice/api.py /opt/cinder-media/api.py
COPY common/checkpoints.py /opt/cinder-media/checkpoints.py
WORKDIR /opt/cinder-media
ENV PYTHONPATH=/opt/openvoice:/opt/melotts
ENV WHISPER_DOWNLOAD_ROOT=/opt/whisper
EXPOSE 8080
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
