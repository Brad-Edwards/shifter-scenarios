FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl openssl util-linux xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2290 arwc-handover \
    && groupadd --system arwc-archive \
    && useradd --system --gid arwc-archive --home-dir /var/lib/arwc-archive --shell /usr/sbin/nologin arwc-archive \
    && usermod -a -G arwc-handover arwc-archive \
    && install -d -o arwc-archive -g arwc-archive -m 0750 /opt/retained-archive

RUN curl -fsSL https://www.7-zip.org/a/7z2301-linux-x64.tar.xz -o /tmp/7zip.tar.xz \
    && echo '23babcab045b78016e443f862363e4ab63c77d75bc715c0b3463f6134cbcf318  /tmp/7zip.tar.xz' | sha256sum -c - \
    && tar -xJf /tmp/7zip.tar.xz -C /usr/local/bin 7zz \
    && chmod 0755 /usr/local/bin/7zz

COPY --chown=arwc-archive:arwc-archive --chmod=0640 \
  build/arwc/runtime/retained_archive.py /opt/retained-archive/retained_archive.py
COPY --chmod=0750 build/arwc/runtime/archive-entrypoint.sh /usr/local/sbin/arwc-archive-entrypoint

EXPOSE 443
ENTRYPOINT ["/usr/local/sbin/arwc-archive-entrypoint"]
