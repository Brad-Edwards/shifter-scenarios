FROM python:3.12.11-slim-bookworm
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV FIELDKEST_CHROMIUM=/opt/chromium/chrome
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl iproute2 unzip util-linux \
    && pip install --no-cache-dir playwright==1.55.0 \
    && playwright install-deps chromium \
    && curl -fsSLo /tmp/chromium.zip https://storage.googleapis.com/chrome-for-testing-public/140.0.7339.207/linux64/chrome-linux64.zip \
    && echo 'ba5e4c245945118a2b462749bec08ed6797b67559de5f49ab20186177d3b9ec7  /tmp/chromium.zip' | sha256sum -c - \
    && unzip -q /tmp/chromium.zip -d /opt \
    && mv /opt/chrome-linux64 /opt/chromium \
    && rm /tmp/chromium.zip \
    && chmod -R a+rX /opt/chromium \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system fieldkest-preview \
    && useradd --system --gid fieldkest-preview --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-preview \
    && groupadd --system fieldkest-renderer \
    && useradd --system --gid fieldkest-renderer --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-renderer \
    && mkdir -p /var/lib/fieldkest-preview/audit /var/lib/fieldkest-preview/browser-profiles \
    && chown -R fieldkest-preview:fieldkest-preview /var/lib/fieldkest-preview \
    && chown fieldkest-renderer:fieldkest-renderer /var/lib/fieldkest-preview/browser-profiles \
    && chmod 0750 /var/lib/fieldkest-preview \
    && chmod 0700 /var/lib/fieldkest-preview/browser-profiles
COPY build/keplerops/runtime/http_support.py /opt/fieldkest/http_support.py
COPY build/keplerops/runtime/platform_service.py /opt/fieldkest/platform_service.py
COPY build/keplerops/runtime/preview_worker.py /opt/fieldkest/preview_worker.py
COPY build/keplerops/runtime/platform-entrypoint.sh /usr/local/bin/fieldkest-platform-entrypoint
RUN ln -s /opt/fieldkest /opt/fieldkest-preview \
    && ln -s /opt/chromium/chrome /usr/bin/chromium \
    && chmod 0555 /opt/fieldkest/preview_worker.py /usr/local/bin/fieldkest-platform-entrypoint
EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldkest-platform-entrypoint"]
