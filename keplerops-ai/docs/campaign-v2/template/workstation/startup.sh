#!/usr/bin/env sh
set -eu

readonly password_file=/run/keplerops/participant-password

test "$(id -u)" -eq 0
test -s "${password_file}"

participant_password="$(cat "${password_file}")"
printf 'kasm-user:%s\n' "${participant_password}" | chpasswd
export VNC_PW="${participant_password}"
unset participant_password

exec /usr/local/bin/keplerops-kasm-startup "$@"
