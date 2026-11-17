"""Focused cloud-wrapper failure checks; no cloud or product test actions."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(os.environ.get("ARWC_BACKUP_SCRIPT", Path(__file__).with_name("golden-vm.sh")))
IMAGE = "cinder-arwc-ot-backup-check"
CLONE = "cinder-arwc-ot-restore-check"
SOURCE = "projects/prod-mgau4w/zones/us-central1-a/instances/cinder-arwc-ot-compat-363"
FAKE = r'''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['CLOUD_CALLS'], 'a') as f: f.write(json.dumps(args) + '\n')
args = [a for a in args if not a.startswith(('--project=', '--account='))]
if args[:3] == ['config', 'get-value', 'account']:
    print('bedwards@paloaltonetworks.com')
elif args[:3] == ['compute', 'machine-images', 'list']:
    print(os.environ.get('EXISTING_IMAGE', ''))
elif args[:3] == ['compute', 'instances', 'list']:
    print(os.environ.get('EXISTING_VM', ''))
elif args[:3] == ['compute', 'instances', 'describe']:
    print(os.environ.get('SOURCE_STATUS', 'RUNNING'))
elif args[:3] == ['compute', 'machine-images', 'create']:
    sys.exit(int(os.environ.get('CAPTURE_EXIT', '0')))
elif args[:3] == ['compute', 'machine-images', 'get-iam-policy']:
    print(json.dumps({'bindings': [{'members': ['allUsers']}]} if os.environ.get('PUBLIC_IMAGE') else {}))
elif args[:3] == ['compute', 'machine-images', 'describe']:
    if '--format=value(status)' in args:
        print('READY')
    else:
        print(json.dumps({'status': 'READY', 'sourceInstance': os.environ.get('IMAGE_SOURCE',
          'projects/prod-mgau4w/zones/us-central1-a/instances/cinder-arwc-ot-compat-363')}))
elif args[:2] != ['compute', 'instances'] or args[2] not in ('start', 'stop', 'create'):
    sys.exit('Unexpected cloud command')
'''


class BackupGuards(unittest.TestCase):
    def run_script(self, *arguments, **settings):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "gcloud"
            fake.write_text(FAKE)
            fake.chmod(0o700)
            calls = root / "calls.jsonl"
            environment = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
                               CLOUD_CALLS=str(calls), **settings)
            result = subprocess.run(["bash", str(SCRIPT), *arguments], env=environment,
                                    text=True, capture_output=True, timeout=20)
            recorded = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
            return result, recorded

    def commands(self, calls, verb):
        return [c for c in calls if "compute" in c and verb in c]

    def test_wrong_project_rejected_before_cloud_access(self):
        result, calls = self.run_script("backup", "other-project", IMAGE)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_source_name_cannot_be_restore_destination(self):
        result, calls = self.run_script("restore", "prod-mgau4w", IMAGE, "cinder-arwc-ot-compat-363")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_capture_failure_restarts_running_source(self):
        result, calls = self.run_script("backup", "prod-mgau4w", IMAGE, CAPTURE_EXIT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.commands(calls, "stop")), 1)
        self.assertEqual(len(self.commands(calls, "start")), 1)

    def test_stopped_source_is_not_started(self):
        result, calls = self.run_script("backup", "prod-mgau4w", IMAGE, SOURCE_STATUS="TERMINATED")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.commands(calls, "start"), [])
        self.assertEqual(self.commands(calls, "stop"), [])

    def test_existing_backup_is_not_replaced(self):
        result, calls = self.run_script("backup", "prod-mgau4w", IMAGE, EXISTING_IMAGE=IMAGE)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.commands(calls, "create"), [])
        self.assertEqual(self.commands(calls, "stop"), [])

    def test_public_backup_cannot_be_restored(self):
        result, calls = self.run_script("restore", "prod-mgau4w", IMAGE, CLONE, PUBLIC_IMAGE="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.commands(calls, "create"), [])

    def test_wrong_source_backup_cannot_be_restored(self):
        result, calls = self.run_script("restore", "prod-mgau4w", IMAGE, CLONE, IMAGE_SOURCE=SOURCE + "-other")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.commands(calls, "create"), [])

    def test_existing_restore_is_not_replaced(self):
        result, calls = self.run_script("restore", "prod-mgau4w", IMAGE, CLONE, EXISTING_VM=CLONE)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.commands(calls, "create"), [])

    def test_restore_has_no_public_address_or_cloud_identity(self):
        result, calls = self.run_script("restore", "prod-mgau4w", IMAGE, CLONE)
        self.assertEqual(result.returncode, 0, result.stderr)
        create, = self.commands(calls, "create")
        self.assertIn("--network-interface=subnet=cinder-arwc-carrier,no-address", create)
        self.assertIn("--no-service-account", create)
        self.assertIn("--no-scopes", create)
        self.assertEqual(self.commands(calls, "stop"), [])


if __name__ == "__main__":
    unittest.main()
