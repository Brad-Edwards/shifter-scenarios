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
        # Publish the connector versions so the highest stable release is published
        # last. The registry sets the package-level readme from the last publish, so
        # the "latest" readme must come from the stable release, not a prerelease.
        def source_order(path: Path) -> tuple[int, tuple[int, ...]]:
            value = json.loads((path / 'package.json').read_text())['version']
            is_stable = 0 if '-' in value else 1
            return (is_stable, tuple(int(part) for part in value.split('-')[0].split('.')))
        sources = sorted(
            (p for p in (SEEDS / 'fieldlink-connector').iterdir() if p.is_dir()),
            key=source_order,
        )
        sources.append(SEEDS / 'support-rehearsal-1.3.1.tgz')
        connector = '@keplerops/fieldlink-connector'
        stable_releases: list[str] = []
        prereleases: list[str] = []
        for source in sources:
            if source.is_dir():
                metadata = json.loads((source / 'package.json').read_text())
                name, version = metadata['name'], metadata['version']
            else:
                name, version = '@keplerops/support-rehearsal', '1.3.1'
            # The legacy v2 line keeps its own tag. A prerelease publishes to a
            # non-latest channel so it never takes the "latest" dist-tag. Only a
            # stable release line can be "latest".
            if version == '6.9.8':
                tag = 'legacy'
            elif '-' in version:
                tag = 'next'
            else:
                tag = 'latest'
            if name == connector and version != '6.9.8':
                (prereleases if '-' in version else stable_releases).append(version)
            existing = subprocess.run(
                ['npm', 'view', f'{name}@{version}', 'version', '--json'],
                env=environment, capture_output=True, text=True, timeout=30,
            )
            if existing.returncode == 0 and json.loads(existing.stdout) == version:
                continue
            subprocess.run(
                ['npm', 'publish', str(source), '--access', 'restricted', '--tag', tag],
                env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                check=True, timeout=30,
            )
        # Pin the connector dist-tags explicitly, so the result does not depend on
        # publish order or on versions that were already present. "latest" is the
        # highest stable release; prereleases stay on the "next" channel.
        def release_key(value: str) -> tuple[int, ...]:
            return tuple(int(part) for part in value.split('-')[0].split('.'))
        for channel, candidates in (('latest', stable_releases), ('next', prereleases)):
            if candidates:
                top = max(candidates, key=release_key)
                subprocess.run(
                    ['npm', 'dist-tag', 'add', f'{connector}@{top}', channel],
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
