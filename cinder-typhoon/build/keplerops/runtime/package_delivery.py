"""Use native npm selection and the existing isolated package consumer."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile

from credentials import credential


PACKAGE = '@keplerops/fieldlink-connector'


def pack_connector(specification: str) -> tuple[dict[str, object], bytes]:
    """Fetch a registry-owned version through npm's normal version selection."""
    if not re.fullmatch(r'\^?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?', specification):
        raise ValueError('invalid_connector_version')
    authorization = base64.b64encode(
        ('svc-fieldlink-ci:' + credential('ci_registry_reader')).encode()
    ).decode()
    with tempfile.TemporaryDirectory(prefix='fieldlink-package-') as temporary:
        root = Path(temporary)
        config = root / 'npmrc'
        config.write_text(
            'registry=https://packages.keplerops.test/\n'
            '//packages.keplerops.test/:_auth=' + authorization + '\n'
            'cafile=/tmp/fieldkest-ca.crt\naudit=false\nfund=false\n'
        )
        config.chmod(0o600)
        result = subprocess.run(
            ['npm', 'pack', f'{PACKAGE}@{specification}', '--json', '--pack-destination', temporary],
            env=os.environ | {'NPM_CONFIG_USERCONFIG': str(config), 'NPM_CONFIG_CACHE': str(root / 'cache')},
            capture_output=True, text=True, check=True, timeout=30,
        )
        records = json.loads(result.stdout)
        if not isinstance(records, list) or len(records) != 1 or records[0].get('name') != PACKAGE:
            raise ValueError('invalid_registry_package')
        metadata = records[0]
        filename = metadata['filename']
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError('invalid_registry_filename')
        path = root / filename
        if path.stat().st_size > 524_288:
            raise ValueError('connector_package_too_large')
        return metadata, path.read_bytes()


def consume_package(archive: bytes, request: dict[str, object]) -> dict[str, object]:
    payload = json.dumps({
        'kind': 'node-package', 'archive_base64': base64.b64encode(archive).decode(),
        'input': request,
    }, separators=(',', ':')).encode() + b'\n'
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(15)
        client.connect('/run/fieldkest-runner/runner.sock')
        client.sendall(payload)
        response = b''
        while not response.endswith(b'\n'):
            chunk = client.recv(65536)
            if not chunk or len(response) + len(chunk) > 1_100_000:
                raise RuntimeError('invalid_package_consumer_response')
            response += chunk
    return json.loads(response)
