# Preserve native FieldLink before reset

Use only `cinder-fieldlink-dev` in `prod-mgau4w`, through the guarded development
wrapper. Coordinate an outage and disconnect QA first. Keep ARWC and its OT,
connector, earned handover and destination receipts unchanged. The FieldLink
relay can restart during a FieldLink reset; it must still target the development
peer `10.77.59.11`.

Outbound osTicket email is unconfigured. Cases, correspondence and files use
the native application; no SMTP delivery is qualified. Historical imports use
the native no-alert and no-autoresponse options, but upstream processing can
still report a missing local `sendmail` command.

Become root on the development VM and run from the FieldLink build directory.
The backup stays private on that same VM. It contains passwords, sessions,
private CA inputs and product data. Do not upload it or print its contents.

```bash
set -euo pipefail
umask 077
cd /opt/cinder-typhoon/build/keplerops
[[ $EUID == 0 && $(hostname) == cinder-fieldlink-dev ]]
project=$(curl --fail --silent --show-error --header 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/project/project-id)
[[ $project == prod-mgau4w ]]
export ARWC_CARRIER_ADDRESS=10.77.59.11
compose=(docker compose -f compose.yaml)
backup=/var/backups/cinder-fieldlink-native/$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$backup"
chmod 0700 "$backup"
python3 native-platform/backup-volumes.py >"$backup/volumes"
[[ -s $backup/volumes ]]
while read -r volume; do [[ $volume == cinder-keplerops-* ]]; done <"$backup/volumes"
stateful=(k-dev k-source k-registry k-ci fieldlink-review k-preview k-support k-indexer k-identity fieldlink-keycloak k-cert fieldlink-kanboard fieldlink-support fieldlink-support-db fieldlink-assistant fieldlink-ollama fieldlink-objects fieldlink-k3s fieldlink-postgres runner)
```

Stop state writers before archiving the validated volumes. Keep the existing
immutable model and Kubernetes image caches on disk; the reset does not remove
them. Excluding those reproducible caches avoids a second large local copy.
The inventory includes existing declared volumes and actual container mounts as
well as ownership labels, including a legacy CA volume created without labels.
Inherited K3s runtime and Kanboard plugin/TLS directories also have explicit
named volumes. The inventory refuses anonymous or undeclared product storage.

```bash
"${compose[@]}" stop "${stateful[@]}"
while read -r volume; do
  docker run --rm --pull never --network none --user 0:0 --entrypoint tar \
    --mount "type=volume,source=$volume,target=/volume,readonly" \
    --mount "type=bind,source=$backup,target=/backup" \
    cinder-keplerops/foundation-dns:hand-build -czpf "/backup/$volume.tar.gz" -C /volume .
done <"$backup/volumes"
tar --exclude=.operator/native-platform/model-source \
  --exclude=.operator/native-platform/model-converted \
  --exclude=.operator/native-platform/k3s-images --exclude=.operator/.terraform \
  -czpf "$backup/operator.tar.gz" .operator
(cd "$backup" && sha256sum -- *.tar.gz >SHA256SUMS && sha256sum --check --quiet SHA256SUMS)
chmod 0600 "$backup"/*.tar.gz "$backup/SHA256SUMS"
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 300 "${stateful[@]}"
python3 native-platform/host-routing.py
python3 ../development-ranges/guest/fieldlink-desktop-login.py
```

If a backup command fails, restart those same services and fix the backup before
reset. Keep the private backup path in operator notes. After QA records ordinary
state and confirms the backup window, use the existing guarded reset command:

```bash
bash cinder-typhoon/build/development-ranges/manage.sh reset fieldlink prod-mgau4w
```

Run that wrapper from the repository root on the operator workstation. It binds
the development peer first. Direct `restore-pristine.sh` also checks the exact
VM/project and pins that same peer before starting the relay. It clears mutable
product import markers and the generated S3 backup dump, preserves immutable
model/image caches, and regenerates native credentials against the new K3s CA.
QA then checks fresh native applications and normal starting records. No
challenge campaign, customer delivery or ARWC reset belongs to this check.

Restore the accepted working state afterward, on the same VM with the same
private backup path. Stop writers before replacing volume contents. Preserve
the immutable caches that remained outside the operator archive.

```bash
set -euo pipefail
umask 077
cd /opt/cinder-typhoon/build/keplerops
[[ $EUID == 0 && $(hostname) == cinder-fieldlink-dev ]]
project=$(curl --fail --silent --show-error --header 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/project/project-id)
[[ $project == prod-mgau4w && ${backup-} == /var/backups/cinder-fieldlink-native/* ]]
compose=(docker compose -f compose.yaml)
export ARWC_CARRIER_ADDRESS=10.77.59.11
(cd "$backup" && sha256sum --check --quiet SHA256SUMS)
"${compose[@]}" down
while read -r volume; do
  [[ $volume == cinder-keplerops-* ]]
  docker volume create --label com.docker.compose.project=cinder-keplerops \
    --label "com.docker.compose.volume=${volume#cinder-keplerops-}" "$volume" >/dev/null
  docker run --rm --pull never --network none --user 0:0 --entrypoint sh \
    --mount "type=volume,source=$volume,target=/volume" \
    --mount "type=bind,source=$backup,target=/backup,readonly" \
    cinder-keplerops/foundation-dns:hand-build -ec \
    'find /volume -mindepth 1 -delete; tar -xzpf "$1" -C /volume' restore "/backup/$volume.tar.gz"
done <"$backup/volumes"
cache_dir="$backup/immutable-caches"
[[ ! -e $cache_dir && ! -e $backup/fresh-operator ]]
mkdir -m 0700 "$cache_dir"
for cache in model-source model-converted k3s-images; do
  mv ".operator/native-platform/$cache" "$cache_dir/$cache"
done
mv .operator "$backup/fresh-operator"
tar -xzpf "$backup/operator.tar.gz"
for cache in model-source model-converted k3s-images; do
  mv "$cache_dir/$cache" ".operator/native-platform/$cache"
done
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 300
python3 native-platform/host-routing.py
python3 ../development-ranges/guest/fieldlink-desktop-login.py
```

If extraction fails, keep products stopped. The immutable caches and the fresh
operator directory remain recoverable under the private backup path; correct
the extraction before moving caches back or restarting. The accepted operator
archive replaces active mutable inputs completely, including keys and markers.

QA confirms that ordinary record changes, files, versions, passwords and product
history returned, and that the retained diagnostic job and earned destination
handover still match. Keep the backup until that recovery check passes.
