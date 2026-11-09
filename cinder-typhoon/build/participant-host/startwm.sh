#!/bin/bash
set -eu

unset DBUS_SESSION_BUS_ADDRESS
unset XDG_RUNTIME_DIR

if [ -r /etc/profile ]; then
  . /etc/profile
fi

xset s off 2>/dev/null || true
xset s noblank 2>/dev/null || true
xset -dpms 2>/dev/null || true

exec startxfce4
