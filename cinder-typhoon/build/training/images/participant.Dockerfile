FROM kalilinux/kali-rolling@sha256:30399bd65187e06525008dd13eecc2b3439d26a82b2c6b0ba32dee72bd843117

RUN sed -i 's/^Suites: .*/Suites: kali-last-snapshot/' /etc/apt/sources.list.d/kali.sources \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
      ca-certificates=20260601 \
      curl=8.21.0-2 \
      git=1:2.53.0-1 \
      jq=1.8.2-1 \
      python3=3.14.7-3 \
      dbus-x11 \
      kali-desktop-xfce \
      xorgxrdp \
      xrdp \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 2000 cinder \
    && useradd --uid 2000 --gid cinder --create-home --shell /bin/bash cinder \
    && usermod -aG ssl-cert xrdp \
    && sed -i 's/^security_layer=.*/security_layer=tls/; s/^ssl_protocols=.*/ssl_protocols=TLSv1.2/' /etc/xrdp/xrdp.ini \
    && grep -qx 'security_layer=tls' /etc/xrdp/xrdp.ini \
    && grep -qx 'ssl_protocols=TLSv1.2' /etc/xrdp/xrdp.ini

COPY --chown=cinder:cinder assets/training/workstation/TRAINING.md /home/cinder/TRAINING.md
COPY build/participant-host/startwm.sh /etc/xrdp/startwm.sh
COPY build/participant-host/startwm.sh /home/cinder/.xsession
COPY build/participant-host/shifter-participant-readiness /usr/local/libexec/shifter-participant-readiness
COPY build/training/participant-readiness.json /usr/local/share/shifter/participant-readiness.json
COPY build/training/runtime/participant-entrypoint.sh /usr/local/bin/cinder-participant-entrypoint
RUN chmod 0444 /home/cinder/TRAINING.md /usr/local/share/shifter/participant-readiness.json \
    && chmod 0755 /etc/xrdp/startwm.sh /home/cinder/.xsession \
      /usr/local/libexec/shifter-participant-readiness /usr/local/bin/cinder-participant-entrypoint \
    && touch /var/log/xrdp.log /var/log/xrdp-sesman.log \
    && chown xrdp:xrdp /var/log/xrdp.log /var/log/xrdp-sesman.log \
    && chown -R cinder:cinder /home/cinder

WORKDIR /home/cinder
EXPOSE 3389
ENTRYPOINT ["/usr/local/bin/cinder-participant-entrypoint"]
