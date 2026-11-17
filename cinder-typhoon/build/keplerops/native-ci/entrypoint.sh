#!/bin/sh
set -eu

ip route replace 10.77.50.0/24 via 10.77.51.254
ip route replace 10.77.52.0/24 via 10.77.51.254
ip route replace 10.77.53.0/24 via 10.77.51.254
ip route replace 10.77.60.0/24 via 10.77.51.254

install -m 0444 /run/fieldlink-ci/ca.crt /tmp/fieldlink-ca.crt
install -m 0600 -o jenkins -g jenkins /run/fieldlink-ci/server.p12 /tmp/fieldlink-ci.p12
install -m 0600 -o jenkins -g jenkins /run/fieldlink-ci/users.json /tmp/fieldlink-ci-users.json
password=$(cat /run/fieldlink-ci/keystore-password)
export GIT_SSL_CAINFO=/tmp/fieldlink-ca.crt
export HOME="$JENKINS_HOME"
export XDG_CACHE_HOME="$JENKINS_HOME/.cache"
export JAVA_OPTS="-Djenkins.install.runSetupWizard=false -Xms256m -Xmx1024m"
exec setpriv --reuid=jenkins --regid=jenkins --init-groups \
  /usr/bin/tini -- /usr/local/bin/jenkins.sh \
    --httpPort=-1 --httpsPort=443 \
    --httpsKeyStore=/tmp/fieldlink-ci.p12 --httpsKeyStorePassword="$password"
