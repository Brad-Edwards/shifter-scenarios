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
