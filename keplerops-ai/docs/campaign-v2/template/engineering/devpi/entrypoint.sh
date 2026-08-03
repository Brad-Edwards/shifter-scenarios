#!/usr/bin/env sh
set -eu

server_dir=${DEVPI_SERVERDIR:-/data}

if [ ! -f "$server_dir/.serverversion" ]; then
  devpi-init --serverdir "$server_dir"
fi

exec devpi-server \
  --host 0.0.0.0 \
  --port 3141 \
  --role standalone \
  --serverdir "$server_dir"
