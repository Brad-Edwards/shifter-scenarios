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
    with os.fdopen(descriptor, 'w') as output:
        output.write(value)


def prepare(operator: Path) -> None:
    target = operator / 'native-platform'
    target.mkdir(mode=0o700, exist_ok=True)
    private = target / 'bootstrap.json'
    create(private, json.dumps({name: secrets.token_urlsafe(32) for name in (
        'k3s_token', 'objects_admin_key', 'objects_admin_secret',
        'objects_rowan_key', 'objects_rowan_secret', 'data_owner', 'data_rowan',
        'assistant_admin', 'assistant_bootstrap', 'assistant_jwt',
    )}))
    values = json.loads(private.read_text())
    for directory in ('kubernetes', 'model-source'):
        (target / directory).mkdir(mode=0o700, exist_ok=True)
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
    create(target / 'anythingllm.env', '\n'.join((
        'STORAGE_DIR=/app/server/storage', 'NODE_ENV=production',
        'DISABLE_TELEMETRY=true', 'VECTOR_DB=lancedb', 'EMBEDDING_ENGINE=native',
        'LLM_PROVIDER=ollama', 'OLLAMA_BASE_PATH=http://fieldlink-ollama:11434',
        'OLLAMA_MODEL_PREF=fieldlink-qwen', 'OLLAMA_MODEL_TOKEN_LIMIT=4096',
        'AUTH_TOKEN=' + values['assistant_bootstrap'],
        'JWT_SECRET=' + values['assistant_jwt'],
    )) + '\n', 0o600)
    # The native application updates its own environment after first setup.
    os.chown(target / 'anythingllm.env', 1000, 1000)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--operator-dir', type=Path, required=True)
    arguments = parser.parse_args()
    os.umask(0o077)
    prepare(arguments.operator_dir)
