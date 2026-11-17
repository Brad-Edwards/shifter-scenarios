FROM python:3.14.10-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1
RUN --network=none --mount=type=bind,from=desktop-assets,target=/offline,readonly \
    cd /offline && sha256sum --check SHA256SUMS >/dev/null \
    && cp /offline/debs/*.deb /var/cache/apt/archives/ \
    && apt-get install --no-download --no-install-recommends -y /offline/debs/*.deb \
    && rm -f /etc/xrdp/cert.pem /etc/xrdp/key.pem /etc/ssl/private/ssl-cert-snakeoil.key /etc/ssl/certs/ssl-cert-snakeoil.pem \
    && rm -f /etc/machine-id /var/lib/dbus/machine-id \
    && python -m venv /opt/opcua-client \
    && /opt/opcua-client/bin/pip install --no-index --require-hashes --find-links=/offline/wheels -r /offline/requirements.lock \
    && install -d /opt/openplc-editor \
    && cp /offline/editor.AppImage /tmp/editor.AppImage \
    && chmod 0755 /tmp/editor.AppImage \
    && cd /opt/openplc-editor && /tmp/editor.AppImage --appimage-extract >/dev/null \
    && rm /tmp/editor.AppImage \
    && install -d /usr/share/arwc-ot \
    && cp /offline/requirements.lock /usr/share/arwc-ot/requirements.lock \
    && dpkg-query -W -f='${Package}\t${Version}\n' > /usr/share/arwc-ot/debian-packages.tsv
RUN groupadd --gid 2500 fieldlink \
    && useradd --uid 2500 --gid 2500 --create-home --shell /bin/bash fieldlink \
    && passwd --lock fieldlink && passwd --lock root \
    && usermod --append --groups ssl-cert xrdp \
    && rm -f /etc/xrdp/cert.pem /etc/xrdp/key.pem /etc/ssl/private/ssl-cert-snakeoil.key /etc/ssl/certs/ssl-cert-snakeoil.pem \
    && sed -i 's/^AllowRootLogin=.*/AllowRootLogin=false/' /etc/xrdp/sesman.ini \
    && sed -i 's/^security_layer=.*/security_layer=tls/; s/^ssl_protocols=.*/ssl_protocols=TLSv1.2/' /etc/xrdp/xrdp.ini \
    && install -d -o fieldlink -g fieldlink /home/fieldlink/Desktop /home/fieldlink/CairnReach \
    && chmod -R a+rX /opt/openplc-editor/squashfs-root \
    && runuser -u fieldlink -- test -x /opt/openplc-editor/squashfs-root/AppRun \
    && runuser -u fieldlink -- test -r /opt/openplc-editor/squashfs-root/resources/app.asar \
    && runuser -u fieldlink -- python -c "import os,pathlib; root=pathlib.Path('/opt/openplc-editor/squashfs-root'); assert all(os.access(p,os.R_OK | (os.X_OK if p.is_dir() else 0)) for p in root.rglob('*'))"
COPY entrypoint.sh /usr/local/sbin/arwc-engineering-entrypoint
COPY startwm.sh /etc/xrdp/startwm.sh
COPY launch-editor.sh /usr/local/bin/openplc-editor
COPY shifter-participant-readiness /usr/local/libexec/shifter-participant-readiness
COPY participant-readiness.json /usr/local/share/shifter/participant-readiness.json
COPY desktop/ /home/fieldlink/Desktop/
COPY desktop/ /usr/share/applications/
COPY docs/ /usr/share/arwc-ot/
COPY challenges/ /usr/share/arwc-ot/challenges/
COPY firefox-policies.json /usr/lib/firefox-esr/distribution/policies.json
RUN chmod 0755 /usr/local/sbin/arwc-engineering-entrypoint /etc/xrdp/startwm.sh /usr/local/bin/openplc-editor /usr/local/libexec/shifter-participant-readiness \
    && install -d -o fieldlink -g fieldlink /home/fieldlink/CairnReach/Briefs \
    && ln -s /usr/share/arwc-ot/challenges/W17 /home/fieldlink/CairnReach/Briefs/W17 \
    && ln -s /usr/share/arwc-ot/challenges/W18 /home/fieldlink/CairnReach/Briefs/W18 \
    && ln -s /usr/share/arwc-ot/challenges/W21 /home/fieldlink/CairnReach/Briefs/W21 \
    && ln -s /usr/share/arwc-ot/challenges/W25 /home/fieldlink/CairnReach/Briefs/W25 \
    && ln -s /usr/share/arwc-ot/challenges/W29 /home/fieldlink/CairnReach/Briefs/W29 \
    && ln -s /usr/share/arwc-ot/challenges/W30 /home/fieldlink/CairnReach/Briefs/W30 \
    && ln -s /usr/share/arwc-ot/challenges/W33 /home/fieldlink/CairnReach/Briefs/W33 \
    && chmod 0755 /usr/share/arwc-ot/challenges/W33/run-schedule.py \
    && chown -R fieldlink:fieldlink /home/fieldlink \
    && chmod 0755 /home/fieldlink/Desktop/*.desktop
EXPOSE 3389
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD python -c "import socket; socket.create_connection(('127.0.0.1',3389),2).close()"
ENTRYPOINT ["/usr/local/sbin/arwc-engineering-entrypoint"]
