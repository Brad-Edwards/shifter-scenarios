"""Native platform setup preserves existing private and user-managed state."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'build/keplerops/native-platform/prepare.py'
spec = importlib.util.spec_from_file_location('native_platform_prepare', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativePlatformTests(unittest.TestCase):
    def test_retained_kdc_adds_missing_user_without_rotating_existing_identity(self) -> None:
        source = ROOT / 'build/keplerops/native-workplace/initialize-kdc.py'
        kdc_spec = importlib.util.spec_from_file_location('kdc_initialize', source)
        kdc = importlib.util.module_from_spec(kdc_spec)
        kdc_spec.loader.exec_module(kdc)
        existing = {'evan.calderoux@KEPLEROPS.TEST', 'HTTP/staff.keplerops.test@KEPLEROPS.TEST'}
        calls = []
        def run(arguments, data=''):
            calls.append((arguments, data))
            existing.add('rowan.ito@KEPLEROPS.TEST')
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            (state / 'krb5kdc').mkdir()
            (state / 'krb5kdc/principal').touch()
            (state / '.native-initialization-complete').touch()
            inputs = state / 'inputs.json'
            inputs.write_text(json.dumps({'users': {'rowan.ito': 'private-new', 'evan.calderoux': 'private-existing'}}))
            with patch.object(kdc, 'STATE', state), patch.object(kdc, 'INPUT', inputs), patch.object(kdc, 'run', run), patch.object(kdc.subprocess, 'check_output', side_effect=lambda *a, **kw: '\n'.join(existing)):
                kdc.initialize()
                kdc.initialize()
        self.assertEqual(len(calls), 1)
        arguments, data = calls[0]
        self.assertEqual(arguments[-1], 'addprinc rowan.ito@KEPLEROPS.TEST')
        self.assertNotIn('private-new', ' '.join(arguments))
        self.assertEqual(data, 'private-new\nprivate-new\n')

    def test_interrupted_assistant_setup_completes_membership_without_reset(self) -> None:
        source = ROOT / 'build/keplerops/native-platform/seed-assistant.py'
        assistant_spec = importlib.util.spec_from_file_location('assistant_seed', source)
        assistant = importlib.util.module_from_spec(assistant_spec)
        assistant_spec.loader.exec_module(assistant)
        updates = []
        def native_api(path, data=None, token=None):
            responses = {
                '/system/multi-user-mode': {'multiUserMode': True},
                '/request-token': {'token': 'setup-token'},
                '/system/update-env': {},
                '/admin/users': {'users': [{'username': name, 'id': index} for index, name in enumerate(('rowan.ito', 'maya.ranscombe', 'talia.mornac'), 1)]},
                '/workspaces': {'workspaces': [{'id': 4, 'name': 'FieldLink Operations', 'slug': 'fieldlink-operations'}]},
                '/admin/workspaces/4/users': {'users': [{'userId': 1}, {'userId': 9}]},
            }
            if path.endswith('/update-users'):
                updates.append(data['userIds'])
                return {'success': True}
            return responses[path]
        with tempfile.TemporaryDirectory() as directory, patch.object(assistant, 'api', native_api):
            operator = Path(directory)
            for name, value in (
                ('native-platform/bootstrap.json', {'assistant_admin': 'private'}),
                ('native-workplace/bootstrap.json', {'staff_maya': 'private', 'staff_talia': 'private'}),
                ('range-seed/runtime-credentials.json', {'credentials': {'developer_token': 'private'}}),
            ):
                path = operator / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            documents = operator / 'native-platform/assistant-documents'
            documents.mkdir()
            for name in ('company-history.md', 'working-guide.md', 'customer-relationships.md'):
                (documents / name).touch()
            assistant.seed(operator)
            self.assertEqual(updates, [[1, 2, 3, 9]])
            with patch.object(assistant, 'api', side_effect=AssertionError('completed state was reseeded')):
                assistant.seed(operator)

    def test_warm_prepare_preserves_private_inputs_and_native_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(module.os, 'chown'):
            operator = Path(directory)
            (operator / 'range-seed').mkdir()
            (operator / 'range-seed/runtime-credentials.json').write_text(json.dumps({'credentials': {'assistant_tool_session': 'test-service-token'}}))
            previous_umask = os.umask(0o077)
            try:
                module.prepare(operator)
            finally:
                os.umask(previous_umask)
            target = operator / 'native-platform'
            original = (target / 'bootstrap.json').read_bytes()
            environment = target / 'anythingllm.env'
            environment.write_text('native application changed its own settings\n')
            module.prepare(operator)
            self.assertEqual((target / 'bootstrap.json').read_bytes(), original)
            self.assertEqual(environment.read_text(), 'native application changed its own settings\n')
            self.assertEqual((target / 's3.json').stat().st_mode & 0o777, 0o444)
            identities = json.loads((target / 's3.json').read_text())['identities']
            developer = next(value for value in identities if value['name'] == 'rowan.ito')
            self.assertNotIn('Admin', developer['actions'])
            self.assertTrue(all(value.endswith(':fieldlink-exports') for value in developer['actions']))
            self.assertEqual((target / 'bootstrap.json').stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
