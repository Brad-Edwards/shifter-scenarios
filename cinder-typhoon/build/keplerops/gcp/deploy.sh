#!/usr/bin/env bash
set -euo pipefail

echo 'This legacy golden deployment entrypoint is retired.' >&2
echo 'Use build/development-ranges/manage.sh for the isolated development VM and docs/design/fieldlink-native-platform.md for native setup.' >&2
exit 1
