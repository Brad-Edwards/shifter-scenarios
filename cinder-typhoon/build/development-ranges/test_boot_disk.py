"""Exercise development provisioning without cloud writes."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
FAKE_CLOUD = '''#!/bin/bash
set -eu
printf '%s\\n' "$*" >>"$CALLS"
case "$*" in
  'auth list '*) echo bedwards@paloaltonetworks.com ;;
  *'--format=value(labels.purpose)'*) echo "${PURPOSE:-development-range}" ;;
  *'--format=value(labels.segment)'*) echo "$SEGMENT" ;;
  *'--format=value(serviceAccounts[0].email)'*) ;;
  *'--format=value(disks[0].source.basename())'*) echo "${BOOT_DISK:-cinder-fieldlink-dev}" ;;
  'compute disks describe '*) echo "${DISK_SIZE:-80}" ;;
  'compute disks resize '*) ;;
  'compute instances describe '*) ;;
  'compute ssh '*) ;;
  *) exit 92 ;;
esac
'''


class BootDiskTests(unittest.TestCase):
    def provision(self, *, target='fieldlink', **values):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            cloud = path / 'gcloud'
            cloud.write_text(FAKE_CLOUD)
            cloud.chmod(0o700)
            calls = path / 'calls'
            result = subprocess.run(
                ['bash', str(ROOT / 'manage.sh'), 'provision', target, 'prod-mgau4w'],
                env=dict(os.environ, GCLOUD_BIN=str(cloud), CALLS=str(calls),
                         SEGMENT=target, **values), capture_output=True, text=True,
            )
            return result, calls.read_text().splitlines()

    def test_grows_only_small_verified_development_boot_disk(self):
        result, calls = self.provision()
        self.assertEqual(result.returncode, 0, result.stderr)
        writes = [call for call in calls if call.startswith('compute disks resize ')]
        self.assertEqual(writes, ['compute disks resize cinder-fieldlink-dev '
                                 '--project=prod-mgau4w --zone=us-central1-a --size=100GB --quiet'])

    def test_keeps_sufficient_disks_and_arwc_unchanged(self):
        for values in ({'DISK_SIZE': '100'}, {'DISK_SIZE': '120'}, {'target': 'arwc'}):
            with self.subTest(values=values):
                result, calls = self.provision(**values)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(any(call.startswith('compute disks resize ') for call in calls))

    def test_rejects_foreign_disk_unmanaged_vm_and_invalid_size(self):
        for values in ({'BOOT_DISK': 'cinder-keplerops-golden'},
                       {'PURPOSE': 'golden'}, {'DISK_SIZE': 'invalid'}):
            with self.subTest(values=values):
                result, calls = self.provision(**values)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(call.startswith('compute disks resize ') for call in calls))


if __name__ == '__main__':
    unittest.main()
