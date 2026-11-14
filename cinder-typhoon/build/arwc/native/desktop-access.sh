#!/usr/bin/env bash
set -euo pipefail
[[ $(hostname) == cinder-arwc-dev ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
desktop=cinder-arwc-ot-engineering
docker cp .operator/ca/certs/root_ca.crt "$desktop:/usr/local/share/ca-certificates/arwc-native-it.crt"
docker exec --user 0 "$desktop" chmod 0644 /usr/local/share/ca-certificates/arwc-native-it.crt
docker exec --user 0 "$desktop" update-ca-certificates >/dev/null
docker exec --user 0 "$desktop" sh -ec 'printf "nameserver 172.29.63.26\noptions timeout:2 attempts:2\n" > /etc/resolv.conf'
docker exec --user 0 -i "$desktop" python3 - <<'PY'
import json
from pathlib import Path
hosts = Path('/etc/hosts')
text = hosts.read_text()
for address, name in (
    ('172.29.63.20', 'plc'), ('172.29.63.21', 'fuxa'),
    ('172.29.63.22', 'postgres'), ('172.29.63.23', 'mosquitto'),
    ('172.29.63.25', 'grafana'),
):
    if not any(name in line.split()[1:] for line in text.splitlines() if not line.startswith('#')):
        text += f'\n{address} {name}\n'
hosts.write_text(text)
path = Path('/usr/lib/firefox-esr/distribution/policies.json')
document = json.loads(path.read_text())
certificates = document['policies'].setdefault('Certificates', {})
install = certificates.setdefault('Install', [])
root = '/usr/local/share/ca-certificates/arwc-native-it.crt'
if root not in install:
    install.append(root)
path.write_text(json.dumps(document))
PY
