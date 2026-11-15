"""Every mounted product volume belongs in backup, including legacy CA data."""
import importlib.util
import json
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'build/keplerops/native-platform/backup-volumes.py'
spec = importlib.util.spec_from_file_location('fieldlink_backup_volumes', SOURCE)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class BackupVolumeTests(unittest.TestCase):
    def test_unlabelled_declared_ca_mount_is_included_with_owned_legacy_volume(self):
        prefix = backup.PROJECT + '-'
        def run(arguments):
            if arguments[1:3] == ['compose', 'config']:
                self.assertIn('--no-env-resolution', arguments)
                return json.dumps({'name': backup.PROJECT, 'volumes': {
                    'ca': {'name': prefix + 'native-ca-data'},
                    'postgres': {'name': prefix + 'native-postgres-data'}}})
            if arguments[1:3] == ['volume', 'ls']:
                names = [prefix + 'native-postgres-data', prefix + 'legacy-data']
                if '--filter' not in arguments:
                    names += [prefix + 'native-ca-data', 'foreign-product-data']
                return '\n'.join(names)
            if arguments[1:3] == ['compose', 'ps']:
                return 'native-ca-container\n'
            if arguments[1] == 'inspect':
                return json.dumps({'labels': {'com.docker.compose.project': backup.PROJECT},
                                   'mounts': [{'Type': 'volume', 'Name': prefix + 'native-ca-data'}]})
            raise AssertionError(arguments)
        self.assertEqual(backup.inventory(run), [prefix + 'legacy-data', prefix + 'native-ca-data', prefix + 'native-postgres-data'])

    def test_undeclared_or_foreign_mounted_volume_refuses_incomplete_backup(self):
        for name in ('foreign-data', backup.PROJECT + '-undeclared'):
            with self.subTest(name=name):
                def run(arguments):
                    if arguments[1:3] == ['compose', 'config']:
                        return json.dumps({'name': backup.PROJECT, 'volumes': {'ca': {'name': backup.PROJECT + '-native-ca-data'}}})
                    if arguments[1:3] == ['compose', 'ps']:
                        return 'native-container'
                    if arguments[1:3] == ['volume', 'ls']:
                        return name
                    if arguments[1] == 'inspect':
                        return json.dumps({'labels': {'com.docker.compose.project': backup.PROJECT}, 'mounts': [{'Type': 'volume', 'Name': name}]})
                    raise AssertionError(arguments)
                with self.assertRaises(ValueError):
                    backup.inventory(run)


if __name__ == '__main__':
    unittest.main()
