"""Check the narrow native self-account role upgrade boundary."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'native-workplace/apply-account-defaults.py'
SPEC = importlib.util.spec_from_file_location('account_defaults', SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AccountDefaultsTests(unittest.TestCase):
    def test_only_missing_default_role_is_added_and_repeat_does_not_mutate(self):
        role = {'id': 'native-role', 'name': 'default-roles-keplerops'}
        mappings = []
        writes = []
        def api(method, path, value=None):
            if method == 'POST':
                writes.append((method, path, value))
                mappings.extend(value)
            elif path.endswith('/roles/default-roles-keplerops'):
                return role
            elif '/users?' in path:
                return [{'id': 'native-rowan'}]
            else:
                return list(mappings)
        with patch.object(MODULE, 'api', side_effect=api):
            MODULE.repair()
            MODULE.repair()
        self.assertEqual(writes, [('POST', '/admin/realms/keplerops/users/native-rowan/role-mappings/realm', [role])])
