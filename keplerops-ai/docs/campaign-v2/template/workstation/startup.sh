#!/usr/bin/env sh
set -eu

readonly password_file=/run/keplerops/participant-password
readonly default_xfce=/home/kasm-default-profile/.config/xfce4
readonly participant_xfce=/home/kasm-user/.config/xfce4
readonly labgrid_ssh_source=/run/keplerops/labgrid-ssh
readonly labgrid_ssh_target=/home/kasm-user/.ssh/labgrid

test "$(id -u)" -eq 0
test -s "${password_file}"

participant_password="$(cat "${password_file}")"
printf 'kasm-user:%s\n' "${participant_password}" | chpasswd
export VNC_PW="${participant_password}"
unset participant_password

install -d -m 0755 "${participant_xfce}/panel"
cp -a "${default_xfce}/panel/." "${participant_xfce}/panel/"
install -d -m 0755 "${participant_xfce}/xfconf/xfce-perchannel-xml"
cp "${default_xfce}/xfconf/xfce-perchannel-xml/xfce4-panel.xml" \
  "${participant_xfce}/xfconf/xfce-perchannel-xml/xfce4-panel.xml"
install -m 0644 /usr/local/share/keplerops/chromium.desktop \
  "${participant_xfce}/panel/launcher-6/17389582522.desktop"
chown -R kasm-user:root "${participant_xfce}"

if [ -s "${labgrid_ssh_source}/id_ed25519" ]; then
  install -d -m 0700 -o kasm-user -g root "${labgrid_ssh_target}"
  install -m 0600 -o kasm-user -g root \
    "${labgrid_ssh_source}/id_ed25519" "${labgrid_ssh_target}/id_ed25519"
  if [ -s "${labgrid_ssh_source}/known_hosts" ]; then
    install -m 0644 -o kasm-user -g root \
      "${labgrid_ssh_source}/known_hosts" "${labgrid_ssh_target}/known_hosts"
  fi
fi

exec /usr/local/bin/keplerops-kasm-startup "$@"
