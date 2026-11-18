FROM node:22.19.0-bookworm-slim AS node-tools

FROM smallstep/step-ca:0.28.4@sha256:0f88382ac5af5c6b7bbba0c6e8fcefef52aee6f22ea364df8e02a09ffd0d22f3 AS step-tools

FROM debian:bookworm-slim AS indexer-reproducer

RUN apt-get update \
    && apt-get install --no-install-recommends -y gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY build/keplerops/runtime/bundle_indexer.c /src/bundle_indexer.c
RUN gcc -std=c11 -O0 -fPIE -pie -Wl,-z,relro,-z,now,--build-id=none -D_FORTIFY_SOURCE=2 \
    -o /fieldkest-bundle-indexer /src/bundle_indexer.c \
    && strip --strip-all /fieldkest-bundle-indexer

FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl dbus-x11 firefox-esr git iproute2 jq krb5-user openssh-server poppler-utils procps sqlite3 unzip util-linux xdg-utils xorgxrdp xrdp xfce4 xfce4-terminal zip \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir cryptography==50.0.2 \
    && groupadd --gid 2000 rowan \
    && useradd --uid 2000 --gid rowan --create-home --shell /bin/bash rowan \
    # Keep the account eligible for public-key SSH while leaving password
    # authentication impossible both here and in sshd_config.
    && usermod --password x rowan \
    && usermod -aG ssl-cert xrdp \
    && sed -i 's/^security_layer=.*/security_layer=tls/; s/^ssl_protocols=.*/ssl_protocols=TLSv1.2/' /etc/xrdp/xrdp.ini \
    && grep -qx 'security_layer=tls' /etc/xrdp/xrdp.ini \
    && grep -qx 'ssl_protocols=TLSv1.2' /etc/xrdp/xrdp.ini \
    && groupadd --system fieldkest-workbench \
    && useradd --system --gid fieldkest-workbench --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-workbench

RUN apt-get update \
    && apt-get install --no-install-recommends -y awscli gpg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl --fail --silent --show-error https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && gpg --show-keys --with-colons /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc | grep -q B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8 \
    && echo 'deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main' > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install --no-install-recommends -y postgresql-client-16 \
    && curl --fail --silent --show-error --location https://dl.k8s.io/release/v1.37.2/bin/linux/amd64/kubectl -o /usr/local/bin/kubectl \
    && echo 'c04487523e7aa7d1493f7808174c899db93d7a9cf57531420cd76b9bd415f8f4  /usr/local/bin/kubectl' | sha256sum --check \
    && chmod 0755 /usr/local/bin/kubectl \
    && apt-get clean

COPY --from=node-tools /usr/local/bin/node /usr/local/bin/node
COPY --from=node-tools /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=step-tools /usr/local/bin/step /usr/local/bin/step
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
ENV NODE_EXTRA_CA_CERTS=/home/rowan/.local/share/keplerops/ca.crt

COPY build/keplerops/runtime/http_support.py /opt/fieldkest-workbench/http_support.py
COPY build/keplerops/runtime/workbench.py /opt/fieldkest-workbench/workbench.py
COPY build/keplerops/runtime/k-dev-entrypoint.sh /usr/local/bin/fieldkest-k-dev-entrypoint
COPY build/keplerops/config/sshd_config /etc/ssh/sshd_config
COPY build/keplerops/config/firefox-policies.json /usr/lib/firefox-esr/distribution/policies.json
COPY build/keplerops/config/krb5.conf /etc/krb5.conf
COPY build/keplerops/native-platform/platform-access.md /usr/local/share/fieldlink/platform-access.md
COPY assets/keplerops/native-workplace/identity-access.md /usr/local/share/fieldlink/identity-access.md
COPY build/participant-host/startwm.sh /etc/xrdp/startwm.sh
COPY build/participant-host/startwm.sh /home/rowan/.xsession
COPY build/participant-host/shifter-participant-readiness /usr/local/libexec/shifter-participant-readiness
COPY build/keplerops/participant-readiness.json /usr/local/share/shifter/participant-readiness.json
COPY assets/keplerops/opening/k-dev-home.tar /tmp/k-dev-home.tar
COPY assets/keplerops/opening/k-dev-workbench.tar /tmp/k-dev-workbench.tar
COPY assets/keplerops/registry/k-dev-registry.tar /var/lib/fieldkest-workbench/seeds/k-dev-registry.tar
COPY assets/keplerops/policy-compiler/k-dev-policy-compiler-home.tar /var/lib/fieldkest-workbench/seeds/k-dev-policy-compiler-home.tar
COPY assets/keplerops/connector-archive/k-dev-connector-archive-home.tar /var/lib/fieldkest-workbench/seeds/k-dev-connector-archive-home.tar
COPY assets/keplerops/release-lineage/k-dev-release-lineage-home.tar /var/lib/fieldkest-workbench/seeds/k-dev-release-lineage-home.tar
COPY --from=indexer-reproducer --chown=2000:2000 --chmod=0550 \
    /fieldkest-bundle-indexer /home/rowan/work/reproducers/fieldkest-bundle-indexer

RUN tar -xf /tmp/k-dev-home.tar -C /home/rowan \
    && tar -xf /var/lib/fieldkest-workbench/seeds/k-dev-registry.tar -C /home/rowan \
    && tar -xf /var/lib/fieldkest-workbench/seeds/k-dev-policy-compiler-home.tar -C /home/rowan \
    && tar -xf /var/lib/fieldkest-workbench/seeds/k-dev-connector-archive-home.tar -C /home/rowan \
    && tar -xf /var/lib/fieldkest-workbench/seeds/k-dev-release-lineage-home.tar -C /home/rowan \
    && rm -f /home/rowan/.config/git/credentials /home/rowan/.npmrc /home/rowan/.config/chromium/Default/Cookies \
    && mkdir -p /home/rowan/.local/share/keplerops \
    && touch /home/rowan/.local/share/keplerops/registry-foundation-2026-09-18 \
    && touch /home/rowan/.local/share/keplerops/policy-compiler-2026-09-18 \
    && touch /home/rowan/.local/share/keplerops/connector-archive-2026-09-18 \
    && touch /home/rowan/.local/share/keplerops/release-lineage-2026-09-18 \
    && tar -xf /tmp/k-dev-workbench.tar -C /opt/fieldkest-workbench \
    && rm /tmp/k-dev-home.tar /tmp/k-dev-workbench.tar \
    && mkdir -p /opt/fieldkest-empty-git-template \
    && git config --system init.templateDir /opt/fieldkest-empty-git-template \
    && git clone /opt/fieldkest-workbench/seed/fieldlink-connector.bundle /home/rowan/work/fieldlink-connector \
    && git -C /home/rowan/work/fieldlink-connector remote set-url origin https://source.keplerops.test/fieldkest/fieldlink-connector.git \
    && mkdir -p /home/rowan/.ssh /home/rowan/.local/share/keplerops /home/rowan/results /run/sshd /var/lib/fieldkest-workbench/audit /var/lib/fieldkest-workbench/results \
    && ln -s /opt/fieldkest-workbench /opt/keplerops-workbench \
    && ssh-keygen -A \
    && chown -R rowan:rowan /home/rowan \
    && chown -R fieldkest-workbench:fieldkest-workbench /opt/fieldkest-workbench \
    && chown -R fieldkest-workbench:fieldkest-workbench /var/lib/fieldkest-workbench \
    && chmod 0750 /home/rowan/work /opt/fieldkest-workbench \
    && chmod 0700 /var/lib/fieldkest-workbench \
    && chmod 0700 /home/rowan /home/rowan/.ssh /home/rowan/.config /home/rowan/.config/chromium /home/rowan/.config/chromium/Default /home/rowan/results \
    && chmod 0600 /home/rowan/.gitconfig /home/rowan/.config/chromium/Default/* \
    && chmod 0755 /etc/xrdp/startwm.sh /home/rowan/.xsession /usr/local/libexec/shifter-participant-readiness \
    && chmod 0444 /usr/local/share/shifter/participant-readiness.json \
    && chmod 0700 /usr/local/bin/fieldkest-k-dev-entrypoint \
    && touch /var/log/xrdp.log /var/log/xrdp-sesman.log \
    && chown xrdp:xrdp /var/log/xrdp.log /var/log/xrdp-sesman.log \
    && chown -R rowan:rowan /home/rowan

EXPOSE 22 3389
ENTRYPOINT ["/usr/local/bin/fieldkest-k-dev-entrypoint"]
