"""Import retained FieldLink repositories through native Gitea administration."""

from __future__ import annotations

import base64
import configparser
import io
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from credentials import credential


ROOT = Path('/var/lib/gitea')
CONFIG = ROOT / 'data/app.ini'
BASE = 'https://source.keplerops.test'
ENGINEERING_NOTE = Path('/opt/fieldkest/engineering-note.md')
CONTEXT = ssl.create_default_context(cafile='/run/fieldkest-tls/ca.crt')
REPOSITORIES = {
    'fieldlink-connector': 'FieldLink customer connector and delivery notes',
    'policy-compiler': 'Retained policy compiler and migration examples',
    'connector-archive': 'Supported connector archive and maintenance records',
    'release-signer-history': 'Release signing history and rollover records',
}


def api(method: str, path: str, password: str, value: object | None = None) -> object:
    """Call the range-local Gitea administration endpoint."""
    authorization = base64.b64encode(f'fieldlink-bootstrap:{password}'.encode()).decode()
    request = Request(
        BASE + '/api/v1' + path,
        data=None if value is None else json.dumps(value).encode(),
        headers={'Authorization': 'Basic ' + authorization, 'Content-Type': 'application/json'},
        method=method,
    )
    with urlopen(request, context=CONTEXT, timeout=30) as response:
        payload = response.read()
    return json.loads(payload) if payload else None


def exists(path: str, password: str) -> bool:
    try:
        api('GET', path, password)
    except HTTPError as error:
        if error.code == 404:
            return False
        raise
    return True


def delivery_history(password: str) -> None:
    """Retain the delivery team's ordinary Git configuration history."""
    marker = ROOT / 'data/.delivery-history-seeded'
    if marker.exists():
        return
    branch = 'delivery-operations'
    if exists('/repos/fieldkest/fieldlink-connector/branches/' + branch, password):
        marker.touch(mode=0o600)
        return
    authorization = base64.b64encode(f'fieldlink-bootstrap:{password}'.encode()).decode()
    environment = os.environ | {
        'GIT_CONFIG_COUNT': '2',
        'GIT_CONFIG_KEY_0': 'http.extraHeader',
        'GIT_CONFIG_VALUE_0': 'Authorization: Basic ' + authorization,
        'GIT_CONFIG_KEY_1': 'http.sslCAInfo',
        'GIT_CONFIG_VALUE_1': '/run/fieldkest-tls/ca.crt',
        'GIT_AUTHOR_NAME': 'Talia Mornac',
        'GIT_AUTHOR_EMAIL': 'talia.mornac@fieldkest.test',
        'GIT_COMMITTER_NAME': 'Talia Mornac',
        'GIT_COMMITTER_EMAIL': 'talia.mornac@fieldkest.test',
        'GIT_AUTHOR_DATE': '2026-09-17T11:32:00Z',
        'GIT_COMMITTER_DATE': '2026-09-17T11:32:00Z',
    }
    with tempfile.TemporaryDirectory(prefix='fieldlink-delivery-') as temporary:
        directory = Path(temporary)
        def git(*arguments: str) -> None:
            subprocess.run(['git', '-C', temporary, *arguments], check=True, env=environment,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        git('clone', '--branch', 'main', '--single-branch',
            BASE + '/fieldkest/fieldlink-connector.git', '.')
        git('checkout', '-b', branch, 'fk-test-6d1e9f7')
        (directory / 'delivery').mkdir()
        (directory / 'delivery/README.md').write_text(
            '# Customer package delivery\n\n'
            'The connector registry is https://packages.keplerops.test/.\n'
            'This workspace publishes the FieldLink connector; support rehearsal packages\n'
            'are maintained by the integration team. Package compatibility is checked by\n'
            'the fieldlink-package-check Jenkins job before a release is approved.\n'
        )
        publisher = base64.b64encode(
            ('fieldlink-importer-publisher:' + credential('registry_publisher_token')).encode()
        ).decode()
        (directory / 'delivery/.npmrc').write_text(
            'registry=https://packages.keplerops.test/\n'
            '//packages.keplerops.test/:_auth=' + publisher + '\n'
            'cafile=/etc/fieldlink/tls/ca.crt\n'
        )
        git('add', 'delivery')
        git('commit', '-m', 'Prepare customer package publishing workspace')
        (directory / 'delivery/.npmrc').unlink()
        (directory / 'delivery/.gitignore').write_text('.npmrc\n')
        git('add', '-A', 'delivery')
        git('commit', '-m', 'Use managed credentials for customer publishing')
        git('push', 'origin', 'HEAD:refs/heads/' + branch)
    marker.touch(mode=0o600)


def engineering_note(password: str) -> None:
    """Retain the ordinary engineering record in native repository history."""
    marker = ROOT / 'data/.connector-engineering-note-seeded'
    if marker.exists():
        return
    repository = '/repos/fieldkest/connector-archive/contents/'
    note = 'internal/fieldlink/legacy-diagnostics/CRR-OG2/ENG-FLK-LEGACY-42.md'
    if not exists(repository + note, password):
        api('POST', repository + note, password, {
            'branch': 'main', 'message': 'Retain Cedar Run engineering reference',
            'content': base64.b64encode(ENGINEERING_NOTE.read_bytes()).decode(),
        })
    readme = api('GET', repository + 'README.md', password)
    contents = base64.b64decode(readme['content']).decode()
    guidance = ('Archived internal diagnostic paths are retained as repository file paths. '
                'Match the path and engineering-note object ID emitted by the retained loader '
                'to its Markdown record in this repository.')
    if guidance not in contents:
        api('PUT', repository + 'README.md', password, {
            'branch': 'main', 'message': 'Document engineering archive locations', 'sha': readme['sha'],
            'content': base64.b64encode((contents.rstrip() + '\n\n' + guidance + '\n').encode()).decode(),
        })
    marker.touch(mode=0o600)


def entitlement_history(password: str) -> None:
    """Seed the ENT-ARWC-DIAG-0698 entitlement record into connector-archive with two commits.

    K08.1 requires recovering the entitlement record and its revision history from Gitea
    rather than from the registry-local endpoint.  The two commits here establish the
    revision 3 → revision 4 progression visible to the participant.
    """
    marker = ROOT / 'data/.entitlement-history-seeded'
    if marker.exists():
        return
    path = 'internal/fieldlink/legacy-diagnostics/CRR-OG2/ENT-ARWC-DIAG-0698.json'
    repository = '/repos/fieldkest/connector-archive/contents/'
    # Revision 3 — initial retained record
    _RECORD_REV3 = json.dumps({
        "cipher": "AES-256-GCM",
        "ciphertext_base64": (
            "UcSjQere8JW9BEDZrwUan4XW4jRW/k36mPtLIUVSrcp6HBVy1QILC3I/73YYxMIR6Ixs8RpRSI7"
            "otvX1Cr02gdTJuiOPlde91Y5U8dnkPpiKR3XwbPGf16SbDOCPKwkbV95r0QloWKWgRxxtHzsQaht"
            "Nbsr8Op3f7BCImM2mz927WlefwSSuGbqOZdSHrIbOQn+zfNAz8uaxSQYLHjrF3IFC/ctkw/nSLwK"
            "nWeoUJYNg6aCNLmRGBrAECSeN8ZhGB8KtYeI0O6NFL2GjA4qfTUGL/mTfYDnbkKf1vqsXEozT8N"
            "tAdiqz5L7XzONz2rBLyspyfeb/71i8sVtt/5hP59mK6tlBDDlq0gHGeUA="
        ),
        "customer_id": "TEN-ARWC-019",
        "feature_id": "diagnostic-loader",
        "grammar": "fieldkest-entitlement/v1 canonical JSON; UTF-8 NFC strings; lexicographically sorted keys",
        "key_id": "fk-entitlement-legacy-2026-08",
        "nonce_hex": "454e542d303639382d563121",
        "package_revision": "FLK-6.9.8",
        "record_id": "ENT-ARWC-DIAG-0698",
        "revision": 3,
        "schema": "fieldkest.entitlement-record/v1",
        "tag_base64": "IUvC8saIDcdgH/ACOtSrMQ==",
    }, indent=2, sort_keys=True)
    # Revision 4 — updated record (same ciphertext; revision counter incremented)
    _RECORD_REV4 = _RECORD_REV3.replace('"revision": 3', '"revision": 4')
    if not exists(repository + path, password):
        api('POST', repository + path, password, {
            'branch': 'main',
            'message': 'Retain ENT-ARWC-DIAG-0698 entitlement record revision 3',
            'content': base64.b64encode(_RECORD_REV3.encode()).decode(),
        })
    file_meta = api('GET', repository + path, password)
    if json.loads(base64.b64decode(file_meta['content'])).get('revision') == 3:
        api('PUT', repository + path, password, {
            'branch': 'main',
            'message': 'Update entitlement record to revision 4',
            'sha': file_meta['sha'],
            'content': base64.b64encode(_RECORD_REV4.encode()).decode(),
        })
    # K08.2: also seed the v2-encrypted record (sealed with v2 HKDF key, revision 3).
    # The expiry_policy field in the record is the missing context participants must use.
    _V2_PATH = 'internal/fieldlink/legacy-diagnostics/CRR-OG2/ENT-ARWC-DIAG-0698-V2.json'
    _RECORD_V2 = json.dumps({
        "cipher": "AES-256-GCM",
        "ciphertext_base64": (
            "SbxbxJEUXOSCN/EdEcRwL/FSI2T21IkuCVkhefb4iBBbIJE9K3NTusSwXD6Z1sE98X38xk+yv7oO"
            "8YnBrR1I24J243ZFFsELiRTsseLVzYTTAcP3rVnTgAgxsvcLNfV9Mrr3GuY27DWenvVDVaDao8XxhC"
            "CdY0rouwbt0gn9JMuJC2Od6OFMH1q3rmK1qWW3tHuASk9J/0Qr21UBsX80BUhiDtl2pMpY74Iost"
            "Q4I4E0zsWUScAipGY+Vgfwcs/p7ntNTj4q+YJF908/MSW+iNU3XUcCUs27mu12X0I9RgR/4LqKg3Y"
            "k0MmD"
        ),
        "customer_id": "TEN-ARWC-019",
        "expiry_policy": "maintenance-window:2026-09-30T23:59:59Z",
        "feature_id": "diagnostic-loader",
        "grammar": "fieldkest-entitlement/v1 canonical JSON; UTF-8 NFC strings; lexicographically sorted keys",
        "key_id": "fk-entitlement-legacy-2026-08",
        "nonce_hex": "525728f55b006f5edf1f5434",
        "package_revision": "FLK-6.9.8",
        "record_id": "ENT-ARWC-DIAG-0698",
        "revision": 3,
        "schema": "fieldkest.entitlement-record/v2",
        "tag_base64": "rFbi5ilwHusX7XmQiY1PZA==",
    }, indent=2, sort_keys=True)
    if not exists(repository + _V2_PATH, password):
        api('POST', repository + _V2_PATH, password, {
            'branch': 'main',
            'message': 'Retain ENT-ARWC-DIAG-0698 version 2 entitlement (revision 3, v2 key)',
            'content': base64.b64encode(_RECORD_V2.encode()).decode(),
        })
    # K08.3: plaintext template showing the allowed field structure for an alternate entitlement.
    _K83_TEMPLATE_PATH = 'internal/fieldlink/legacy-diagnostics/CRR-OG2/ENT-ARWC-DIAG-0698-plaintext-template.json'
    _K83_TEMPLATE = json.dumps({
        "_note": (
            "Encrypt this canonical JSON with the K08.2 v2 HKDF key (base_info+expiry_policy). "
            "The checker binds customer_id and feature_id; wrong values return 422."
        ),
        "customer_id": "TEN-ARWC-019",
        "expiry_policy": "<value from K08.2 checker result>",
        "feature_id": "diagnostic-loader",
        "package_revision": "FLK-6.9.8",
        "record_id": "ENT-ARWC-DIAG-0698",
        "revision": "<integer != 4; must differ from K08.1 and K08.2 baselines>",
        "schema": "fieldkest-entitlement/v1",
    }, indent=2, sort_keys=True)
    if not exists(repository + _K83_TEMPLATE_PATH, password):
        api('POST', repository + _K83_TEMPLATE_PATH, password, {
            'branch': 'main',
            'message': 'Add K08.3 alternate entitlement plaintext template',
            'content': base64.b64encode(_K83_TEMPLATE.encode()).decode(),
        })
    marker.touch(mode=0o600)


def archive_reference_repository(password: str) -> None:
    """Make the retained connector repository read-only through Gitea."""
    api('PATCH', '/repos/fieldkest/fieldlink-connector', password, {'archived': True})


def main() -> None:
    password_path = ROOT / 'data/.bootstrap-password'
    if not password_path.exists():
        descriptor = os.open(password_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(secrets.token_urlsafe(32))
    password = password_path.read_text()
    users = subprocess.check_output(
        ['/usr/local/bin/gitea', 'admin', 'user', 'list', '--config', str(CONFIG)], text=True,
    )
    if 'fieldlink-bootstrap' not in users:
        subprocess.run(
            ['/usr/local/bin/gitea', 'admin', 'user', 'create', '--config', str(CONFIG),
             '--username', 'fieldlink-bootstrap', '--password', password,
             '--email', 'source-admin@fieldkest.test', '--admin', '--must-change-password=false'],
            check=True, stdout=subprocess.DEVNULL,
        )
    if not exists('/users/rowan.ito', password):
        api('POST', '/admin/users', password, {
            'username': 'rowan.ito', 'password': credential('developer_token'),
            'email': 'rowan.ito@fieldkest.test', 'must_change_password': False,
            'login_name': 'rowan.ito', 'source_id': 0,
        })
    if not exists('/orgs/fieldkest', password):
        api('POST', '/orgs', password, {'username': 'fieldkest', 'visibility': 'private'})
    for name, description in REPOSITORIES.items():
        path = f'/repos/fieldkest/{name}'
        marker = ROOT / f'data/.seeded-{name}'
        if marker.exists():
            continue
        if not exists(path, password):
            api('POST', '/orgs/fieldkest/repos', password, {
                'name': name, 'description': description, 'private': True,
                'auto_init': False, 'default_branch': 'main',
            })
        authorization = base64.b64encode(f'fieldlink-bootstrap:{password}'.encode()).decode()
        environment = os.environ | {
            'GIT_CONFIG_COUNT': '2',
            'GIT_CONFIG_KEY_0': 'http.extraHeader',
            'GIT_CONFIG_VALUE_0': 'Authorization: Basic ' + authorization,
            'GIT_CONFIG_KEY_1': 'http.sslCAInfo',
            'GIT_CONFIG_VALUE_1': '/run/fieldkest-tls/ca.crt',
        }
        with tempfile.TemporaryDirectory(prefix='gitea-seed-') as temporary:
            subprocess.run(
                ['git', 'clone', '--bare', str(ROOT / f'seeds/{name}.bundle'), temporary],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ['git', '-C', temporary, 'push', '--mirror', BASE + f'/fieldkest/{name}.git'],
                check=True, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        api('PUT', path + '/collaborators/rowan.ito', password, {'permission': 'read'})
        if name in {'policy-compiler', 'connector-archive'}:
            api('PATCH', path, password, {
                'website': 'https://source-tools.keplerops.test:8443/.well-known/fieldkest-client',
            })
        marker.touch(mode=0o600)
    handover = json.loads((ROOT / 'handovers/HND-FLK-2026-09.json').read_text())
    marker = ROOT / 'data/.handover-seeded'
    if not marker.exists():
        api('POST', '/repos/fieldkest/fieldlink-connector/issues', password, {
            'title': 'Connector support handover HND-FLK-2026-09',
            'body': f"Release {handover['release']} · revision {handover['revision']}\n\n"
                    + f"Owner: {handover['owner']}\n\n"
                    + '\n'.join('- ' + note for note in handover['notes']),
        })
        marker.touch(mode=0o600)
    ordinary_marker = ROOT / 'data/.ordinary-issues-seeded'
    if not ordinary_marker.exists():
        for title, body in (
            ('Connector 7.3 maintenance follow-up', 'Retain the Riverbend compatibility notes until the September support window closes.'),
            ('Document package channel ownership', 'Release Operations owns the stable package channel. Customer Support owns the handover record.'),
            ('North Quay rehearsal summary', 'The rehearsal completed with the expected connector revision and no customer-side retry.'),
        ):
            api('POST', '/repos/fieldkest/fieldlink-connector/issues', password, {'title': title, 'body': body})
        ordinary_marker.touch(mode=0o600)
    if 'fieldlink-connector' in REPOSITORIES:
        delivery_history(password)
        # This retained release repository is reference material for the
        # developer workstation.  Gitea's native archived state preserves
        # authenticated reads while rejecting issue, branch and repository
        # writes by ordinary collaborators.
        archive_reference_repository(password)
    if 'connector-archive' in REPOSITORIES:
        engineering_note(password)
        entitlement_history(password)
    print('Native Gitea repositories and handover ready')


def configure(template: Path = Path('/etc/gitea/app.ini')) -> None:
    """Keep generated product secrets stable while applying tracked settings."""
    secret_file = ROOT / 'data/.native-secrets.json'
    if not secret_file.exists():
        descriptor = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as handle:
            json.dump({name: secrets.token_hex(32) for name in ('secret', 'internal', 'jwt')}, handle)
    values = json.loads(secret_file.read_text())
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config.read_string('[DEFAULT]\n' + template.read_text())
    config['security']['SECRET_KEY'] = values['secret']
    config['security']['INTERNAL_TOKEN'] = values['internal']
    config['oauth2']['JWT_SECRET'] = values['jwt']
    output = io.StringIO()
    config.write(output)
    CONFIG.write_text(output.getvalue().removeprefix('[DEFAULT]\n'))
    CONFIG.chmod(0o600)


if __name__ == '__main__':
    if sys.argv[1:] == ['--configure']:
        configure()
    else:
        main()
