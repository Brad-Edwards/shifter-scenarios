"""Reject plausible but false release, recovery, and operating evidence."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import yaml

from validate_release_platform import check_release_platform

PACK = Path(__file__).resolve().parents[1]
AUTHOR = PACK / 'assets/narrative/authoring'


class ReleasePlatformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def load(name):
            return yaml.safe_load((AUTHOR / name).read_text())
        cls.identity = load('people.yaml')
        cls.roster = load('workforce.yaml')['employees']
        cls.mail = load('mail-release-platform.yaml')['messages']
        cls.docs = (load('documents-release-platform.yaml')['documents'] +
                    load('documents-product-quality.yaml')['documents'])
        cls.events = load('calendars-release-platform.yaml')['events']
        cls.manifest = load('release-platform.yaml')

    def test_shipped_records(self):
        counts = check_release_platform(PACK / 'assets/narrative', self.identity,
                                        self.roster, self.mail, self.docs, self.events)
        self.assertEqual(counts['histories'], 120)

    def test_rejects_false_evidence(self):
        def release_before_acceptance(manifest, docs, mail, events):
            manifest['records'][0]['opened_at'] = '2026-01-01T09:00:00-04:00'

        def use_deferred_quality_decision(manifest, docs, mail, events):
            manifest['records'][0]['quality_records'][0] = 'PQ-2026-0221'

        def publish_deferred_release(manifest, docs, mail, events):
            record = next(r for r in manifest['records'] if r['kind'] == 'release'
                          and r['status'] == 'deferred')
            record['published_at'] = record['closed_at']

        def change_selected_artifact(manifest, docs, mail, events):
            manifest['records'][0]['events'][-1]['sha256'] = '0' * 64
            # Keep the event file consistent; the check must compare against the manifest.
            record = manifest['records'][0]
            doc = next(d for d in docs if d['id'] == record['id'].lower() + '-events')
            doc['text'] = '\n'.join(json.dumps(e) for e in record['events']) + '\n'

        def fabricate_restore_digest(manifest, docs, mail, events):
            record = next(r for r in manifest['records'] if r['kind'] == 'backup')
            record['sample'][0]['sha256'] = '0' * 64
            doc = next(d for d in docs if d['id'] == record['id'].lower() + '-sample')
            sample = json.loads(doc['text'])
            sample['documents'] = record['sample']
            doc['text'] = json.dumps(sample)

        def overbook_capacity(manifest, docs, mail, events):
            record = next(r for r in manifest['records'] if r['kind'] == 'capacity')
            record['available_hours'] += 1

        def attachment_to_unrelated_reader(manifest, docs, mail, events):
            mail[0]['to'] = ['rosa']

        def confirm_cancelled_window(manifest, docs, mail, events):
            next(e for e in events if e['status'] == 'CANCELLED')['status'] = 'CONFIRMED'

        def invent_service(manifest, docs, mail, events):
            manifest['records'][0]['service_owner'] = 'k-cloud.made-up-server'

        def alter_machine_notice(manifest, docs, mail, events):
            notice = next(m for m in mail if m['from'] == 'k_recovery_updates'
                          and 'bytes=' in m['body'])
            import re
            notice['body'] = re.sub(r'bytes=\d+', 'bytes=1', notice['body'])

        for mutate in (release_before_acceptance, use_deferred_quality_decision,
                       publish_deferred_release, change_selected_artifact,
                       fabricate_restore_digest, overbook_capacity,
                       attachment_to_unrelated_reader, confirm_cancelled_window,
                       invent_service, alter_machine_notice):
            with self.subTest(mutation=mutate.__name__), tempfile.TemporaryDirectory() as temp:
                pack = Path(temp)
                root = pack / 'assets/narrative'
                (root / 'authoring').mkdir(parents=True)
                shutil.copytree(PACK / 'sdl/modules/world', pack / 'sdl/modules/world')
                shutil.copy(AUTHOR / 'product-quality.yaml', root / 'authoring')
                manifest, docs, mail, events = copy.deepcopy(
                    (self.manifest, self.docs, self.mail, self.events))
                mutate(manifest, docs, mail, events)
                (root / 'authoring/release-platform.yaml').write_text(
                    yaml.safe_dump(manifest, sort_keys=False))
                with self.assertRaises(ValueError):
                    check_release_platform(root, self.identity, self.roster, mail, docs, events)


if __name__ == '__main__':
    unittest.main()
