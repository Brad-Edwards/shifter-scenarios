# Preserve native IT state before reset

Use only `cinder-arwc-dev`. Coordinate a native IT outage with QA first. Keep the
OT project, engineering desktop, connector and its earned handover running.
Do not reset the VM or restore the old OT image for this check.

Use the existing private development access and become root on that VM. From
`/opt/arwc-ot-compat/it/cinder-typhoon/build/arwc/native`, define:

```bash
set -euo pipefail
umask 077
[[ $(hostname) == cinder-arwc-dev && $EUID == 0 ]]
[[ $PWD == /opt/arwc-ot-compat/it/cinder-typhoon/build/arwc/native ]]
compose=(docker compose --env-file images.env -f compose.yaml -f corporate.compose.yaml -f dmz.compose.yaml)
backup=/var/backups/cinder-arwc-native/$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$backup"
chmod 0700 "$backup"
docker volume ls --filter label=com.docker.compose.project=cinder-arwc-native -q > "$backup/volumes"
[[ -s $backup/volumes ]]
while read -r volume; do [[ $volume == cinder-arwc-native_* ]]; done < "$backup/volumes"
```

Stop only native IT before copying database and file volumes. This makes the
backup consistent across the selected products. Keep the backup private on this
VM; it contains credentials, application sessions and private CA material.

```bash
"${compose[@]}" stop
for volume in $(cat "$backup/volumes"); do
  docker run --rm --pull never --network none --user 0:0 --entrypoint tar \
    --mount "type=volume,src=$volume,dst=/volume,readonly" \
    --mount "type=bind,src=$backup,dst=/backup" \
    cinder-arwc/native-dns:404 -czpf "/backup/$volume.tar.gz" -C /volume .
done
tar -czpf "$backup/operator.tar.gz" .operator
(cd "$backup" && sha256sum -- *.tar.gz > SHA256SUMS)
(cd "$backup" && sha256sum --check --quiet SHA256SUMS)
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 420
```

If copying fails, restart native IT and resolve the backup failure before any
reset. Retain the backup path in the private operator notes. Record the current
ordinary records, user changes, file versions, reports and repository history
through QA. Do not print credentials into test reports.

Only after the backup is verified and the reset window is released, run the
existing scoped `manage.sh reset cinder-arwc-native`. QA checks stock application
login, normal records, read-only data, documents, history, Git and the supplier
portal. No challenge actions or OT operation is part of this check.

Restore the preserved working state after that check. Keep the same private
`backup` path and `compose` array. Do not start products while their volumes are
being restored. These commands affect only the validated native IT volumes:

```bash
(cd "$backup" && sha256sum --check --quiet SHA256SUMS)
"${compose[@]}" down
while read -r volume; do
  [[ $volume == cinder-arwc-native_* ]]
  docker volume create \
    --label com.docker.compose.project=cinder-arwc-native \
    --label "com.docker.compose.volume=${volume#cinder-arwc-native_}" "$volume" >/dev/null
  docker run --rm --pull never --network none --user 0:0 --entrypoint sh \
    --mount "type=volume,src=$volume,dst=/volume" \
    --mount "type=bind,src=$backup,dst=/backup,readonly" \
    cinder-arwc/native-dns:404 -ec \
    'find /volume -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +; tar -xzpf "$1" -C /volume' \
    restore "/backup/$volume.tar.gz"
done < "$backup/volumes"
[[ $PWD == /opt/arwc-ot-compat/it/cinder-typhoon/build/arwc/native ]]
rm -rf -- .operator
tar -xzpf "$backup/operator.tar.gz"
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 420
```

QA confirms the preserved ordinary changes, replacement password and product
history are back. Compare the OT, connector and desktop container identities
before and after the entire window. Their identities and earned handover must
remain unchanged. Keep the backup until that recovery check passes.
