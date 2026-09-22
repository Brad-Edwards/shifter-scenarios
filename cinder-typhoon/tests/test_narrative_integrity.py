"""Targeted corruption checks for retained correspondence and source artifacts."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import yaml
import validate_narrative as validator


class NarrativeIntegrityTests(unittest.TestCase):
    def test_rejects_corrupted_content(self):
        def alter_attachment(root):
            p = root / 'generated/messages/k-workshop-1.eml'
            p.write_bytes(p.read_bytes().replace(b'Content-Disposition: attachment', b'Content-Disposition: inline'))

        def add_unrelated_mailbox_copy(root):
            p = root / 'generated/packages/keplerops-mail.json'
            data = json.loads(p.read_text())
            coverage = json.loads((root / 'story-coverage.json').read_text())
            private = coverage['messages']['k-lunch-2']['message_id']
            self.assertNotIn(private, data['mailboxes']['rowan.ito@keplerops.com']['folders']['INBOX'])
            data['mailboxes']['rowan.ito@keplerops.com']['folders']['INBOX'].append(private)
            p.write_text(json.dumps(data))
            # Rebind the catalog to the mutated bytes, so the audience check must fail.
            import hashlib
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            catalog_path = root / 'artifact-catalog.json'
            catalog = json.loads(catalog_path.read_text())
            for entry in catalog['artifacts']:
                if entry['content_ref'] == 'narrative-keplerops.mail':
                    entry['sha256'] = digest
                    entry['source']['version'] = 'sha256-' + digest
            catalog_path.write_text(json.dumps(catalog))

        def change_source(root):
            p = root / 'generated/packages/arwc-documents.json'
            p.write_bytes(p.read_bytes() + b' ')

        def detach_reply(root):
            p = root / 'generated/messages/k-bike-3.eml'
            p.write_bytes(p.read_bytes().replace(b'In-Reply-To:', b'X-Previous-Message:'))

        def create_reporting_loop(root):
            p = root / 'authoring/workforce.yaml'
            workforce = yaml.safe_load(p.read_text())
            head = next(person for person in workforce['employees'] if person['key'] == 'leah')
            head['manager'] = 'rowan'
            p.write_text(yaml.safe_dump(workforce, sort_keys=False))

        def alter_accepted_delivery_amount(root):
            p = root / 'authoring/business-network.yaml'
            network = yaml.safe_load(p.read_text())
            merewick = next(org for org in network['organizations'] if org['key'] == 'merewick')
            merewick['settled_activity'][0]['accepted_amount_usd'] = '552.01'
            p.write_text(yaml.safe_dump(network, sort_keys=False))

        def bridge_support_visibility_threads(root):
            p = root / 'authoring/support-intake.yaml'
            support = yaml.safe_load(p.read_text())
            case = support['cases'][0]
            case['threads']['internal']['last'] = case['threads']['customer_visible']['last']
            p.write_text(yaml.safe_dump(support, sort_keys=False))

        def fabricate_engineering_resolution(root):
            p = root / 'authoring/support-intake.yaml'
            support = yaml.safe_load(p.read_text())
            case = next(c for c in support['cases'] if c['category'] == 'engineering_escalation')
            case['outcome'] = 'Engineering fixed the behavior and released it to the customer.'
            p.write_text(yaml.safe_dump(support, sort_keys=False))

        def change_private_package_access(root, public):
            import hashlib
            path = root / 'generated/packages/arwc-documents.json'
            data = json.loads(path.read_text())
            draft = next(d for d in data['documents'] if d['name']=='fg-publication-01-p1')
            draft['readers'] = []
            if public:
                draft['access'] = 'public'
                draft['document_state'] = 'published'
            path.write_text(json.dumps(data))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            catalog_path = root / 'artifact-catalog.json'
            catalog = json.loads(catalog_path.read_text())
            for entry in catalog['artifacts']:
                if entry['content_ref'] == 'narrative-arwc.documents':
                    entry['sha256'] = digest
                    entry['source']['version'] = 'sha256-' + digest
            catalog_path.write_text(json.dumps(catalog))

        def publish_private_draft(root):
            change_private_package_access(root, True)

        def empty_private_readers(root):
            change_private_package_access(root, False)

        for mutate in (alter_attachment, add_unrelated_mailbox_copy, change_source,
                       detach_reply, create_reporting_loop, alter_accepted_delivery_amount,
                       bridge_support_visibility_threads, fabricate_engineering_resolution,
                       publish_private_draft, empty_private_readers):
            with self.subTest(mutation=mutate.__name__), tempfile.TemporaryDirectory() as temp:
                pack = Path(temp)
                root = pack / 'assets/narrative'
                shutil.copytree(validator.ROOT, root)
                shutil.copytree(validator.PACK / 'sdl', pack / 'sdl')
                review = pack / 'docs/narrative'
                review.mkdir(parents=True)
                shutil.copy(validator.PACK / 'docs/narrative/content-ownership.json', review)
                mutate(root)
                with patch.object(validator, 'ROOT', root), patch.object(validator, 'PACK', pack):
                    with self.assertRaises(ValueError):
                        validator.check_assets()


class ITServiceIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        author = validator.ROOT / 'authoring'
        cls.roster = yaml.safe_load((author / 'workforce.yaml').read_text())['employees']
        cls.identity = yaml.safe_load((author / 'people.yaml').read_text())
        cls.mail = yaml.safe_load((author / 'mail-it-services.yaml').read_text())['messages']
        cls.docs = (yaml.safe_load((author / 'documents.yaml').read_text())['documents'] +
                    yaml.safe_load((author / 'documents-it-services.yaml').read_text())['documents'])
        cls.events = yaml.safe_load((author / 'calendars-governance.yaml').read_text())['events']

    def test_it_records_reconcile(self):
        self.assertEqual(validator.check_it_services(validator.ROOT, self.roster, self.identity,
                                                     self.mail, self.docs, self.events)['cases'], 480)

    def test_it_private_case_rejects_unrelated_reader(self):
        docs = deepcopy(self.docs)
        next(d for d in docs if d['id'] == 'it-case-0301')['reader_keys'].append('rosa')
        with self.assertRaisesRegex(ValueError, 'case readers'):
            validator.check_it_services(validator.ROOT, self.roster, self.identity,
                                        self.mail, docs, self.events)

    def test_it_reply_cannot_precede_approval(self):
        mail = deepcopy(self.mail)
        next(m for m in mail if m['id'] == 'it-0903')['date'] = '2026-06-01T08:00:00-04:00'
        with self.assertRaisesRegex(ValueError, 'chronology'):
            validator.check_it_services(validator.ROOT, self.roster, self.identity,
                                        mail, self.docs, self.events)

    def test_it_deferred_change_has_no_window(self):
        events = deepcopy(self.events)
        fake = deepcopy(next(e for e in events if e['id'].startswith('it-window-')))
        fake['id'] = 'it-window-01'
        events.append(fake)
        with self.assertRaisesRegex(ValueError, 'calendar count|change calendar'):
            validator.check_it_services(validator.ROOT, self.roster, self.identity,
                                        self.mail, self.docs, events)


if __name__ == '__main__':
    unittest.main()
