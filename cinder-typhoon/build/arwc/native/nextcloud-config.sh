#!/bin/sh
set -eu
# Runs as www-data through the upstream before-starting hook, after the stock
# installer has populated config.php and its environment configuration files.
# Replace the managed fragment even if a restored former bind placeholder is
# owned by root. The product-owned directory controls this rename.
temporary=$(mktemp /var/www/html/config/.arwc-config.XXXXXX)
trap 'rm -f "$temporary"' EXIT HUP INT TERM
cp /run/arwc-nextcloud.config.php "$temporary"
chmod 0644 "$temporary"
mv -f "$temporary" /var/www/html/config/arwc.config.php
trap - EXIT HUP INT TERM
