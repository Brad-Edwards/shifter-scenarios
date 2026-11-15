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
                 'support_db', 'support_admin', 'mariadb_root', 'ca', 'enrollment_client',
                 'kerberos_master', 'kerberos_evan', 'staff_maya', 'staff_talia'):
        values.setdefault(name, secrets.token_urlsafe(32))
    write(private, json.dumps(values))
    runtime = json.loads((operator / 'range-seed/runtime-credentials.json').read_text())['credentials']
    write(target / 'kerberos.json', json.dumps({
        'master': values['kerberos_master'],
        'users': {'rowan.ito': runtime['developer_token'], 'evan.calderoux': values['kerberos_evan']},
    }), 0o444)
    write(target / 'keycloak.env',
          'KC_DB_PASSWORD=' + values['identity_db'] + '\n'
          'KC_BOOTSTRAP_ADMIN_USERNAME=platform-admin\n'
          'KC_BOOTSTRAP_ADMIN_PASSWORD=' + values['identity_admin'] + '\n')
    write(target / 'kanboard.env',
          'DATABASE_URL=postgres://fieldlink_staff:' + values['kanboard_db']
          + '@fieldlink-postgres:5432/fieldlink_staff\n')
    write(target / 'kanboard-bootstrap.json', json.dumps({
        'admin_password': values['kanboard_admin'],
        'users': [
            {'username': 'rowan.ito', 'name': 'Rowan Ito', 'password': runtime['developer_token'],
             'role': 'app-user', 'is_active': 1},
            {'username': 'maya.ranscombe', 'name': 'Maya Ranscombe', 'password': values['staff_maya'],
             'role': 'app-user', 'is_active': 1},
            {'username': 'talia.mornac', 'name': 'Talia Mornac', 'password': values['staff_talia'],
             'role': 'app-user', 'is_active': 1},
            {'username': 'evan.calderoux', 'name': 'Evan Calderoux', 'password': values['kerberos_evan'],
             'role': 'app-user', 'is_active': 0},
        ],
    }))
    write(target / 'identity_db_password', values['identity_db'])
    write(target / 'kanboard_db_password', values['kanboard_db'])
    write(target / 'support_db_password', values['support_db'])
    write(target / 'mariadb_root_password', values['mariadb_root'])
    write(target / 'support-bootstrap.json', json.dumps({
        'name': 'FieldKest Support', 'email': 'support@keplerops.test',
        'fname': 'Support', 'lname': 'Administrator',
        'admin_email': 'support-admin@keplerops.test', 'username': 'platform-admin',
        'passwd': values['support_admin'], 'passwd2': values['support_admin'],
        'prefix': 'ost_', 'dbhost': 'fieldlink-support-db', 'dbname': 'fieldlink_support',
        'dbuser': 'fieldlink_support', 'dbpass': values['support_db'],
    }))
    configuration = target / 'ost-config.php'
    if not configuration.exists():
        write(configuration, '')
    sql = []
    for product, password in (('identity', values['identity_db']), ('staff', values['kanboard_db'])):
        role = 'fieldlink_' + product
        sql.extend((
            f"SELECT 'CREATE ROLE {role} LOGIN' WHERE NOT EXISTS "
            f"(SELECT FROM pg_roles WHERE rolname = '{role}')\\gexec",
            f"ALTER ROLE {role} PASSWORD '{password}';",
            f"SELECT 'CREATE DATABASE {role} OWNER {role}' WHERE NOT EXISTS "
            f"(SELECT FROM pg_database WHERE datname = '{role}')\\gexec",
            f"REVOKE ALL ON DATABASE {role} FROM PUBLIC;",
        ))
    # The enclosing operator directory remains private; PostgreSQL's own UID
    # must be able to read the individually mounted initialization file.
    write(target / 'postgres.sql', '\n'.join(sql) + '\n', 0o444)
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


def configure_ca(operator: Path) -> None:
    target = operator / 'native-workplace'
    values = json.loads((target / 'bootstrap.json').read_text())
    path = target / 'ca/config/ca.json'
    config = json.loads(path.read_text())
    provisioners = config['authority']['provisioners']
    provisioner = {
        'type': 'OIDC', 'name': 'keplerops-staff', 'clientID': 'fieldlink-enrollment',
        'clientSecret': values['enrollment_client'],
        'configurationEndpoint': 'https://identity.keplerops.test/realms/keplerops/.well-known/openid-configuration',
        'domains': ['keplerops.test'], 'listenAddress': ':10000',
    }
    matches = [index for index, value in enumerate(provisioners) if value.get('name') == provisioner['name']]
    if matches:
        provisioners[matches[0]] = provisioner
    else:
        provisioners.append(provisioner)
    write(path, json.dumps(config, indent=2) + '\n')
    # step-ca validates the IdP over HTTPS using the public infrastructure CA.
    write(target / 'ca/issuer-trust.crt', (operator / 'tls/ca.crt').read_text(), 0o644)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--operator-dir', type=Path, required=True)
    parser.add_argument('--ca-config', action='store_true')
    arguments = parser.parse_args()
    os.umask(0o077)
    if arguments.ca_config:
        configure_ca(arguments.operator_dir)
    else:
        prepare(arguments.operator_dir)
