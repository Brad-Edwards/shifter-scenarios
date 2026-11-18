#!/usr/bin/env bash
# Extract the service keytabs that k-identity generated into the operator dir.
#
# k-identity (the KDC) writes HTTP/staff and HTTP/identity keytabs into its own
# state volume. k-staff-spnego and k-identity-spnego mount the keytabs from
# $operator/native-platform/{staff,identity}.keytab. Without this step those
# bind-mount sources do not exist, so docker creates empty directories and
# SPNEGO verification fails (K20.1/K20.2). Run this after k-identity is up and
# before the SPNEGO services start, so the keytabs match the current KDC keys.
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
operator=${KEPLEROPS_OPERATOR_DIR:-"$ROOT/.operator"}
for name in staff identity; do
  target="$operator/native-platform/$name.keytab"
  # Remove an empty directory a previous bind mount may have created.
  rm -rf -- "$target"
  docker compose -f compose.yaml cp \
    "k-identity:/var/lib/keplerops-identity/keytabs/$name.keytab" "$target"
  chmod 0444 "$target"
done
echo 'Kerberos service keytabs extracted to the operator directory.'
