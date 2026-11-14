#!/usr/bin/env python3
"""Check package metadata and retain the delivery build workspace."""

import base64
import json
import os
from pathlib import Path
import subprocess


workspace = Path('package-workspace')
workspace.mkdir(exist_ok=True)
authorization = base64.b64encode((
    os.environ['FIELDLINK_NPM_USER'] + ':' + os.environ['FIELDLINK_NPM_PASSWORD']
).encode()).decode()
configuration = workspace / '.npmrc'
configuration.write_text(
    'registry=https://packages.keplerops.test/\n'
    '//packages.keplerops.test/:_auth=' + authorization + '\n'
    'cafile=/tmp/fieldlink-ca.crt\n'
    'audit=false\nfund=false\n'
)
configuration.chmod(0o600)
environment = os.environ | {'NPM_CONFIG_CACHE': str(workspace.resolve() / '.cache')}
for package in ('@keplerops/fieldlink-connector@7.4.2', '@keplerops/support-rehearsal@1.3.1'):
    result = subprocess.run(['npm', 'view', package, 'name', 'version', '--json'],
                            cwd=workspace, env=environment, capture_output=True, check=True, timeout=30)
    metadata = json.loads(result.stdout)
    (workspace / (metadata['name'].split('/')[-1] + '.json')).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + '\n')
result = subprocess.run(['npm', 'pack', '@keplerops/fieldlink-connector@7.4.2', '--json'],
                        cwd=workspace, env=environment, capture_output=True, check=True, timeout=30)
(workspace / 'package-manifest.json').write_text(
    json.dumps(json.loads(result.stdout), indent=2, sort_keys=True) + '\n')
print('Connector and support metadata checked; connector package retained.')
