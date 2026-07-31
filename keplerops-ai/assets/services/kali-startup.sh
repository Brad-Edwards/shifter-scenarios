#!/usr/bin/env sh
set -eu

export VNC_PW="$(cat /run/keplerops/participant-password)"
if [ -x /usr/local/bin/keplerops-file-recorder ]; then
  /usr/local/bin/keplerops-file-recorder >/tmp/keplerops-file-recorder.log 2>&1 &
fi
if [ -x /usr/local/bin/keplerops-browser-recorder ]; then
  /usr/local/bin/keplerops-browser-recorder >/tmp/keplerops-browser-recorder.log 2>&1 &
fi

exec /dockerstartup/kasm_default_profile.sh \
  /dockerstartup/vnc_startup.sh \
  /dockerstartup/kasm_startup.sh \
  --wait
