"""Focused recovery and persistence checks for the native Gitea importer."""

from __future__ import annotations

import importlib.util
import base64
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
    def test_engineering_note_import_retries_without_overwriting_completed_native_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'data').mkdir()
            note = root / 'engineering-note.md'
            note.write_text('# Retained engineering record\n')
            with patch.object(SEED, 'ROOT', root), patch.object(SEED, 'ENGINEERING_NOTE', note):
                with patch.object(SEED, 'exists', return_value=False), patch.object(SEED, 'api') as api:
                    api.side_effect = RuntimeError('interrupted native import')
                    with self.assertRaises(RuntimeError):
                        SEED.engineering_note('bootstrap-test')
                    self.assertFalse((root / 'data/.connector-engineering-note-seeded').exists())
                    api.reset_mock(side_effect=True)
                    api.return_value = {'content': base64.b64encode(b'# Archive\n').decode(), 'sha': 'native-readme-sha'}
                    SEED.engineering_note('bootstrap-test')
                    self.assertTrue((root / 'data/.connector-engineering-note-seeded').exists())
                    self.assertEqual([call.args[0] for call in api.call_args_list], ['POST', 'GET', 'PUT'])
                    api.reset_mock()
                    SEED.engineering_note('bootstrap-test')
                    api.assert_not_called()

    def test_delivery_history_retries_a_failed_push_then_preserves_native_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'data').mkdir()
            marker = root / 'data/.delivery-history-seeded'
            def fail_push(command, **options):
                if 'push' in command:
                    raise subprocess.CalledProcessError(1, ['git', 'push'])
            with patch.object(SEED, 'ROOT', root), patch.object(SEED, 'exists', return_value=False):
                with patch.object(SEED.subprocess, 'run', side_effect=fail_push):
                    with self.assertRaises(subprocess.CalledProcessError):
                        SEED.delivery_history('bootstrap-test')
                self.assertFalse(marker.exists())
                with patch.object(SEED.subprocess, 'run') as run:
                    SEED.delivery_history('bootstrap-test')
                    self.assertTrue(marker.exists())
                    self.assertTrue(any('push' in call.args[0] for call in run.call_args_list))
                    run.reset_mock()
                    SEED.delivery_history('bootstrap-test')
                    run.assert_not_called()

    def test_existing_delivery_branch_is_not_overwritten_after_interruption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'data').mkdir()
            with patch.object(SEED, 'ROOT', root), patch.object(SEED, 'exists', return_value=True):
                with patch.object(SEED.subprocess, 'run') as run:
                    SEED.delivery_history('bootstrap-test')
                    run.assert_not_called()
            self.assertTrue((root / 'data/.delivery-history-seeded').exists())

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
