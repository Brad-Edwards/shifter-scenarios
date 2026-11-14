"""Focused recovery and persistence checks for the native Gitea importer."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


RUNTIME = Path(__file__).resolve().parents[1] / 'runtime'
SPEC = importlib.util.spec_from_file_location('seed_gitea', RUNTIME / 'seed-gitea.py')
assert SPEC is not None and SPEC.loader is not None
SEED = importlib.util.module_from_spec(SPEC)
with patch.dict(sys.modules, {'credentials': types.SimpleNamespace(credential=lambda _: 'test-password')}):
    with patch('ssl.create_default_context'):
        SPEC.loader.exec_module(SEED)


class NativeSourceSeedTests(unittest.TestCase):
    def test_failed_push_retries_then_preserves_participant_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'data').mkdir()
            (root / 'handovers').mkdir()
            (root / 'handovers/HND-FLK-2026-09.json').write_text(json.dumps({
                'release': 'FLK-7.4.2', 'revision': 12, 'owner': 'Rowan Ito', 'notes': [],
            }))
            with patch.object(SEED, 'ROOT', root), patch.object(SEED, 'REPOSITORIES', {'project': 'Project'}):
                with patch.object(SEED, 'exists', return_value=True), patch.object(SEED, 'api') as api:
                    with patch.object(SEED.subprocess, 'check_output', return_value='fieldlink-bootstrap'):
                        with patch.object(SEED.subprocess, 'run') as run:
                            run.side_effect = [None, subprocess.CalledProcessError(1, ['git', 'push'])]
                            with self.assertRaises(subprocess.CalledProcessError):
                                SEED.main()
                            self.assertFalse((root / 'data/.seeded-project').exists())
                            run.reset_mock(side_effect=True)
                            SEED.main()
                            self.assertTrue((root / 'data/.seeded-project').exists())
                            self.assertEqual(run.call_count, 2)
                            api.assert_any_call('PUT', '/repos/fieldkest/project/collaborators/rowan.ito',
                                                (root / 'data/.bootstrap-password').read_text(), {'permission': 'read'})
                            run.reset_mock()
                            SEED.main()
                            run.assert_not_called()

    def test_product_secrets_survive_configuration_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'data').mkdir()
            template = RUNTIME.parent / 'config/gitea-app.ini'
            with patch.object(SEED, 'ROOT', root), patch.object(SEED, 'CONFIG', root / 'data/app.ini'):
                SEED.configure(template)
                first = (root / 'data/app.ini').read_text()
                SEED.configure(template)
                self.assertEqual(first, (root / 'data/app.ini').read_text())
                self.assertTrue(first.startswith('APP_NAME = FieldKest Source'))
                self.assertIn('START_SSH_SERVER = true', first)
                self.assertEqual((root / 'data/.native-secrets.json').stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
