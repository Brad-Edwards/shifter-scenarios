"""Prepare private native Jenkins account and HTTPS material for this range."""

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess


def prepare(operator: Path) -> None:
    directory = operator / 'native-ci'
    directory.mkdir(mode=0o700, exist_ok=True)
    users = directory / 'users.json'
    if not users.exists():
        runtime = json.loads((operator / 'range-seed/runtime-credentials.json').read_text())
        with users.open('x') as output:
            json.dump({
                'developer_password': runtime['credentials']['developer_token'],
                'administrator_password': secrets.token_urlsafe(32),
            }, output)
        users.chmod(0o600)
    password = directory / 'keystore-password'
    if not password.exists():
        password.write_text(secrets.token_hex(24))
        password.chmod(0o600)
    subprocess.run([
        'openssl', 'pkcs12', '-export', '-name', 'ci.keplerops.test',
        '-in', str(operator / 'tls/server.crt'), '-inkey', str(operator / 'tls/server.key'),
        '-certfile', str(operator / 'tls/ca.crt'), '-out', str(directory / 'server.p12'),
        '-passout', 'file:' + str(password),
    ], check=True)
    (directory / 'server.p12').chmod(0o600)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--operator-dir', type=Path, required=True)
    arguments = parser.parse_args()
    os.umask(0o077)
    prepare(arguments.operator_dir)
