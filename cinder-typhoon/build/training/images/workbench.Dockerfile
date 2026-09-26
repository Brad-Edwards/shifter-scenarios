FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y git=1:2.39.5-0+deb12u2 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system cinder-workbench \
    && useradd --system --gid cinder-workbench --home-dir /nonexistent --shell /usr/sbin/nologin cinder-workbench

COPY build/training/runtime/http_support.py /opt/cinder-workbench/http_support.py
COPY build/training/runtime/build_repository.py /opt/cinder-workbench/build_repository.py
COPY build/training/runtime/workbench.py /opt/cinder-workbench/workbench.py
COPY assets/training/workbench/index.md /srv/cinder-workbench/public/index.md
COPY assets/training/workbench/workspace/handover-current.md /srv/cinder-workbench/public/workspace/handover-current.md
COPY assets/training/workbench/workspace/delivery-tracker.csv /srv/cinder-workbench/public/workspace/delivery-tracker.csv
COPY assets/training/workbench/workspace/repository-seed.json /var/lib/cinder-workbench/repository-seed.json
COPY assets/training/workbench/dispatch/index.md /srv/cinder-workbench/dispatch/index.md
COPY assets/training/workbench/dispatch/notice-DL-204.md /srv/cinder-workbench/dispatch/notice-DL-204.md
COPY assets/training/workbench/dispatch/site.webmanifest /srv/cinder-workbench/dispatch/site.webmanifest
COPY assets/training/workbench/dispatch/current.json /srv/cinder-workbench/dispatch/content/current.json
COPY assets/training/workbench/dispatch/retired.json /srv/cinder-workbench/dispatch/content/retired.json
COPY assets/training/workbench/dispatch/amendment-AMEND-204.json /srv/cinder-workbench/dispatch/retired/amendment-AMEND-204.json
COPY assets/training/workbench/courier/profile.json /srv/cinder-workbench/public/retired-client/profile.json
COPY assets/training/workbench/courier/request-history.txt /srv/cinder-workbench/public/retired-client/request-history.txt
COPY assets/training/workbench/courier/manifest-DL-204.json /var/lib/cinder-workbench/courier/manifest-DL-204.json
COPY assets/training/workbench/diagnostics/public/DL-204.json /var/lib/cinder-workbench/diagnostics/public/DL-204.json
COPY assets/training/workbench/diagnostics/internal/DL-204.json /var/lib/cinder-workbench/diagnostics/internal/DL-204.json
COPY assets/training/workbench/service-contract.json /etc/cinder-workbench/service-contract.json

RUN mkdir -p /var/lib/cinder-workbench/audit /var/lib/cinder-workbench/handover.git \
    && chown -R root:cinder-workbench /srv/cinder-workbench /etc/cinder-workbench /var/lib/cinder-workbench \
    && chmod -R a-w /srv/cinder-workbench /etc/cinder-workbench \
    && chmod 0440 /etc/cinder-workbench/service-contract.json /var/lib/cinder-workbench/repository-seed.json \
    && chown cinder-workbench:cinder-workbench /var/lib/cinder-workbench/audit /var/lib/cinder-workbench/handover.git \
    && chmod 0700 /var/lib/cinder-workbench/audit \
    && chmod 0750 /var/lib/cinder-workbench/handover.git

USER cinder-workbench
WORKDIR /opt/cinder-workbench
EXPOSE 8080 8081 8082 8083
CMD ["python3", "/opt/cinder-workbench/workbench.py"]
