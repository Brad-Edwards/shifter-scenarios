FROM golang:1.22.12-bookworm AS collector

WORKDIR /src
COPY build/arwc/runtime/collector-crr.go ./main.go
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath \
    -ldflags='-buildid=COLLECT-CRR-12 -X main.buildID=COLLECT-CRR-12' \
    -o /collector-crr ./main.go

FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl openssl util-linux xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2290 arwc-handover \
    && groupadd --system --gid 2292 arwc-archive-source \
    && groupadd --system arwc-archive \
    && useradd --system --gid arwc-archive --home-dir /var/lib/arwc-archive --shell /usr/sbin/nologin arwc-archive \
    && usermod -a -G arwc-handover,arwc-archive-source arwc-archive \
    && install -d -o arwc-archive -g arwc-archive -m 0750 /opt/retained-archive

RUN pip install --no-cache-dir cryptography==42.0.8

RUN curl -fsSL https://www.7-zip.org/a/7z2301-linux-x64.tar.xz -o /tmp/7zip.tar.xz \
    && echo '23babcab045b78016e443f862363e4ab63c77d75bc715c0b3463f6134cbcf318  /tmp/7zip.tar.xz' | sha256sum -c - \
    && tar -xJf /tmp/7zip.tar.xz -C /usr/local/bin 7zz \
    && chmod 0755 /usr/local/bin/7zz

COPY --chown=arwc-archive:arwc-archive --chmod=0640 \
  build/arwc/runtime/retained_archive.py /opt/retained-archive/retained_archive.py
COPY --chown=arwc-archive:arwc-archive --chmod=0640 \
  build/arwc/runtime/generate_archive_artifacts.py /opt/retained-archive/generate_archive_artifacts.py
COPY --from=collector --chown=arwc-archive:arwc-archive --chmod=0750 \
  /collector-crr /opt/retained-archive/collector-crr
COPY --chmod=0750 build/arwc/runtime/archive-entrypoint.sh /usr/local/sbin/arwc-archive-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-archive-entrypoint"]
