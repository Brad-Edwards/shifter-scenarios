FROM debian:bookworm-slim AS browser

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://storage.googleapis.com/chrome-for-testing-public/128.0.6613.137/linux64/chrome-headless-shell-linux64.zip -o /tmp/chrome.zip \
    && echo 'ab945ee7dd4a86ff0eed01f48ef712e159066e9690259cbf275040f575c6cccd  /tmp/chrome.zip' | sha256sum -c - \
    && unzip -q /tmp/chrome.zip -d /opt

FROM golang:1.22.12-bookworm AS collector

WORKDIR /src
COPY build/arwc/runtime/collector-crr.go ./main.go
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath \
    -ldflags='-buildid=COLLECT-CRR-12 -X main.buildID=COLLECT-CRR-12' \
    -o /collector-crr ./main.go

FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        ca-certificates curl openssl util-linux xz-utils \
        fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
        libcups2 libdrm2 libgbm1 libglib2.0-0 libgtk-3-0 libnspr4 libnss3 \
        libx11-6 libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 \
        libxkbcommon0 libxrandr2 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2290 arwc-handover \
    && groupadd --system --gid 2292 arwc-archive-source \
    && groupadd --system --gid 2295 arwc-plan-evidence \
    && groupadd --system arwc-archive \
    && useradd --system --gid arwc-archive --home-dir /var/lib/arwc-archive --shell /usr/sbin/nologin arwc-archive \
    && usermod -a -G arwc-handover,arwc-archive-source,arwc-plan-evidence arwc-archive \
    && install -d -o arwc-archive -g arwc-archive -m 0750 /opt/retained-archive

COPY --from=browser /opt/chrome-headless-shell-linux64 /opt/chrome-headless-shell
RUN /opt/chrome-headless-shell/chrome-headless-shell --no-sandbox --version 2>&1 | grep -F '128.0.6613.137'

RUN pip install --no-cache-dir cryptography==50.0.2 psycopg2-binary==2.9.10

RUN curl -fsSL https://www.7-zip.org/a/7z2301-linux-x64.tar.xz -o /tmp/7zip.tar.xz \
    && echo '23babcab045b78016e443f862363e4ab63c77d75bc715c0b3463f6134cbcf318  /tmp/7zip.tar.xz' | sha256sum -c - \
    && tar -xJf /tmp/7zip.tar.xz -C /usr/local/bin 7zz \
    && chmod 0755 /usr/local/bin/7zz

COPY --chown=arwc-archive:arwc-archive --chmod=0640 \
  build/arwc/runtime/retained_archive.py /opt/retained-archive/retained_archive.py
COPY --chown=arwc-archive:arwc-archive --chmod=0640 \
  build/arwc/runtime/generate_archive_artifacts.py /opt/retained-archive/generate_archive_artifacts.py
COPY --chown=arwc-archive:arwc-archive --chmod=0640 \
  build/arwc/runtime/fetch_archive_workflow.py /opt/retained-archive/fetch_archive_workflow.py
COPY --from=collector --chown=arwc-archive:arwc-archive --chmod=0750 \
  /collector-crr /opt/retained-archive/collector-crr
COPY --chmod=0755 build/arwc/runtime/arwc_handover.py /usr/local/libexec/arwc-handover.py
COPY --chmod=0750 build/arwc/runtime/archive-entrypoint.sh /usr/local/sbin/arwc-archive-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-archive-entrypoint"]
