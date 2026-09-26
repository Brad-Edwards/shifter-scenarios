FROM kalilinux/kali-rolling@sha256:30399bd65187e06525008dd13eecc2b3439d26a82b2c6b0ba32dee72bd843117

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
      ca-certificates=20260601 \
      curl=8.21.0-2 \
      git=1:2.53.0-1 \
      jq=1.8.2-1 \
      python3=3.14.7-3 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 2000 cinder \
    && useradd --uid 2000 --gid cinder --create-home --shell /bin/bash cinder

COPY --chown=cinder:cinder assets/training/workstation/TRAINING.md /home/cinder/TRAINING.md
RUN chmod 0444 /home/cinder/TRAINING.md

USER cinder
WORKDIR /home/cinder
CMD ["sleep", "infinity"]
