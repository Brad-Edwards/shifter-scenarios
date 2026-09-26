FROM python:3.12.11-slim-bookworm

RUN groupadd --system cinder-accounts \
    && useradd --system --gid cinder-accounts --home-dir /nonexistent --shell /usr/sbin/nologin cinder-accounts

COPY build/training/runtime/http_support.py /opt/cinder-accounts/http_support.py
COPY build/training/runtime/accounts.py /opt/cinder-accounts/accounts.py
COPY assets/training/accounts/index.md /srv/cinder-accounts/public/index.md
COPY assets/training/accounts/candidates.md /srv/cinder-accounts/public/candidates.md
COPY assets/training/accounts/directory/index.json /srv/cinder-accounts/public/directory/index.json
COPY assets/training/accounts/directory/app.js /srv/cinder-accounts/public/directory/app.js
COPY assets/training/accounts/directory/assignment-STF-204.json /var/lib/cinder-accounts/directory/assignment-STF-204.json
COPY assets/training/accounts/realm.json /var/lib/cinder-accounts/realm.json
COPY assets/training/accounts/handover-rhea-moss.md /var/lib/cinder-accounts/handovers/rhea.moss.md
COPY assets/training/accounts/assignment-ASG-204.json /var/lib/cinder-accounts/assignments/ASG-204.json
COPY assets/training/accounts/assignment-ASG-317.json /var/lib/cinder-accounts/assignments/ASG-317.json
COPY assets/training/accounts/service-contract.json /etc/cinder-accounts/service-contract.json

RUN mkdir -p /var/lib/cinder-accounts/audit /var/lib/cinder-accounts/sessions \
    && chown -R root:cinder-accounts /srv/cinder-accounts /etc/cinder-accounts /var/lib/cinder-accounts \
    && chmod -R a-w /srv/cinder-accounts /etc/cinder-accounts \
    && chmod 0440 /etc/cinder-accounts/service-contract.json /var/lib/cinder-accounts/realm.json \
      /var/lib/cinder-accounts/directory/assignment-STF-204.json \
      /var/lib/cinder-accounts/handovers/rhea.moss.md \
      /var/lib/cinder-accounts/assignments/ASG-204.json \
      /var/lib/cinder-accounts/assignments/ASG-317.json \
    && chown cinder-accounts:cinder-accounts /var/lib/cinder-accounts/audit /var/lib/cinder-accounts/sessions \
    && chmod 0700 /var/lib/cinder-accounts/audit /var/lib/cinder-accounts/sessions

USER cinder-accounts
WORKDIR /opt/cinder-accounts
EXPOSE 8080
CMD ["python3", "/opt/cinder-accounts/accounts.py"]
