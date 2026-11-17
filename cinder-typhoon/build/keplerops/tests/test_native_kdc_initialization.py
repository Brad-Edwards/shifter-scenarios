"""Check the retained KDC boundary without running participant protocols."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'native-workplace/initialize-kdc.py'
SPEC = importlib.util.spec_from_file_location('initialize_kdc', SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NativeKdcInitializationTests(unittest.TestCase):
    def test_retained_database_is_not_reprovisioned_or_read_as_bootstrap_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / 'krb5kdc').mkdir()
            principal = state / 'krb5kdc/principal'
            principal.write_bytes(b'existing-native-database-fixture')
            with patch.object(MODULE, 'STATE', state), patch.object(MODULE, 'INPUT', state / 'absent-input'):
                with patch.object(MODULE, 'run') as run:
                    MODULE.initialize()
                    run.assert_not_called()
            self.assertEqual(principal.read_bytes(), b'existing-native-database-fixture')

    def test_incomplete_unowned_state_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / 'krb5kdc').mkdir()
            (state / 'krb5kdc/unexpected-state').touch()
            with patch.object(MODULE, 'STATE', state):
                with self.assertRaisesRegex(RuntimeError, 'refusing to overwrite'):
                    MODULE.initialize()
