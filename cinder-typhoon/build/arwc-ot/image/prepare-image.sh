#!/bin/bash
# Destructive preparation is restricted to a disposable private bake clone.
set -euo pipefail
[[ $EUID == 0 ]] || exit 1
bake_name=$(curl -fsS -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/instance/name)
[[ $bake_name == cinder-arwc-bake-* ]] || {
  echo 'Refusing image preparation outside a temporary ARWC bake VM.' >&2
  exit 1
}
root=/opt/cinder-typhoon/build/arwc-ot
test -s "$root/image/runtime-inventory.json"
cd "$root"
python3 - <<'PY'
import importlib.util
import pathlib
p = pathlib.Path('image/first_boot.py').resolve()
s = importlib.util.spec_from_file_location('arwc_image', p)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
m.verify_images()
PY

# The clone has no participant session to preserve. Remove every mutable volume.
mapfile -t containers < <(docker ps -aq)
if ((${#containers[@]})); then
  docker rm -f "${containers[@]}" >/dev/null
fi
docker volume prune --all --force >/dev/null
docker network prune --force >/dev/null
docker image prune --force >/dev/null

# Keep only the committed production tree and qualified software images.
rm -rf -- /opt/arwc-ot-compat
find /opt/cinder-typhoon -type d -name .operator -prune -exec rm -rf -- {} +
find /opt/cinder-typhoon -type f -name .env -delete
find /home -mindepth 1 -maxdepth 1 -type d ! -name atomik -exec rm -rf -- {} +
if find /home -mindepth 1 -maxdepth 1 -type d -print -quit | grep -q .; then
  echo "An unhandled operator home remains; refusing image preparation." >&2
  exit 1
fi
rm -rf -- /root/.config /root/.cache /root/.local /root/.ssh /root/.docker
rm -f -- /root/.bash_history /root/.python_history
find /tmp /var/tmp -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +

install -d -m 0755 /usr/local/libexec
install -m 0755 /opt/cinder-typhoon/build/gcp-images/guest/cinder-arwc-ot-first-boot \
  /usr/local/libexec/cinder-arwc-ot-first-boot
printf '%s\n' arwc.private-ot-image/v1 >/etc/cinder-arwc-ot-image
chmod 0644 /etc/cinder-arwc-ot-image
bash /opt/cinder-typhoon/build/gcp-images/guest/prepare-image.sh arwc
test -z "$(docker volume ls -q)"
test ! -e /opt/arwc-ot-compat
sync
