ARG ODOO_BASE_IMAGE=odoo:18.0@sha256:66fae420378996f4c7e633b3fd47bfef0909170d75db897e3935e8ad1162db1a
FROM ${ODOO_BASE_IMAGE}

USER root

RUN python3 -m pip install \
      --break-system-packages \
      --disable-pip-version-check \
      --no-cache-dir \
      ecdsa==0.19.2 \
      pyasn1==0.6.4 \
      rsa==4.9.1 \
      python-jose==3.5.0

COPY --chown=odoo:odoo addons/auth_oidc /mnt/extra-addons/auth_oidc
COPY OCA_SERVER_AUTH_REVISION /usr/share/doc/keplerops-odoo/OCA_SERVER_AUTH_REVISION
COPY OCA-LICENSE /usr/share/doc/keplerops-odoo/OCA-LICENSE

LABEL org.opencontainers.image.title="KeplerOps Odoo Community 18 with OIDC" \
      org.opencontainers.image.base.name="odoo:18.0@sha256:66fae420378996f4c7e633b3fd47bfef0909170d75db897e3935e8ad1162db1a" \
      org.opencontainers.image.vendor="KeplerOps AI Systems" \
      org.opencontainers.image.licenses="LGPL-3.0-only AND AGPL-3.0-or-later" \
      io.keplerops.oca.server-auth.revision="6d57b614fadf77bdbe4d02cce61c671e33061ef4" \
      io.keplerops.oca.auth-oidc.version="18.0.1.1.0"

USER odoo
