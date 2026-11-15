#!/usr/bin/env python3
"""Initial company users and workspace through native AnythingLLM administration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

BASE = 'http://10.77.56.42:3001/api'


def api(path: str, data: dict | None = None, token: str | None = None) -> dict:
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = Request(BASE + path, data=None if data is None else json.dumps(data).encode(), headers=headers)
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get('error'):
        raise RuntimeError('Native assistant administration rejected ' + path)
    return result


def seed(operator: Path) -> None:
    values = json.loads((operator / 'native-platform/bootstrap.json').read_text())
    workplace = json.loads((operator / 'native-workplace/bootstrap.json').read_text())
    runtime = json.loads((operator / 'range-seed/runtime-credentials.json').read_text())['credentials']
    if not api('/system/multi-user-mode').get('multiUserMode'):
        initial = api('/request-token', {'password': values['assistant_bootstrap']})
        api('/system/enable-multi-user', {'username': 'platform-admin', 'password': values['assistant_admin']}, initial['token'])
    session = api('/request-token', {'username': 'platform-admin', 'password': values['assistant_admin']})
    token = session['token']
    if not token:
        raise RuntimeError('Native assistant administrator authentication failed')
    users = {value['username']: value for value in api('/admin/users', token=token)['users']}
    for username, password, role in (
        ('rowan.ito', runtime['developer_token'], 'default'),
        ('maya.ranscombe', workplace['staff_maya'], 'default'),
        ('talia.mornac', workplace['staff_talia'], 'manager'),
    ):
        if username not in users:
            value = api('/admin/users/new', {'username': username, 'password': password, 'role': role}, token)['user']
            if not value:
                raise RuntimeError('Native assistant company account import failed')
            users[username] = value
    workspaces = api('/workspaces', token=token)['workspaces']
    workspace = next((value for value in workspaces if value['name'] == 'FieldLink Operations'), None)
    if not workspace:
        workspace = api('/admin/workspaces/new', {'name': 'FieldLink Operations'}, token)['workspace']
        result = api('/admin/workspaces/' + str(workspace['id']) + '/update-users', {
            'userIds': [users[name]['id'] for name in ('rowan.ito', 'maya.ranscombe', 'talia.mornac')],
        }, token)
        if not result.get('success'):
            raise RuntimeError('Native assistant workspace assignment failed')
    print('Native assistant company users and workspace ready.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--operator-dir', type=Path, required=True)
    arguments = parser.parse_args()
    seed(arguments.operator_dir)
