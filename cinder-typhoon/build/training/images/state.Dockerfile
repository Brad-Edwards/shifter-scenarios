FROM python:3.12.11-slim-bookworm

RUN groupadd --system cinder-state \
    && useradd --system --gid cinder-state --home-dir /nonexistent --shell /usr/sbin/nologin cinder-state

COPY build/training/runtime/http_support.py /opt/cinder-state/http_support.py
COPY build/training/runtime/state.py /opt/cinder-state/state.py
COPY assets/training/state/index.md /srv/cinder-state/public/index.md
COPY assets/training/state/field-guide.md /srv/cinder-state/public/field-guide.md
COPY assets/training/state/captures/status.json /srv/cinder-state/public/captures/status.json
COPY assets/training/state/captures/volume.json /srv/cinder-state/public/captures/volume.json
COPY assets/training/state/replay/observations.csv /srv/cinder-state/public/replay/observations.csv
COPY assets/training/state/replay/report.json /srv/cinder-state/public/replay/report.json
COPY assets/training/state/replay/requests.json /srv/cinder-state/public/replay/requests.json
COPY assets/training/state/practice-initial.json /var/lib/cinder-state/initial.json
COPY assets/training/state/service-contract.json /etc/cinder-state/service-contract.json

RUN mkdir -p /var/lib/cinder-state/live \
    && chown -R root:cinder-state /srv/cinder-state /etc/cinder-state /var/lib/cinder-state \
    && chmod -R a-w /srv/cinder-state /etc/cinder-state \
    && chmod 0440 /etc/cinder-state/service-contract.json /var/lib/cinder-state/initial.json \
    && chown cinder-state:cinder-state /var/lib/cinder-state/live \
    && chmod 0700 /var/lib/cinder-state/live

USER cinder-state
WORKDIR /opt/cinder-state
EXPOSE 8080
CMD ["python3", "/opt/cinder-state/state.py"]
