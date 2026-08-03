ARG ORION_AGENT_IMAGE=keplerops/orion-agent:0.1.0

FROM node:20-bookworm-slim AS mcp-vulnerable
ADD https://github.com/sammcj/mcp-package-docs/archive/refs/tags/v0.1.26.tar.gz /tmp/mcp-package-docs-v0.1.26.tar.gz
RUN mkdir -p /opt/mcp-package-docs-vulnerable \
    && sha256sum /tmp/mcp-package-docs-v0.1.26.tar.gz >/opt/mcp-package-docs-vulnerable/UPSTREAM-ARCHIVE.sha256 \
    && tar -xzf /tmp/mcp-package-docs-v0.1.26.tar.gz --strip-components=1 -C /opt/mcp-package-docs-vulnerable \
    && test "$(node -p "require('/opt/mcp-package-docs-vulnerable/package.json').version")" = 0.1.26 \
    && grep -Fq 'execAsync(cmd)' /opt/mcp-package-docs-vulnerable/src/package-docs-server.ts \
    && grep -Fq 'go doc ${packageName}' /opt/mcp-package-docs-vulnerable/src/package-docs-server.ts \
    && cd /opt/mcp-package-docs-vulnerable \
    && npm install --ignore-scripts \
    && npm install --ignore-scripts --no-save cheerio@1.0.0 turndown@7.2.0 \
    && node -e "const fs=require('fs'); const p='node_modules/vscode-languageserver-protocol/package.json'; const j=JSON.parse(fs.readFileSync(p)); j.exports['./node.js']=j.exports['./node']; fs.writeFileSync(p, JSON.stringify(j, null, 2)+'\n');" \
    && (npm run build || test -f build/index.js) \
    && test -f build/index.js \
    && rm /tmp/mcp-package-docs-v0.1.26.tar.gz

FROM node:20-bookworm-slim AS mcp-patched-control
COPY vendor/mcp-package-docs-v0.1.27.tar.gz /tmp/mcp-package-docs-v0.1.27.tar.gz
RUN echo 'e0aae710aadf4b1d8ca9ece939d4de449da039faafb772c353f1a5d73055ffd1  /tmp/mcp-package-docs-v0.1.27.tar.gz' | sha256sum -c - \
    && mkdir -p /opt/mcp-package-docs-patched \
    && tar -xzf /tmp/mcp-package-docs-v0.1.27.tar.gz --strip-components=1 -C /opt/mcp-package-docs-patched \
    && grep -Fq 'safeGoDoc(packageName, symbol)' /opt/mcp-package-docs-patched/src/package-docs-server.ts \
    && cd /opt/mcp-package-docs-patched \
    && npm install --ignore-scripts \
    && npm install --ignore-scripts --no-save cheerio@1.0.0 turndown@7.2.0 \
    && node -e "const fs=require('fs'); const p='node_modules/vscode-languageserver-protocol/package.json'; const j=JSON.parse(fs.readFileSync(p)); j.exports['./node.js']=j.exports['./node']; fs.writeFileSync(p, JSON.stringify(j, null, 2)+'\n');" \
    && (npm run build || test -f build/index.js) \
    && rm /tmp/mcp-package-docs-v0.1.27.tar.gz

FROM ${ORION_AGENT_IMAGE}
USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      bubblewrap ca-certificates chromium curl ffmpeg golang-go openssl poppler-utils python3-venv strace \
    && apt-get clean \
    && find /var/lib/apt/lists -mindepth 1 -delete
COPY vendor/picklescan-0.0.20-py3-none-any.whl /tmp/picklescan-0.0.20-py3-none-any.whl
RUN echo '0f7380addf3a32f161ddec85d9fa1934cd39578e7e26ce1d947d25f03663bba5  /tmp/picklescan-0.0.20-py3-none-any.whl' | sha256sum -c - \
    && python -m pip install --no-cache-dir /tmp/picklescan-0.0.20-py3-none-any.whl \
      boto3==1.40.20 cryptography==45.0.6 devpi-client==7.3.0 \
      haystack-ai==2.17.1 minio==7.2.16 playwright==1.54.0 qdrant-client==1.15.1 \
    && python -m venv /opt/picklescan-patched \
    && /opt/picklescan-patched/bin/pip install --no-cache-dir picklescan==0.0.22 \
    && rm /tmp/picklescan-0.0.20-py3-none-any.whl
COPY --from=mcp-vulnerable /usr/local/bin/node /usr/local/bin/node
COPY --from=mcp-vulnerable /opt/mcp-package-docs-vulnerable /opt/mcp-package-docs-vulnerable
COPY --from=mcp-patched-control /opt/mcp-package-docs-patched /opt/mcp-package-docs-patched
COPY business_worker.py recipient-worker.py reset_runtime.py /app/
RUN mv /app/recipient-worker.py /app/recipient_worker.py \
    && install -d -m 0755 /state /work /run/keplerops
USER 0:0
CMD ["python", "/app/business_worker.py", "business"]
