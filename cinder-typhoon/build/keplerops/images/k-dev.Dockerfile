FROM python:3.12.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl git iproute2 jq krb5-user openssh-server procps sqlite3 unzip util-linux zip \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir cryptography==46.0.5 \
    && groupadd --gid 2000 rowan \
    && useradd --uid 2000 --gid rowan --create-home --shell /bin/bash rowan \
    # Keep the account eligible for public-key SSH while leaving password
    # authentication impossible both here and in sshd_config.
    && usermod --password x rowan \
    && groupadd --system fieldkest-workbench \
    && useradd --system --gid fieldkest-workbench --home-dir /nonexistent --shell /usr/sbin/nologin fieldkest-workbench

COPY build/keplerops/runtime/http_support.py /opt/fieldkest-workbench/http_support.py
COPY build/keplerops/runtime/workbench.py /opt/fieldkest-workbench/workbench.py
COPY build/keplerops/runtime/k-dev-entrypoint.sh /usr/local/bin/fieldkest-k-dev-entrypoint
COPY build/keplerops/config/sshd_config /etc/ssh/sshd_config
COPY build/keplerops/config/krb5.conf /etc/krb5.conf
COPY assets/keplerops/opening/k-dev-home.tar /tmp/k-dev-home.tar
COPY assets/keplerops/opening/k-dev-workbench.tar /tmp/k-dev-workbench.tar
COPY assets/keplerops/registry/k-dev-registry.tar /opt/fieldkest-seeds/k-dev-registry.tar
COPY assets/keplerops/policy-compiler/k-dev-k11-home.tar /opt/fieldkest-seeds/k-dev-k11-home.tar
COPY assets/keplerops/connector-archive/k-dev-k28-home.tar /opt/fieldkest-seeds/k-dev-k28-home.tar
COPY assets/keplerops/release-lineage/k-dev-k29-home.tar /opt/fieldkest-seeds/k-dev-k29-home.tar

RUN tar -xf /tmp/k-dev-home.tar -C /home/rowan \
    && tar -xf /opt/fieldkest-seeds/k-dev-registry.tar -C /home/rowan \
    && tar -xf /opt/fieldkest-seeds/k-dev-k11-home.tar -C /home/rowan \
    && tar -xf /opt/fieldkest-seeds/k-dev-k28-home.tar -C /home/rowan \
    && tar -xf /opt/fieldkest-seeds/k-dev-k29-home.tar -C /home/rowan \
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
    && mkdir -p /home/rowan/.ssh /home/rowan/.local/share/keplerops /home/rowan/results /run/sshd /var/lib/fieldkest-workbench/audit \
    && ln -s /opt/fieldkest-workbench /opt/keplerops-workbench \
    && ssh-keygen -A \
    && chown -R rowan:rowan /home/rowan \
    && chown -R fieldkest-workbench:fieldkest-workbench /opt/fieldkest-workbench \
    && chown -R fieldkest-workbench:fieldkest-workbench /var/lib/fieldkest-workbench \
    && chmod 0750 /home/rowan/work /opt/fieldkest-workbench \
    && chmod 0700 /var/lib/fieldkest-workbench \
    && chmod 0700 /home/rowan /home/rowan/.ssh /home/rowan/.config /home/rowan/.config/chromium /home/rowan/.config/chromium/Default /home/rowan/results \
    && chmod 0600 /home/rowan/.gitconfig /home/rowan/.config/git/credentials /home/rowan/.config/chromium/Default/* \
    && chmod 0755 /usr/local/bin/fieldkest-k-dev-entrypoint

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/fieldkest-k-dev-entrypoint"]
