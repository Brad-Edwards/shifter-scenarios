#!/usr/bin/env python3
"""Create missing private inputs for native cloud, data and assistant products."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets


def create(path: Path, value: str, mode: int = 0o600) -> None:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError:
        return
    os.fchmod(descriptor, mode)
    with os.fdopen(descriptor, 'w') as output:
        output.write(value)


def prepare(operator: Path) -> None:
    target = operator / 'native-platform'
    target.mkdir(mode=0o700, exist_ok=True)
    private = target / 'bootstrap.json'
    create(private, json.dumps({name: secrets.token_urlsafe(32) for name in (
        'k3s_token', 'objects_admin_key', 'objects_admin_secret',
        'objects_rowan_key', 'objects_rowan_secret', 'data_rowan',
        'assistant_admin', 'assistant_bootstrap', 'assistant_jwt',
    )}))
    values = json.loads(private.read_text())
    for directory in ('kubernetes', 'model-source', 'model-converted', 'k3s-images'):
        (target / directory).mkdir(mode=0o700, exist_ok=True)
    runtime = json.loads((operator / 'range-seed/runtime-credentials.json').read_text())['credentials']
    create(target / 'assistant-support.json', json.dumps({'token': runtime['assistant_tool_session']}), 0o400)
    os.chown(target / 'assistant-support.json', 1000, 1000)
    create(target / 'k3s.env', 'K3S_TOKEN=' + values['k3s_token'] + '\n')
    identities = [{
        'name': 'platform-admin',
        'credentials': [{'accessKey': values['objects_admin_key'], 'secretKey': values['objects_admin_secret']}],
        'actions': ['Admin', 'Read', 'Write', 'List', 'Tagging'],
    }, {
        'name': 'rowan.ito',
        'credentials': [{'accessKey': values['objects_rowan_key'], 'secretKey': values['objects_rowan_secret']}],
        'actions': [action + ':fieldlink-exports' for action in ('Read', 'Write', 'List', 'Tagging')],
    }]
    create(target / 's3.json', json.dumps({'identities': identities}), 0o444)
    os.chmod(target / 's3.json', 0o444)
    create(target / 'anythingllm.env', '\n'.join((
        'STORAGE_DIR=/app/server/storage', 'NODE_ENV=production',
        'DISABLE_TELEMETRY=true', 'VECTOR_DB=lancedb', 'EMBEDDING_ENGINE=native',
        'LLM_PROVIDER=ollama', 'OLLAMA_BASE_PATH=http://fieldlink-ollama:11434',
        'OLLAMA_MODEL_PREF=fieldlink-qwen', 'OLLAMA_MODEL_TOKEN_LIMIT=4096',
        'AUTH_TOKEN=' + values['assistant_bootstrap'],
        'JWT_SECRET=' + values['assistant_jwt'],
    )) + '\n', 0o600)
    create(target / 'aws-credentials', '[default]\naws_access_key_id=' + values['objects_rowan_key'] + '\naws_secret_access_key=' + values['objects_rowan_secret'] + '\n')
    create(target / 'aws-config', '[default]\nregion=us-east-1\nca_bundle=/home/rowan/.local/share/keplerops/ca.crt\ns3=\n    addressing_style=path\n')
    create(target / 'pgpass', 'data.keplerops.test:5432:fieldlink_data:rowan_data:' + values['data_rowan'] + '\n')
    create(target / 'pg_service.conf', '[fieldlink]\nhost=data.keplerops.test\nport=5432\ndbname=fieldlink_data\nuser=rowan_data\nsslmode=verify-full\nsslrootcert=/home/rowan/.local/share/keplerops/ca.crt\n')
    create(target / 'postgres.sql', '\n'.join((
        "SELECT 'CREATE ROLE fieldlink_data_owner NOLOGIN' WHERE NOT EXISTS "
        "(SELECT FROM pg_roles WHERE rolname='fieldlink_data_owner')\\gexec",
        "SELECT 'CREATE ROLE rowan_data LOGIN' WHERE NOT EXISTS "
        "(SELECT FROM pg_roles WHERE rolname='rowan_data')\\gexec",
        "ALTER ROLE rowan_data PASSWORD '" + values['data_rowan'] + "';",
        "SELECT 'CREATE DATABASE fieldlink_data OWNER fieldlink_data_owner' WHERE NOT EXISTS "
        "(SELECT FROM pg_database WHERE datname='fieldlink_data')\\gexec",
        "REVOKE ALL ON DATABASE fieldlink_data FROM PUBLIC;",
        "GRANT CONNECT ON DATABASE fieldlink_data TO rowan_data;",
    )) + '\n')
    # The native application updates its own environment after first setup.
    os.chown(target / 'anythingllm.env', 1000, 1000)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--operator-dir', type=Path, required=True)
    arguments = parser.parse_args()
    os.umask(0o077)
    prepare(arguments.operator_dir)
