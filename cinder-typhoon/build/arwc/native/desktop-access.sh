#!/usr/bin/env bash
set -euo pipefail
[[ $(hostname) == cinder-arwc-dev || $(hostname) == cinder-arwc-golden ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
desktop=cinder-arwc-ot-engineering
docker cp .operator/ca/certs/root_ca.crt "$desktop:/usr/local/share/ca-certificates/arwc-native-it.crt"
docker exec --user 0 "$desktop" chmod 0644 /usr/local/share/ca-certificates/arwc-native-it.crt
docker cp ../.operator/tls/ca.crt "$desktop:/usr/local/share/ca-certificates/arwc-customer-integration.crt"
docker exec --user 0 "$desktop" chmod 0644 /usr/local/share/ca-certificates/arwc-customer-integration.crt
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
for root in ('/usr/local/share/ca-certificates/arwc-native-it.crt',
             '/usr/local/share/ca-certificates/arwc-customer-integration.crt'):
    if root not in install:
        install.append(root)
path.write_text(json.dumps(document))
PY

# Deliver only the existing scoped HTTPS reader's normal client configuration.
if ! docker exec "$desktop" test -e /home/fieldlink/CairnReach/Connections/operating-history.json; then
ot_operator=${ARWC_OT_OPERATOR_DIR:-/opt/arwc-ot-compat/slice/.operator}
docker cp "$ot_operator/integration-bridge/operating-reader.json" "$desktop:/home/fieldlink/CairnReach/Connections/operating-history.json"
docker exec --user 0 -i "$desktop" python3 - <<'PYCLIENT'
import json
from pathlib import Path
path = Path('/home/fieldlink/CairnReach/Connections/operating-history.json')
client = json.loads(path.read_text())
client['endpoint'] = 'https://read-data.arwc.test/api/operating-history'
path.write_text(json.dumps(client) + '\n')
path.chmod(0o600)
PYCLIENT
docker exec --user 0 "$desktop" chown 2500:2500 /home/fieldlink/CairnReach/Connections/operating-history.json
fi
