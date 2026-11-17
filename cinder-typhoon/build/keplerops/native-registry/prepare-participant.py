"""Prepare the native npm client configuration for the developer account."""

import argparse
import base64
import json
import os
from pathlib import Path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--operator-dir', type=Path, required=True)
    operator = parser.parse_args().operator_dir
    destination = operator / 'range-seed/participant/npmrc'
    if not destination.exists():
        credentials = json.loads((operator / 'range-seed/runtime-credentials.json').read_text())['credentials']
        authorization = base64.b64encode(('rowan.ito:' + credentials['developer_token']).encode()).decode()
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as output:
            output.write('registry=https://packages.keplerops.test/\n'
                         '//packages.keplerops.test/:_auth=' + authorization + '\n'
                         'cafile=/home/rowan/.local/share/keplerops/ca.crt\n'
                         'audit=false\nfund=false\n')
    destination.chmod(0o444)
