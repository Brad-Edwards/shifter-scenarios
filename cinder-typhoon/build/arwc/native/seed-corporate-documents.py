#!/usr/bin/env python3
"""Import unchanged, ownership-verified corporate records through native APIs."""
import base64
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import hmac
import json
import os
import re
from pathlib import Path, PurePosixPath
import runpy
from urllib.parse import quote, urlencode
from zipfile import ZipFile

FILES = runpy.run_path('/seed/seed-documents.py')
request, decode, dav, ocs = (FILES[name] for name in ('request', 'decode_ocs', 'dav', 'ocs'))
ROOT = 'Retained corporate records'
SOURCE = Path('/seed/documents')


def shares(path):
    query = urlencode({'format': 'json', 'path': '/' + path})
    return decode(request('GET', '/ocs/v2.php/apps/files_sharing/api/v1/shares?' + query))['data']


def records():
    by_digest = {}
    for document in json.loads(Path('/seed/arwc-documents.json').read_text())['documents']:
        digest = document.get('sha256')
        if digest:
            # File-backed records may carry an excerpt in the document body;
            # the declared hash identifies the complete original archive file.
            if not re.fullmatch(r'[0-9a-f]{64}', digest):
                raise RuntimeError('Malformed corporate source checksum')
        else:
            content = base64.b64decode(document['content_base64'], validate=True) if 'content_base64' in document else document['text'].encode()
            digest = hashlib.sha256(content).hexdigest()
        by_digest.setdefault(digest, []).append(document)
    selected = []
    for source in sorted(SOURCE.glob('*-records.zip')):
        with ZipFile(source) as archive:
            for name in sorted(archive.namelist()):
                if name.endswith('/'):
                    continue
                path = PurePosixPath(name)
                if path.is_absolute() or '..' in path.parts:
                    raise RuntimeError('Unsafe retained record path')
                content = archive.read(name)
                digest = hashlib.sha256(content).hexdigest()
                owners = by_digest.get(digest, [])
                if owners:
                    # Identical source bytes can have multiple entries. The
                    # intersection preserves every original reader boundary.
                    readers = set.intersection(*(set(row['readers']) for row in owners))
                    selected.append((f'{ROOT}/{source.stem}/{name}', content, readers, digest))
    return selected


def provision_users(readers):
    staff = {row['work_email']: row for row in csv.DictReader((SOURCE / 'workforce/a-personnel-register.csv').open())}
    if not readers <= staff.keys():
        raise RuntimeError('Retained record has a reader without a workforce owner')
    for email in sorted(readers):
        user = quote(email, safe='')
        if not ocs('GET', f'users/{user}', accepted=(200, 404)):
            password = hmac.new(os.environ['STAFF_SEED'].encode(), email.encode(), hashlib.sha256).hexdigest()
            ocs('POST', 'users', {'userid': email, 'password': password, 'displayName': staff[email]['name'], 'email': email})
        ocs('POST', f'users/{user}/groups', {'groupid': 'Staff'})


def import_record(record):
    path, content, readers, digest = record
    if not request('HEAD', dav(path), accepted=(200, 404)):
        request('PUT', dav(path), content, headers={'Content-Type': 'application/octet-stream'})
    actual = request('GET', dav(path))
    if hashlib.sha256(actual).hexdigest() != digest:
        raise RuntimeError('Native record differs from its unchanged source')
    existing = shares(path)
    for share in existing:
        if str(share.get('share_type')) != '0' or share.get('share_with') not in readers or int(share.get('permissions', 0)) != 1:
            raise RuntimeError('Existing native record share exceeds the retained reader scope')
    present = {share['share_with'] for share in existing}
    for reader in sorted(readers - present):
        decode(request('POST', '/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json', urlencode({
            'path': '/' + path, 'shareType': 0, 'shareWith': reader, 'permissions': 1,
        }).encode()))
    final = shares(path)
    if {share.get('share_with') for share in final} != readers or any(int(share.get('permissions', 0)) != 1 for share in final):
        raise RuntimeError('Native retained-reader shares did not persist')
    return len(readers)


def seed():
    selected = records()
    parents = sorted({str(parent) for path, _, _, _ in selected for parent in PurePosixPath(path).parents if str(parent) != '.'}, key=lambda p: (len(PurePosixPath(p).parts), p))
    for parent in parents:
        request('MKCOL', dav(parent), accepted=(201, 405))
        if shares(parent):
            raise RuntimeError('Retained record parent is already shared; per-file scope cannot restrict inherited access')
    readers = {reader for _, _, people, _ in selected for reader in people}
    provision_users(readers)
    with ThreadPoolExecutor(max_workers=4) as workers:
        grants = 0
        for completed, count in enumerate(workers.map(import_record, selected), 1):
            grants += count
            if completed % 50 == 0:
                print(json.dumps({'imported_records': completed, 'read_only_shares': grants}), flush=True)
    print(json.dumps({'unchanged_arwc_records': len(selected), 'native_reader_accounts': len(readers), 'read_only_record_shares': grants}))


if __name__ == '__main__':
    seed()
