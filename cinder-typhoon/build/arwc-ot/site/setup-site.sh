#!/bin/bash
# Manual development setup; the golden and participant ranges are not targets.
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || exit 1
[[ $EUID != 0 ]] || { echo 'Run as the IAP operator.' >&2; exit 1; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $PWD == /opt/arwc-ot-compat/slice ]] || {
  echo 'Use the persistent /opt/arwc-ot-compat/slice directory.' >&2; exit 1;
}
umask 077
mkdir -p .operator/site-io
editor=/opt/arwc-ot-compat/upstream/squashfs-root
project=/opt/arwc-ot-compat/work/arwc-site
compose=(sudo docker compose -f compose.yaml -f site/compose.yaml)
if [[ ! -f "$project/project.json" ]]; then
  env APPDIR="$editor" "$editor/AppRun" --cli create arwc-site --path /opt/arwc-ot-compat/work --language fbd --time 'T#100ms'
fi
python3 site/generate_project.py "$project"
"${compose[@]}" config -q
"${compose[@]}" stop dispatcher
"${compose[@]}" build plc io fuxa > .operator/site-image-build.log 2>&1
"${compose[@]}" up -d plc io postgres fuxa
for attempt in {1..60}; do
  if "${compose[@]}" exec -T postgres pg_isready -U historian -d historian > /dev/null; then
    break
  fi
  [[ $attempt != 60 ]] || exit 1
  sleep 1
done
python3 upload_fixture.py "$project" > .operator/site-upload.log 2>&1
for attempt in {1..60}; do
  if sudo docker exec arwc-ot-compat-plc-1 test -s /workdir/core/src/drivers/plugins/python/opcua/certs/server_cert.pem; then
    break
  fi
  [[ $attempt != 60 ]] || { echo 'Native OPC UA certificate did not become ready.' >&2; exit 1; }
  sleep 1
done
sudo docker cp arwc-ot-compat-plc-1:/workdir/core/src/drivers/plugins/python/opcua/certs/server_cert.pem .operator/server-cert.pem
"${compose[@]}" run --rm -T tools python /slice/prepare_services.py
if ! sudo head -c 12 .operator/mosquitto/passwords | rg -q '^operator:\$7\$'; then
  sudo docker run --rm --entrypoint mosquitto_passwd --mount "type=bind,src=$PWD/.operator/mosquitto,dst=/mosquitto/config" eclipse-mosquitto:2.0.22@sha256:81a6193ae693942a3231cd3ac52875b02b7e3a19da671b2fb4b55cc874c5b279 -U /mosquitto/config/passwords
fi
"${compose[@]}" up -d --force-recreate telegraf mosquitto grafana
for attempt in {1..45}; do
  if "${compose[@]}" exec -T postgres psql -U historian -d historian -Atc "SELECT to_regclass('remote_enabled') IS NOT NULL" | rg -q '^t$'; then
    break
  fi
  [[ $attempt != 45 ]] || exit 1
  sleep 1
done
"${compose[@]}" run --rm -T tools python /slice/finalize_history.py
"${compose[@]}" run --rm -T tools python /slice/configure_fuxa.py
"${compose[@]}" restart fuxa
echo 'The site controller is running, disarmed. Site participant surfaces are separate component work.'
