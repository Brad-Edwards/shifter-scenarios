FROM debian:bookworm-slim AS browser

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://storage.googleapis.com/chrome-for-testing-public/128.0.6613.137/linux64/chrome-headless-shell-linux64.zip -o /tmp/chrome.zip \
    && echo 'ab945ee7dd4a86ff0eed01f48ef712e159066e9690259cbf275040f575c6cccd  /tmp/chrome.zip' | sha256sum -c - \
    && unzip -q /tmp/chrome.zip -d /opt

FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdrm2 libgbm1 libglib2.0-0 libgtk-3-0 libnspr4 libnss3 libx11-6 libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxkbcommon0 libxrandr2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2310 arwc-field-session \
    && groupadd --system --gid 2293 arwc-integration \
    && groupadd --system arwc-approval \
    && useradd --system --gid arwc-approval --groups arwc-field-session,arwc-integration --home-dir /var/lib/arwc-approval --shell /usr/sbin/nologin arwc-approval \
    && install -d -o arwc-approval -g arwc-approval -m 0750 /opt/maintenance-review

RUN pip install --no-cache-dir cryptography==42.0.8

COPY --from=browser /opt/chrome-headless-shell-linux64 /opt/chrome-headless-shell
RUN /opt/chrome-headless-shell/chrome-headless-shell --no-sandbox --version 2>&1 | grep -F '128.0.6613.137'
COPY --chown=arwc-approval:arwc-approval --chmod=0640 \
  build/arwc/runtime/maintenance_review.py /opt/maintenance-review/maintenance_review.py
COPY --chmod=0750 build/arwc/runtime/approval-entrypoint.sh /usr/local/sbin/arwc-approval-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-approval-entrypoint"]
