#!/usr/bin/env python3
"""Initial company users and workspace through native AnythingLLM administration."""
from __future__ import annotations

import argparse
import json
import uuid
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



def import_document(path: Path, slug: str, token: str) -> None:
    boundary = uuid.uuid4().hex
    body = ('--' + boundary + '\r\nContent-Disposition: form-data; name="file"; filename="'
            + path.name + '"\r\nContent-Type: text/markdown\r\n\r\n').encode()
    body += path.read_bytes() + ('\r\n--' + boundary + '--\r\n').encode()
    request = Request(BASE + '/workspace/' + slug + '/upload-and-embed', data=body, headers={
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'multipart/form-data; boundary=' + boundary,
    })
    with urlopen(request, timeout=180) as response:
        result = json.load(response)
    if not result.get('success') or not result.get('document'):
        raise RuntimeError('Native company document import failed')


def seed(operator: Path) -> None:
    marker = operator / 'native-platform/assistant-company-seeded'
    if marker.exists():
        print('Native assistant company state retained.')
        return
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
    api('/system/update-env', {'OllamaLLMModelPref': 'fieldlink-qwen:latest'}, token)
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
    documents = operator / 'native-platform/assistant-documents'
    documents.mkdir(mode=0o700, exist_ok=True)
    source = Path(__file__).resolve().parents[3] / 'assets/narrative/documents/keplerops'
    for name in ('company-history.md', 'working-guide.md', 'customer-relationships.md'):
        imported = documents / name
        if not imported.exists():
            import_document(source / name, workspace['slug'], token)
            imported.touch(mode=0o600)
    marker.touch(mode=0o600)
    print('Native assistant company users and workspace ready.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--operator-dir', type=Path, required=True)
    arguments = parser.parse_args()
    seed(arguments.operator_dir)
