#!/bin/bash
# Manual development setup on the dedicated VM. No cloud credentials required.
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || {
  echo 'Run on cinder-arwc-ot-compat-363.' >&2; exit 1;
}
[[ $EUID != 0 ]] || { echo 'Run as the IAP operator, not root.' >&2; exit 1; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
root=/opt/arwc-ot-compat
editor="$root/upstream/squashfs-root"
project="$root/work/arwc-compat"
if [[ ! -x "$editor/AppRun" ]]; then
  sudo install -d -o "$(id -u)" -g "$(id -g)" "$root/work"
  (cd "$root/work" && "$root/upstream/OpenPLC.Editor-4.3.4.AppImage" --appimage-extract > /tmp/arwc-ot-editor-extract.log)
  editor="$root/work/squashfs-root"
  sudo mv -- "$editor" "$root/upstream/squashfs-root"
  editor="$root/upstream/squashfs-root"
fi
if [[ ! -f "$project/project.json" ]]; then
  sudo install -d -o "$(id -u)" -g "$(id -g)" "$root/work"
  env APPDIR="$editor" "$editor/AppRun" --cli create arwc-compat --path "$root/work" --time 'T#100ms'
fi
python3 configure_fixture.py "$project"
sudo docker compose build plc io fuxa > /tmp/arwc-ot-build.log 2>&1
sudo docker compose up -d plc io postgres fuxa
for attempt in {1..60}; do
  if sudo docker compose exec -T postgres pg_isready -U historian -d historian > /dev/null; then
    break
  fi
  [[ $attempt != 60 ]] || exit 1
  sleep 1
done
python3 upload_fixture.py > /tmp/arwc-ot-upload.log 2>&1
sudo docker cp arwc-ot-compat-plc-1:/workdir/core/src/drivers/plugins/python/opcua/certs/server_cert.pem .operator/server-cert.pem
sudo docker compose run --rm -T tools python /slice/prepare_services.py
# Hash the bootstrap passwords once with the broker's own maintained utility.
if ! sudo head -c 12 .operator/mosquitto/passwords | rg -q '^operator:\$7\$'; then
  sudo docker compose run --rm -T --no-deps -v "$PWD/.operator/mosquitto:/mosquitto/config" --entrypoint mosquitto_passwd mosquitto -U /mosquitto/config/passwords
fi
sudo docker compose up -d --force-recreate telegraf mosquitto grafana
for attempt in {1..45}; do
  if sudo docker compose exec -T postgres psql -U historian -d historian -Atc "SELECT to_regclass('remote_enabled') IS NOT NULL" | rg -q '^t$'; then
    break
  fi
  [[ $attempt != 45 ]] || exit 1
  sleep 1
done
sudo docker compose run --rm -T tools python /slice/finalize_history.py
sudo docker compose run --rm -T tools python /slice/configure_fuxa.py
sudo docker compose restart fuxa
sudo docker compose up -d --force-recreate dispatcher
echo 'Compatibility slice configured. Run the focused qualification commands in README.md.'
