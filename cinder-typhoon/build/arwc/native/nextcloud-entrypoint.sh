#!/bin/sh
set -eu
# Docker creates this directory for the nested read-only configuration mount.
# The stock installer must be able to create its own private config.php here.
chown www-data:www-data /var/www/html/config
exec /entrypoint.sh "$@"
