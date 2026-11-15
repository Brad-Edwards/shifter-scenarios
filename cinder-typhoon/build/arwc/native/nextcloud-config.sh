#!/bin/sh
set -eu
# Runs as www-data through the upstream before-starting hook, after the stock
# installer has populated config.php and its environment configuration files.
cp /run/arwc-nextcloud.config.php /var/www/html/config/arwc.config.php
chmod 0644 /var/www/html/config/arwc.config.php
