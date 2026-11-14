"""Initialize native registry users and publish retained package sources with npm."""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

from credentials import credential


ROOT = Path('/var/lib/verdaccio')
SEEDS = Path('/opt/fieldlink-native-packages')
REGISTRY = 'https://packages.keplerops.test/'


def accounts() -> None:
    secret = ROOT / '.seed-admin-password'
    if not secret.exists():
        descriptor = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as output:
            output.write(secrets.token_urlsafe(32))
    passwd = ROOT / 'htpasswd'
    if passwd.exists() and passwd.stat().st_size:
        return
    users = {
        'rowan.ito': credential('developer_token'),
        'fieldlink-importer-publisher': credential('registry_publisher_token'),
        'svc-fieldlink-ci': credential('ci_registry_reader'),
        'svc-package-admin': secret.read_text(),
    }
    lines = []
    for username, password in users.items():
        result = subprocess.run(
            ['htpasswd', '-niB', username], input=password + '\n',
            text=True, capture_output=True, check=True,
        )
        lines.append(result.stdout.strip())
    temporary = ROOT / '.htpasswd-new'
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        output.write('\n'.join(lines) + '\n')
    temporary.replace(passwd)


def packages() -> None:
    marker = ROOT / '.native-packages-seeded'
    if marker.exists():
        return
    authorization = base64.b64encode(
        ('svc-package-admin:' + (ROOT / '.seed-admin-password').read_text()).encode()
    ).decode()
    with tempfile.TemporaryDirectory(prefix='registry-seed-') as temporary:
        work = Path(temporary)
        config = work / 'npmrc'
        config.write_text(
            'registry=' + REGISTRY + '\n'
            '//packages.keplerops.test/:_auth=' + authorization + '\n'
            'cafile=/run/fieldkest-tls/ca.crt\n'
            'audit=false\nfund=false\n'
        )
        config.chmod(0o600)
        environment = os.environ | {
            'NPM_CONFIG_USERCONFIG': str(config), 'NPM_CONFIG_CACHE': str(work / 'cache'),
        }
        sources = list(sorted((SEEDS / 'fieldlink-connector').iterdir()))
        sources.append(SEEDS / 'support-rehearsal-1.3.1.tgz')
        for source in sources:
            if source.is_dir():
                metadata = json.loads((source / 'package.json').read_text())
                name, version = metadata['name'], metadata['version']
            else:
                name, version = '@keplerops/support-rehearsal', '1.3.1'
            existing = subprocess.run(
                ['npm', 'view', f'{name}@{version}', 'version', '--json'],
                env=environment, capture_output=True, text=True, timeout=30,
            )
            if existing.returncode == 0 and json.loads(existing.stdout) == version:
                continue
            subprocess.run(
                ['npm', 'publish', str(source), '--access', 'restricted', '--tag',
                 'legacy' if version == '6.9.8' else 'latest'],
                env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                check=True, timeout=30,
            )
        subprocess.run(
            ['npm', 'deprecate', '@keplerops/fieldlink-connector@6.9.8',
             'The legacy v2 interface is retained for maintained installations.'],
            env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            check=True, timeout=30,
        )
    marker.touch(mode=0o600)
    print('Native Verdaccio packages published')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['accounts', 'packages'])
    args = parser.parse_args()
    accounts() if args.action == 'accounts' else packages()
