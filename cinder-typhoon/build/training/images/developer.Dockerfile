FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y git=1:2.39.5-0+deb12u2 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 2000 cinder-developer \
    && useradd --system --uid 2000 --gid cinder-developer --home-dir /nonexistent --shell /usr/sbin/nologin cinder-developer

COPY build/training/runtime/http_support.py /opt/cinder-developer/http_support.py
COPY build/training/runtime/build_repository.py /opt/cinder-developer/build_repository.py
COPY build/training/runtime/developer.py /opt/cinder-developer/developer.py
COPY assets/training/developer/index.md /srv/cinder-developer/public/index.md
COPY assets/training/developer/consumer-contract.md /srv/cinder-developer/public/consumer-contract.md
COPY assets/training/developer/repository-seed.json /var/lib/cinder-developer/repository-seed.json
COPY assets/training/developer/build-BLD-204.log /srv/cinder-developer/public/build/BLD-204.log
COPY assets/training/developer/channel-manifest.json /var/lib/cinder-developer/registry/channel-manifest.json
COPY assets/training/developer/baseline-package.json /var/lib/cinder-developer/registry/packages/1.4.0.json
COPY assets/training/developer/sample-package/package.json /srv/cinder-developer/public/sample-package/package.json
COPY assets/training/developer/sample-package/package-lock.json /srv/cinder-developer/public/sample-package/package-lock.json
COPY assets/training/developer/sample-package/scripts/register-rehearsal.js /srv/cinder-developer/public/sample-package/scripts/register-rehearsal.js
COPY assets/training/developer/sample-package/fixtures/rehearsal-source.json /srv/cinder-developer/public/sample-package/fixtures/rehearsal-source.json
COPY assets/training/developer/service-contract.json /etc/cinder-developer/service-contract.json

RUN mkdir -p /var/lib/cinder-developer/audit /var/lib/cinder-developer/delivery-formatter.git \
      /var/lib/cinder-developer/registry/published /var/lib/cinder-developer/consumer/receipts \
    && chown -R root:cinder-developer /srv/cinder-developer /etc/cinder-developer /var/lib/cinder-developer \
    && chmod -R a-w /srv/cinder-developer /etc/cinder-developer \
    && chmod 0440 /etc/cinder-developer/service-contract.json /var/lib/cinder-developer/repository-seed.json \
      /var/lib/cinder-developer/registry/channel-manifest.json /var/lib/cinder-developer/registry/packages/1.4.0.json \
    && chown cinder-developer:cinder-developer /var/lib/cinder-developer/audit \
      /var/lib/cinder-developer/delivery-formatter.git /var/lib/cinder-developer/registry/published \
      /var/lib/cinder-developer/consumer/receipts \
    && chmod 0700 /var/lib/cinder-developer/audit /var/lib/cinder-developer/registry/published \
      /var/lib/cinder-developer/consumer/receipts \
    && chmod 0750 /var/lib/cinder-developer/delivery-formatter.git

USER cinder-developer
WORKDIR /opt/cinder-developer
EXPOSE 8080 8081 8082 8083 8084
CMD ["python3", "/opt/cinder-developer/developer.py"]
