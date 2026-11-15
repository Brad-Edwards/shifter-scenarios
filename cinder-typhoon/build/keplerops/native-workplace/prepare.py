#!/usr/bin/env python3
"""Prepare private native workplace account and initial realm inputs."""

import argparse
import json
import os
from pathlib import Path
import secrets
import tempfile


def write(path: Path, value: str, mode: int = 0o600) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name + '-')
    try:
        with os.fdopen(descriptor, 'w') as output:
            output.write(value)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def prepare(operator: Path) -> None:
    target = operator / 'native-workplace'
    target.mkdir(mode=0o700, exist_ok=True)
    private = target / 'bootstrap.json'
    values = json.loads(private.read_text()) if private.exists() else {}
    for name in ('identity_db', 'identity_admin', 'kanboard_db', 'kanboard_admin',
                 'support_db', 'support_admin', 'mariadb_root', 'ca', 'enrollment_client'):
        values.setdefault(name, secrets.token_urlsafe(32))
    write(private, json.dumps(values))
    runtime = json.loads((operator / 'range-seed/runtime-credentials.json').read_text())['credentials']
    write(target / 'keycloak.env',
          'KC_DB_PASSWORD=' + values['identity_db'] + '\n'
          'KC_BOOTSTRAP_ADMIN_USERNAME=platform-admin\n'
          'KC_BOOTSTRAP_ADMIN_PASSWORD=' + values['identity_admin'] + '\n')
    write(target / 'identity_db_password', values['identity_db'])
    write(target / 'kanboard_db_password', values['kanboard_db'])
    write(target / 'support_db_password', values['support_db'])
    write(target / 'mariadb_root_password', values['mariadb_root'])
    realm = {
        'realm': 'keplerops', 'enabled': True, 'displayName': 'KeplerOps Staff',
        'registrationAllowed': False, 'resetPasswordAllowed': False,
        'eventsEnabled': True, 'adminEventsEnabled': True,
        'roles': {'realm': [{'name': name} for name in
                            ('developer', 'support', 'release-reviewer', 'certificate-operator')]},
        'groups': [{'name': 'Engineering'}, {'name': 'Customer Support'}, {'name': 'Release Operations'}],
        'users': [{
            'username': 'rowan.ito', 'enabled': True, 'firstName': 'Rowan', 'lastName': 'Ito',
            'email': 'rowan.ito@keplerops.test', 'emailVerified': True,
            'realmRoles': ['developer'], 'groups': ['/Engineering'],
            'credentials': [{'type': 'password', 'value': runtime['developer_token'], 'temporary': False}],
        }],
        'clients': [{
            'clientId': 'fieldlink-enrollment', 'name': 'FieldLink certificate enrollment',
            'enabled': True, 'protocol': 'openid-connect', 'publicClient': False,
            'secret': values['enrollment_client'], 'standardFlowEnabled': True,
            'directAccessGrantsEnabled': False, 'serviceAccountsEnabled': False,
            'redirectUris': ['http://127.0.0.1:10000'],
            'defaultClientScopes': ['web-origins', 'acr', 'profile', 'roles', 'email'],
        }],
    }
    write(target / 'realm.json', json.dumps(realm), 0o644)
    ca = target / 'ca'
    (ca / 'secrets').mkdir(mode=0o700, parents=True, exist_ok=True)
    write(ca / 'secrets/password', values['ca'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--operator-dir', type=Path, required=True)
    arguments = parser.parse_args()
    os.umask(0o077)
    prepare(arguments.operator_dir)
