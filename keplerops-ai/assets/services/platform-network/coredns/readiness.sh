#!/bin/sh
set -eu

dns_host="${COREDNS_HOST:-127.0.0.1}"
health_port="${COREDNS_HEALTH_PORT:-8080}"
ready_port="${COREDNS_READY_PORT:-8181}"
dns_port="${COREDNS_DNS_PORT:-53}"
curl --fail --silent --show-error "http://${dns_host}:${health_port}/health" | grep -qx 'OK'
curl --fail --silent --show-error "http://${dns_host}:${ready_port}/ready" | grep -qx 'OK'
dig +short +tcp "@${dns_host}" -p "${dns_port}" research-index-01.keplerops.lab A | grep -Eq '^[0-9]+(\.[0-9]+){3}$'
dig +short "@${dns_host}" -p "${dns_port}" public-sites-01.keplerops.lab A | grep -Eq '^[0-9]+(\.[0-9]+){3}$'
