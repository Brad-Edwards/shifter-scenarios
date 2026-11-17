#!/usr/bin/env python3
"""Submit a report provider to the FieldLink isolated review service."""

import base64
import json
from pathlib import Path
import ssl
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main() -> int:
    archive = Path('provider.zip').read_bytes()
    if not archive or len(archive) > 524_288:
        raise ValueError('provider.zip must contain at most 512 KiB')
    credential = json.loads(Path('/tmp/fieldlink-ci-users.json').read_text())['developer_password']
    headers = {'Authorization': 'Bearer ' + credential, 'Content-Type': 'application/json'}
    context = ssl.create_default_context(cafile='/tmp/fieldlink-ca.crt')
    request = Request('https://review.keplerops.test/api/jobs', headers=headers, data=json.dumps({
        'template': 'report-consumer-v2',
        'input': {'archive_base64': base64.b64encode(archive).decode()},
    }).encode())
    try:
        with urlopen(request, context=context, timeout=30) as response:
            submitted = json.load(response)
    except HTTPError as error:
        detail = json.loads(error.read(16384))
        print('Report rejected:', detail.get('error', 'review_failed'))
        return 1
    job_id = submitted['job_id']
    request = Request('https://review.keplerops.test/api/jobs/' + job_id, headers=headers)
    with urlopen(request, context=context, timeout=15) as response:
        result = json.load(response)
    if result.get('state') != 'success' or result.get('job_id') != job_id:
        raise ValueError('review did not produce a completed report')
    destination = Path('reports')
    destination.mkdir(exist_ok=True)
    (destination / 'review-result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    (destination / 'report.json').write_text(json.dumps(result['report'], indent=2, sort_keys=True) + '\n')
    print('Report accepted:', job_id)
    print('Report SHA-256:', result['report_sha256'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
