"""Check native workplace bootstrap persistence and initial authority."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'native-workplace/prepare.py'
SPEC = importlib.util.spec_from_file_location('workplace_prepare', SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WorkplacePrepareTests(unittest.TestCase):
    def test_repeat_preserves_private_credentials_and_bounded_native_user(self):
        with tempfile.TemporaryDirectory() as temporary:
            operator = Path(temporary)
            (operator / 'range-seed').mkdir()
            (operator / 'range-seed/runtime-credentials.json').write_text(json.dumps({
                'credentials': {'developer_token': 'local-test-developer-password'},
            }))
            MODULE.prepare(operator)
            target = operator / 'native-workplace'
            first = (target / 'bootstrap.json').read_bytes()
            MODULE.prepare(operator)
            self.assertEqual(first, (target / 'bootstrap.json').read_bytes())
            self.assertEqual((target / 'bootstrap.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)
            realm = json.loads((target / 'realm.json').read_text())
            self.assertEqual(realm['users'][0]['realmRoles'], ['developer'])
            self.assertFalse(realm['clients'][0]['serviceAccountsEnabled'])
            self.assertFalse(realm['clients'][0]['directAccessGrantsEnabled'])
