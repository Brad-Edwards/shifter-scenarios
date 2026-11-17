#!/usr/bin/env python3
"""K06.2 seed: BLD-611 package-check run and svc-fieldlink-ci .npmrc artifact.

Seeds the native CI review service (review.keplerops.test) with the BLD-611
package-check run record and the retained package-workspace .npmrc artifact.
The .npmrc contains the svc-fieldlink-ci registry credential, which grants read
access to @keplerops/support-rehearsal (the K06.2 target package).
"""

from __future__ import annotations

import base64
import argparse
import json
from pathlib import Path


VOLUME_RUNS = Path('/var/lib/docker/volumes/cinder-keplerops-ci-runs/_data')
VOLUME_ARTIFACTS = Path('/var/lib/docker/volumes/cinder-keplerops-ci-artifacts/_data')


def seed(operator: Path) -> None:
    marker = operator / 'native-ci/k06-ci-seeded'
    if marker.exists():
        print('K06 CI artifact already seeded.')
        return
    runtime = json.loads((operator / 'range-seed/runtime-credentials.json').read_text())
    ci_password = runtime['credentials']['ci_registry_reader']
    auth = base64.b64encode(f'svc-fieldlink-ci:{ci_password}'.encode()).decode()

    npmrc_content = (
        'registry=https://packages.keplerops.test/\n'
        f'//packages.keplerops.test/:_auth={auth}\n'
        'cafile=/tmp/fieldlink-ca.crt\n'
        'audit=false\nfund=false\n'
    )

    run = {
        'schema': 'fieldkest.ci-run/v1',
        'run_id': 'BLD-611',
        'job': 'package-check',
        'state': 'success',
        'started_at': '2026-09-18T10:14:22Z',
        'finished_at': '2026-09-18T10:14:52Z',
        'retained_artifacts': [
            {
                'name': 'package-workspace.npmrc',
                'url': '/api/runs/BLD-611/artifacts/package-workspace.npmrc',
            }
        ],
    }
    artifact = {
        'schema': 'fieldkest.ci-artifact/v1',
        'artifact_id': 'WORKSPACE-BLD-611-NPMRC',
        'run_id': 'BLD-611',
        'file': 'package-workspace/.npmrc',
        'content': npmrc_content,
    }
    run_log = (
        'Started by user svc-fieldlink-ci\n'
        'Running package-check for @keplerops/fieldlink-connector@7.4.2 and @keplerops/support-rehearsal@1.3.1\n'
        'Archiving artifacts: package-workspace/**\n'
        'Retained artifact: package-workspace.npmrc\n'
        'Finished: SUCCESS\n'
    )

    import os as _os
    import tarfile as _tarfile

    # fieldkest-ci uid/gid is 2100 (from ci.Dockerfile groupadd/useradd)
    CI_UID = CI_GID = 2100

    VOLUME_RUNS.mkdir(parents=True, exist_ok=True)
    VOLUME_ARTIFACTS.mkdir(parents=True, exist_ok=True)
    art_dir = VOLUME_ARTIFACTS / 'BLD-611'
    art_dir.mkdir(mode=0o750, exist_ok=True)
    art_dir.chmod(0o750)
    import os as _os
    _os.chown(str(art_dir), CI_UID, CI_GID)

    run_path = VOLUME_RUNS / 'BLD-611.json'
    run_path.write_text(json.dumps(run, sort_keys=True, separators=(',', ':')) + '\n')
    run_path.chmod(0o640)
    _os.chown(str(run_path), CI_UID, CI_GID)

    log_path = VOLUME_RUNS / 'BLD-611.log'
    log_path.write_text(run_log)
    log_path.chmod(0o640)
    _os.chown(str(log_path), CI_UID, CI_GID)

    art_path = art_dir / 'package-workspace.npmrc'
    art_path.write_text(json.dumps(artifact, sort_keys=True, separators=(',', ':')) + '\n')
    art_path.chmod(0o640)
    _os.chown(str(art_path), CI_UID, CI_GID)

    # Ensure BLD-1842 (from image layer) is in the volume in case it was
    # pre-populated before docker compose up could copy the image content.
    ci_state_tar = operator.parent.parent / 'assets/keplerops/opening/k-ci-state.tar'
    if ci_state_tar.is_file() and not (VOLUME_RUNS / 'BLD-1842.json').exists():
        with _tarfile.open(str(ci_state_tar)) as tf:
            for member in ('runs/BLD-1842.json', 'runs/BLD-1842.log'):
                f = tf.extractfile(member)
                if f:
                    dest = VOLUME_RUNS / Path(member).name
                    dest.write_bytes(f.read())
                    dest.chmod(0o640)
                    _os.chown(str(dest), CI_UID, CI_GID)

    marker.touch(mode=0o600)
    print('K06 CI artifact seeded: BLD-611 run and package-workspace.npmrc artifact.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--operator-dir', type=Path, required=True)
    seed(parser.parse_args().operator_dir)
