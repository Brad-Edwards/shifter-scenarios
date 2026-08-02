ARG ORION_AGENT_IMAGE=keplerops/orion-agent:0.1.0
FROM node:20-bookworm-slim AS mcp-builder

COPY vendor/mcp-package-docs-v0.1.27.tar.gz /tmp/mcp-package-docs.tar.gz
RUN echo 'e0aae710aadf4b1d8ca9ece939d4de449da039faafb772c353f1a5d73055ffd1  /tmp/mcp-package-docs.tar.gz' | sha256sum -c - \
    && mkdir -p /opt/mcp-package-docs \
    && tar -xzf /tmp/mcp-package-docs.tar.gz --strip-components=1 -C /opt/mcp-package-docs \
    && cd /opt/mcp-package-docs \
    && sed -i 's#vscode-languageserver-protocol/node\.js#vscode-languageserver-protocol/node#' src/lsp/typescript-lsp-client.ts \
    && npm install --ignore-scripts \
    && npm install --ignore-scripts --no-save cheerio@1.0.0 turndown@7.2.0 \
    && (npm run build || test -f build/index.js) \
    && test -f build/tool-handlers.js \
    && chmod +x build/index.js \
    && npm cache clean --force \
    && rm /tmp/mcp-package-docs.tar.gz

FROM ${ORION_AGENT_IMAGE}

USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      bubblewrap ca-certificates chromium curl ffmpeg golang-go poppler-utils python3-venv \
    && apt-get clean \
    && find /var/lib/apt/lists -mindepth 1 -delete
COPY vendor/picklescan-0.0.20-py3-none-any.whl /tmp/picklescan-0.0.20-py3-none-any.whl
RUN echo '0f7380addf3a32f161ddec85d9fa1934cd39578e7e26ce1d947d25f03663bba5  /tmp/picklescan-0.0.20-py3-none-any.whl' | sha256sum -c - \
    && python -m pip install --no-cache-dir /tmp/picklescan-0.0.20-py3-none-any.whl \
    && rm /tmp/picklescan-0.0.20-py3-none-any.whl
COPY --from=mcp-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=mcp-builder /opt/mcp-package-docs /opt/mcp-package-docs
COPY campaign_service.py /app/campaign_service.py
USER 65532:65532
CMD ["uvicorn", "campaign_service:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
