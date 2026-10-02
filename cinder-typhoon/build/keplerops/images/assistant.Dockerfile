FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates iproute2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.6.0 \
    && pip install --no-cache-dir transformers==4.48.3 huggingface-hub==0.28.1 safetensors==0.5.2 \
    && groupadd --system fieldkest-assistant \
    && useradd --system --gid fieldkest-assistant --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-assistant \
    && groupadd --system assistant-completion \
    && useradd --system --gid assistant-completion --home-dir /nonexistent --shell /usr/sbin/nologin svc-assistant-completion \
    && mkdir -p /var/lib/fieldkest-assistant/audit \
    && chown -R fieldkest-assistant:fieldkest-assistant /var/lib/fieldkest-assistant \
    && chmod 0700 /var/lib/fieldkest-assistant

RUN python3 -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen2.5-3B-Instruct', revision='14d7620ba47cf51be0b176e14e27e38a34d4ff88', local_dir='/opt/fieldkest-assistant/models/Qwen2.5-3B-Instruct', allow_patterns=['*.json','*.safetensors','*.model','*.txt','tokenizer*'])" \
    && find /opt/fieldkest-assistant/models/Qwen2.5-3B-Instruct -type f -exec chmod 0444 {} + \
    && find /opt/fieldkest-assistant/models/Qwen2.5-3B-Instruct -type d -exec chmod 0755 {} +

COPY build/keplerops/runtime/http_support.py /opt/fieldkest-assistant/http_support.py
COPY build/keplerops/runtime/platform_service.py /opt/fieldkest-assistant/platform_service.py
COPY build/keplerops/runtime/platform-entrypoint.sh /usr/local/bin/fieldkest-platform-entrypoint
COPY build/keplerops/config/completion-handover.json /var/lib/fieldkest-assistant/handovers/HANDOVER-COMP-2841.json
COPY build/keplerops/config/assistant-app.js /opt/fieldkest-assistant/web/app.js

RUN chmod 0444 /var/lib/fieldkest-assistant/handovers/HANDOVER-COMP-2841.json \
    && chmod 0644 /opt/fieldkest-assistant/web/app.js \
    && chown -R fieldkest-assistant:fieldkest-assistant /var/lib/fieldkest-assistant/handovers \
    && chmod 0755 /usr/local/bin/fieldkest-platform-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-platform-entrypoint"]
