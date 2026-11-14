FROM jenkins/jenkins:2.580.2-jdk21@sha256:74401de6a6f92e1afe1b02d1c8e3d0c33f263bfb5275dd8813f9150355f2367b

USER root
RUN apt-get update \
    && apt-get install --no-install-recommends -y iproute2 openssl python3 util-linux \
    && rm -rf /var/lib/apt/lists/*
USER jenkins
RUN jenkins-plugin-cli --plugins git:5.11.0 matrix-auth:3.3

COPY build/keplerops/native-ci/init.groovy /usr/share/jenkins/ref/init.groovy.d/10-fieldlink.groovy
COPY --chmod=0755 build/keplerops/native-ci/entrypoint.sh /usr/local/bin/fieldlink-jenkins-entrypoint

USER root
EXPOSE 443
ENTRYPOINT ["/usr/local/bin/fieldlink-jenkins-entrypoint"]
