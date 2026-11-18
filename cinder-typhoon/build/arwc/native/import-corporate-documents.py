#!/usr/bin/env python3
"""Run the explicit native record import with a bounded, restored API limit."""
import copy
import json
import os
import re
from pathlib import Path
import signal
import socket
import subprocess
import uuid

COMPOSE = ['docker', 'compose', '--env-file', 'images.env', '-f', 'compose.yaml', '-f', 'corporate.compose.yaml', '-f', 'dmz.compose.yaml']
OCC = COMPOSE + ['exec', '-T', '--user', 'www-data', 'nextcloud', 'php', 'occ']
KEYS = ('ratelimit_overwrite', 'ratelimit.protection.enabled', 'auth.bruteforce.protection.enabled')


def config(name):
    result = subprocess.run(OCC + ['config:system:get', name, '--output=json'], text=True, capture_output=True)
    if result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip():
        return {'present': False}
    result.check_returncode()
    return {'present': True, 'value': json.loads(result.stdout)}


def restore(saved):
    value = saved['ratelimit_overwrite']
    if value['present']:
        subprocess.run(OCC + ['config:system:set', 'ratelimit_overwrite', '--type=json', '--value', json.dumps(value['value'])], check=True, stdout=subprocess.DEVNULL)
    else:
        subprocess.run(OCC + ['config:system:delete', 'ratelimit_overwrite'], check=True, stdout=subprocess.DEVNULL)
    if {key: config(key) for key in KEYS} != saved:
        raise RuntimeError('Native API limit/protection restoration could not be verified')
    print('Native API limits and protection settings restored and verified', flush=True)



def tokens():
    return json.loads(subprocess.check_output(OCC + ['user:auth-tokens:list', 'records-admin', '--output=json'], text=True))


def revoke_batch_token(label, previous_ids):
    created = [row for row in tokens() if row.get('name') == label and str(row['id']) not in previous_ids]
    for row in created:
        subprocess.run(OCC + ['user:auth-tokens:delete', 'records-admin', str(row['id'])], check=True, stdout=subprocess.DEVNULL)
    if any(row.get('name') == label and str(row['id']) not in previous_ids for row in tokens()):
        raise RuntimeError('Native import app-password revocation could not be verified')


def main():
    if (socket.gethostname() not in ('cinder-arwc-dev','cinder-arwc-golden') and not os.path.exists('/etc/cinder-arwc-image')) or os.geteuid() != 0:
        raise SystemExit('Use root on cinder-arwc-dev for the explicit data import')
    os.chdir(Path(__file__).resolve().parent)
    os.umask(0o077)
    routes = json.loads(subprocess.check_output(OCC + ['router:list', '--output=json'], text=True))
    matches = [row['route'] for row in routes if row.get('path') == '/ocs/v2.php/apps/files_sharing/api/v1/shares' and row.get('request') == 'POST']
    if len(matches) != 1:
        raise RuntimeError('Native share-create route is missing or ambiguous')
    saved = {key: config(key) for key in KEYS}
    snapshot = Path('.operator') / ('corporate-import-limit-' + uuid.uuid4().hex + '.json')
    snapshot.write_text(json.dumps(saved))
    snapshot.chmod(0o600)
    modified = copy.deepcopy(saved['ratelimit_overwrite'].get('value', {}))
    modified.setdefault(matches[0], {})['user'] = {'limit': 25000, 'period': 3600}
    name = 'arwc-native-record-import-' + uuid.uuid4().hex[:12]
    process = None
    token_label = 'corporate-record-import-' + uuid.uuid4().hex
    previous_token_ids = {str(row['id']) for row in tokens()}
    def interrupted(signum, _frame):
        raise SystemExit(128 + signum)
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, interrupted)
    try:
        subprocess.run(OCC + ['config:system:set', 'ratelimit_overwrite', '--type=json', '--value', json.dumps(modified)], check=True, stdout=subprocess.DEVNULL)
        environment = dict(os.environ, NC_PASS=Path('.operator/documents_admin_password').read_text().strip())
        command = COMPOSE + ['exec', '-T', '--user', 'www-data', '--env', 'NC_PASS', 'nextcloud', 'php', 'occ',
                             'user:auth-tokens:add', 'records-admin', '--password-from-env', '--name', token_label]
        secret = subprocess.check_output(command, text=True, env=environment).strip().splitlines()[-1]
        if not re.fullmatch(r'[A-Za-z0-9]{72}', secret):
            raise RuntimeError('Native app-password creation did not return the supported token format')
        environment = dict(os.environ, DOCUMENTS_IMPORT_PASSWORD=secret)
        process = subprocess.Popen(COMPOSE + ['--profile', 'seed', 'run', '--rm', '--name', name,
                                             '--env', 'DOCUMENTS_IMPORT_PASSWORD', 'seed-corporate-documents'], env=environment)
        result = process.wait()
    finally:
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(signum, signal.SIG_IGN)
        try:
            if process is not None and process.poll() is None:
                subprocess.run(['docker', 'rm', '-f', name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                process.wait(timeout=30)
        finally:
            try:
                revoke_batch_token(token_label, previous_token_ids)
            finally:
                restore(saved)
    raise SystemExit(result)


if __name__ == '__main__':
    main()
