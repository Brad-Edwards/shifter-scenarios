"""Import retained FieldLink repositories through native Gitea administration."""

from __future__ import annotations

import base64
import configparser
import io
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from credentials import credential


ROOT = Path('/var/lib/gitea')
CONFIG = ROOT / 'data/app.ini'
BASE = 'https://source.keplerops.test'
CONTEXT = ssl.create_default_context(cafile='/run/fieldkest-tls/ca.crt')
REPOSITORIES = {
    'fieldlink-connector': 'FieldLink customer connector and delivery notes',
    'policy-compiler': 'Retained policy compiler and migration examples',
    'connector-archive': 'Supported connector archive and maintenance records',
    'release-signer-history': 'Release signing history and rollover records',
}


def api(method: str, path: str, password: str, value: object | None = None) -> object:
    """Call the range-local Gitea administration endpoint."""
    authorization = base64.b64encode(f'fieldlink-bootstrap:{password}'.encode()).decode()
    request = Request(
        BASE + '/api/v1' + path,
        data=None if value is None else json.dumps(value).encode(),
        headers={'Authorization': 'Basic ' + authorization, 'Content-Type': 'application/json'},
        method=method,
    )
    with urlopen(request, context=CONTEXT, timeout=30) as response:
        payload = response.read()
    return json.loads(payload) if payload else None


def exists(path: str, password: str) -> bool:
    try:
        api('GET', path, password)
    except HTTPError as error:
        if error.code == 404:
            return False
        raise
    return True


def main() -> None:
    password_path = ROOT / 'data/.bootstrap-password'
    if not password_path.exists():
        descriptor = os.open(password_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(secrets.token_urlsafe(32))
    password = password_path.read_text()
    users = subprocess.check_output(
        ['/usr/local/bin/gitea', 'admin', 'user', 'list', '--config', str(CONFIG)], text=True,
    )
    if 'fieldlink-bootstrap' not in users:
        subprocess.run(
            ['/usr/local/bin/gitea', 'admin', 'user', 'create', '--config', str(CONFIG),
             '--username', 'fieldlink-bootstrap', '--password', password,
             '--email', 'source-admin@fieldkest.test', '--admin', '--must-change-password=false'],
            check=True, stdout=subprocess.DEVNULL,
        )
    if not exists('/users/rowan.ito', password):
        api('POST', '/admin/users', password, {
            'username': 'rowan.ito', 'password': credential('developer_token'),
            'email': 'rowan.ito@fieldkest.test', 'must_change_password': False,
            'login_name': 'rowan.ito', 'source_id': 0,
        })
    if not exists('/orgs/fieldkest', password):
        api('POST', '/orgs', password, {'username': 'fieldkest', 'visibility': 'private'})
    for name, description in REPOSITORIES.items():
        path = f'/repos/fieldkest/{name}'
        marker = ROOT / f'data/.seeded-{name}'
        if marker.exists():
            continue
        if not exists(path, password):
            api('POST', '/orgs/fieldkest/repos', password, {
                'name': name, 'description': description, 'private': True,
                'auto_init': False, 'default_branch': 'main',
            })
        authorization = base64.b64encode(f'fieldlink-bootstrap:{password}'.encode()).decode()
        environment = os.environ | {
            'GIT_CONFIG_COUNT': '2',
            'GIT_CONFIG_KEY_0': 'http.extraHeader',
            'GIT_CONFIG_VALUE_0': 'Authorization: Basic ' + authorization,
            'GIT_CONFIG_KEY_1': 'http.sslCAInfo',
            'GIT_CONFIG_VALUE_1': '/run/fieldkest-tls/ca.crt',
        }
        with tempfile.TemporaryDirectory(prefix='gitea-seed-') as temporary:
            subprocess.run(
                ['git', 'clone', '--bare', str(ROOT / f'seeds/{name}.bundle'), temporary],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ['git', '-C', temporary, 'push', '--mirror', BASE + f'/fieldkest/{name}.git'],
                check=True, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        api('PUT', path + '/collaborators/rowan.ito', password, {'permission': 'read'})
        marker.touch(mode=0o600)
    handover = json.loads((ROOT / 'handovers/HND-FLK-2026-09.json').read_text())
    marker = ROOT / 'data/.handover-seeded'
    if not marker.exists():
        api('POST', '/repos/fieldkest/fieldlink-connector/issues', password, {
            'title': 'Connector support handover HND-FLK-2026-09',
            'body': f"Release {handover['release']} · revision {handover['revision']}\n\n"
                    + f"Owner: {handover['owner']}\n\n"
                    + '\n'.join('- ' + note for note in handover['notes']),
        })
        marker.touch(mode=0o600)
    print('Native Gitea repositories and handover ready')


def configure(template: Path = Path('/etc/gitea/app.ini')) -> None:
    """Keep generated product secrets stable while applying tracked settings."""
    secret_file = ROOT / 'data/.native-secrets.json'
    if not secret_file.exists():
        descriptor = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as handle:
            json.dump({name: secrets.token_hex(32) for name in ('secret', 'internal', 'jwt')}, handle)
    values = json.loads(secret_file.read_text())
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config.read_string('[DEFAULT]\n' + template.read_text())
    config['security']['SECRET_KEY'] = values['secret']
    config['security']['INTERNAL_TOKEN'] = values['internal']
    config['oauth2']['JWT_SECRET'] = values['jwt']
    output = io.StringIO()
    config.write(output)
    CONFIG.write_text(output.getvalue().removeprefix('[DEFAULT]\n'))
    CONFIG.chmod(0o600)


if __name__ == '__main__':
    if sys.argv[1:] == ['--configure']:
        configure()
    else:
        main()
