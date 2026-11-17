"""Restore only the native default self-account role through Keycloak Admin REST."""

import json
import os
import ssl
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE = 'https://identity.keplerops.test'
TOKEN = ''


def api(method: str, path: str, value=None, *, form=False):
    data = None if value is None else (urlencode(value).encode() if form else json.dumps(value).encode())
    headers = {'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json'}
    if TOKEN:
        headers['Authorization'] = 'Bearer ' + TOKEN
    request = Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urlopen(request, context=ssl.create_default_context(cafile='/run/fieldlink/ca.crt'), timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else None
    except HTTPError as error:
        raise RuntimeError(f'Native identity API returned HTTP {error.code}') from None


def repair() -> None:
    role = api('GET', '/admin/realms/keplerops/roles/default-roles-keplerops')
    users = api('GET', '/admin/realms/keplerops/users?username=rowan.ito&exact=true')
    if len(users) != 1:
        raise RuntimeError('Native staff account was not found uniquely')
    path = f'/admin/realms/keplerops/users/{users[0]["id"]}/role-mappings/realm'
    existing = api('GET', path)
    changed = not any(value['id'] == role['id'] for value in existing)
    if changed:
        api('POST', path, [role])
    print(json.dumps({'native_default_account_role_restored': changed}))


if __name__ == '__main__':
    TOKEN = api('POST', '/realms/master/protocol/openid-connect/token', {
        'client_id': 'admin-cli', 'grant_type': 'password',
        'username': os.environ['KC_BOOTSTRAP_ADMIN_USERNAME'],
        'password': os.environ['KC_BOOTSTRAP_ADMIN_PASSWORD'],
    }, form=True)['access_token']
    repair()
