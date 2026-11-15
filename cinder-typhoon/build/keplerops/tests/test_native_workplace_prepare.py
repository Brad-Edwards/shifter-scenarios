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
            ca_password_inode = (target / 'ca/secrets/password').stat().st_ino
            MODULE.prepare(operator)
            self.assertEqual(first, (target / 'bootstrap.json').read_bytes())
            self.assertEqual((target / 'bootstrap.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)
            self.assertEqual((target / 'ca/secrets/password').stat().st_ino, ca_password_inode)
            realm = json.loads((target / 'realm.json').read_text())
            self.assertEqual(realm['users'][0]['realmRoles'], ['default-roles-keplerops', 'developer'])
            self.assertFalse(realm['clients'][0]['serviceAccountsEnabled'])
            self.assertFalse(realm['clients'][0]['directAccessGrantsEnabled'])

    def test_ca_configuration_keeps_existing_native_provisioners_on_repeat(self):
        with tempfile.TemporaryDirectory() as temporary:
            operator = Path(temporary)
            target = operator / 'native-workplace'
            (target / 'ca/config').mkdir(parents=True)
            (operator / 'tls').mkdir()
            (operator / 'tls/ca.crt').write_text('public infrastructure CA fixture')
            (target / 'bootstrap.json').write_text(json.dumps({'enrollment_client': 'local-client-fixture'}))
            config = target / 'ca/config/ca.json'
            config.write_text(json.dumps({'authority': {'provisioners': [{'name': 'infrastructure', 'type': 'JWK'}]}}))
            MODULE.configure_ca(operator)
            MODULE.configure_ca(operator)
            values = json.loads(config.read_text())['authority']['provisioners']
            self.assertEqual([value['name'] for value in values], ['infrastructure', 'keplerops-staff'])
            self.assertEqual(values[1]['configurationEndpoint'],
                             'https://identity.keplerops.test/realms/keplerops/.well-known/openid-configuration')
