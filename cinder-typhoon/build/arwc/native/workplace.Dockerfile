FROM python:3.14.10-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install --no-install-recommends -y openssh-server krb5-user ca-certificates curl git \
    && apt-get clean \
    && rm -f /etc/ssh/ssh_host_ed25519_key /etc/ssh/ssh_host_ed25519_key.pub \
      /etc/ssh/ssh_host_rsa_key /etc/ssh/ssh_host_rsa_key.pub \
      /etc/ssh/ssh_host_ecdsa_key /etc/ssh/ssh_host_ecdsa_key.pub \
    && groupadd --gid 2600 morgan \
    && useradd --uid 2600 --gid morgan --create-home --shell /bin/bash morgan \
    && usermod --password x morgan \
    && passwd --lock root
COPY workplace-sshd.conf /etc/ssh/sshd_config
COPY krb5.conf /etc/krb5.conf
COPY workplace-entrypoint.sh /usr/local/bin/arwc-workplace
RUN chmod 0755 /usr/local/bin/arwc-workplace
ENV SSL_CERT_FILE=/tmp/arwc-public-ca.pem CURL_CA_BUNDLE=/tmp/arwc-public-ca.pem GIT_SSL_CAINFO=/tmp/arwc-public-ca.pem
ENTRYPOINT ["/usr/local/bin/arwc-workplace"]
