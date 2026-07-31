#!/bin/sh
set -eu

public_web_url="${PUBLIC_WEB_URL:-http://127.0.0.1:8080}"
curl --fail --silent --show-error "${public_web_url}/healthz" | grep -qx 'ok'
curl --fail --silent --show-error "${public_web_url}/" | grep -q 'KeplerOps AI Systems'
