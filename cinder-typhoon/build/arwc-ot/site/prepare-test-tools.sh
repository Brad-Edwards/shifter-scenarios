#!/bin/bash
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || {
  echo 'Run on the dedicated compatibility VM.' >&2; exit 1;
}
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $PWD == /opt/arwc-ot-compat/slice ]] || {
  echo 'Use the persistent /opt/arwc-ot-compat/slice directory.' >&2; exit 1;
}
umask 077
mkdir -p .operator/compiler
if ! command -v g++ > /dev/null; then
  sudo apt-get update
  sudo apt-get install -y g++
fi
cd .operator/compiler
if [[ ! -x strucpp/strucpp ]]; then
  curl -fsSL --retry 3 https://github.com/Autonomy-Logic/STruCpp/releases/download/v0.7.0/strucpp-linux-x64.tar.gz -o strucpp-linux-x64.tar.gz
  printf '%s  %s\n' eb060d416b18d339db35715ebb06dcbecd70e0c177a4dcbfa57c2fa1c7fb05d5 strucpp-linux-x64.tar.gz | sha256sum --check
  tar -xzf strucpp-linux-x64.tar.gz
fi
./strucpp/strucpp --version
