#!/bin/sh
set -eu

scan_host="${SCAN_TARGET_HOST:-127.0.0.1}"
curl --fail --silent --show-error "http://${scan_host}:18080/healthz" | grep -qx 'ok'
curl --fail --silent --show-error "http://${scan_host}:18081/healthz" | grep -qx 'ok'
curl --fail --silent --show-error "http://${scan_host}:18080/" | grep -q 'Range Documentation Service'
curl --fail --silent --show-error "http://${scan_host}:18081/" | grep -q '"service": "range-status"'
