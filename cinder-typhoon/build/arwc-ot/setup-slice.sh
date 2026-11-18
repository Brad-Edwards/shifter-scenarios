#!/bin/bash
# First-boot setup for the OT compatibility slice.
# Runs on the dedicated development VM (cinder-arwc-ot-compat-363) or any
# cinder-* range VM that carries the OT slice at /opt/arwc-ot-compat/slice.
set -euo pipefail
_host=$(hostname)
[[ $_host == cinder-arwc-ot-compat-363 || $_host == cinder-* ]] || {
  echo "Run on a Cinder OT VM (got: $_host)." >&2; exit 1;
}
[[ $EUID != 0 ]] || { echo 'Run as the IAP operator, not root.' >&2; exit 1; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
[[ $PWD == /opt/arwc-ot-compat/slice ]] || {
  echo 'Use the persistent /opt/arwc-ot-compat/slice directory.' >&2; exit 1;
}
root=/opt/arwc-ot-compat
editor="$root/upstream/squashfs-root"
project="$root/work/arwc-compat"
# Sync PLC build files from the IT tree so the slice always uses the
# version that was baked into the image, not an older snapshot.
_it_tree="$root/it/cinder-typhoon/build/arwc-ot"
for _f in plc.Dockerfile plc-entrypoint.sh plugins.conf; do
  [[ -f "$_it_tree/$_f" ]] && sudo cp "$_it_tree/$_f" "$PWD/$_f"
done
unset _it_tree _f
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
# Seed the PLC program, save runtime artefacts (binary, cert, opcua.json) to the
# plc-state volume, and copy the server cert to .operator/ for Telegraf.
# seed_plc.py uses a committed plc-program.zip if present (no editor needed);
# otherwise it falls back to the host build directory from a previous editor run.
python3 seed_plc.py > /tmp/arwc-ot-seed.log 2>&1
# On the dedicated development VM the editor is also available; keep upload_fixture.py
# for iterative development where the program source has changed.
if [[ $_host == cinder-arwc-ot-compat-363 ]] && [[ -x "$editor/AppRun" ]]; then
  python3 upload_fixture.py > /tmp/arwc-ot-upload.log 2>&1
fi
sudo docker compose run --rm -T tools python /slice/prepare_services.py
# Hash the bootstrap passwords once with the broker's own maintained utility.
if ! sudo head -c 12 .operator/mosquitto/passwords | rg -q '^operator:\$7\$'; then
  sudo docker run --rm --entrypoint mosquitto_passwd --mount "type=bind,src=$PWD/.operator/mosquitto,dst=/mosquitto/config" eclipse-mosquitto:2.0.22@sha256:81a6193ae693942a3231cd3ac52875b02b7e3a19da671b2fb4b55cc874c5b279 -U /mosquitto/config/passwords
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
