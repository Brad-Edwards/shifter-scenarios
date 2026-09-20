"""Adversarial checks for customer closure and workshop continuity."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
import yaml

from validate_customer_followup import check_customer_followup, sha

PACK = Path(__file__).resolve().parents[1]
ROOT = PACK / 'assets/narrative'
AUTHOR = ROOT / 'authoring'


class CustomerFollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def load(path):
            return yaml.safe_load(path.read_text())
        cls.identity = load(AUTHOR / 'people.yaml')
        cls.roster = load(AUTHOR / 'workforce.yaml')['employees']
        cls.mail = [m for p in AUTHOR.glob('mail-*.yaml') for m in load(p)['messages']]
        cls.docs = [d for p in AUTHOR.glob('documents*.yaml') for d in load(p)['documents']]
        cls.calendars = [e for p in AUTHOR.glob('calendars*.yaml') for e in load(p)['events']]
        cls.manifest = load(AUTHOR / 'customer-followup.yaml')

    def test_shipped_followup(self):
        result = check_customer_followup(ROOT, self.identity, self.roster,
                                         self.mail, self.docs, self.calendars)
        self.assertEqual(result['existing_cases_updated'], 230)

    def test_rejects_false_closures_and_visibility(self):
        def no_customer_verification(manifest, mail, docs, calendars):
            next(r for r in manifest['records'] if r['status'] == 'closed_verified')['verified_at'] = None

        def delivery_before_authorization(manifest, mail, docs, calendars):
            record = next(r for r in manifest['records'] if r['status'] == 'closed_verified')
            record['authorized_at'] = record['last_activity']

        def unrelated_release(manifest, mail, docs, calendars):
            record = next(r for r in manifest['records'] if r['status'] == 'closed_verified')
            record['release_id'] = next(k['id'] for k in manifest['releases'] if k['id'] != record['release_id'])

        def unrelated_previous_decision(manifest, mail, docs, calendars):
            manifest['engineering_resolutions'][0]['previous_quality_records'][-1] = 'PQ-2026-0001'

        def private_thread_to_customer(manifest, mail, docs, calendars):
            record = manifest['records'][0]
            first = record['threads']['customer_visible']['added'][0]
            next(m for m in mail if m['id'] == first)['reply_to'] = record['threads']['internal']['previous_last']

        def private_attachment_to_customer(manifest, mail, docs, calendars):
            mid = manifest['workshop']['threads']['customer_visible']['added'][0]
            next(m for m in mail if m['id'] == mid)['attachments'] = ['rillhaven-workshop-preparation']

        def earlier_article_changed(manifest, mail, docs, calendars):
            key = manifest['knowledge'][0]['previous_document']
            next(d for d in docs if d['id'] == key)['text'] += '\nNew wording in an old attachment.\n'

        def premature_acceptance(manifest, mail, docs, calendars):
            manifest['engineering_resolutions'][0]['accepted_at'] = '2026-01-01T09:00:00-04:00'

        def false_test_result(manifest, mail, docs, calendars):
            fix = manifest['engineering_resolutions'][0]
            fix['fixture_rows'][0]['observed'] = 'wrong result'
            import csv
            import io
            stream = io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=list(fix['fixture_rows'][0]), lineterminator='\n')
            writer.writeheader(); writer.writerows(fix['fixture_rows'])
            next(d for d in docs if d['id'] == fix['id'].lower() + '-fixtures')['text'] = stream.getvalue()
            fix['fixture_sha256'] = sha(stream.getvalue())

        def completed_future_session(manifest, mail, docs, calendars):
            next(r for r in manifest['records'] if r['kind'] == 'planned_work')['work_occurred_at'] = '2026-09-15T10:00:00-04:00'

        def workshop_finished(manifest, mail, docs, calendars):
            manifest['workshop']['status'] = 'completed'

        def missing_parent(manifest, mail, docs, calendars):
            next(r for r in manifest['records'] if r['kind'] == 'child_followup')['parent_case'] = 'SUP-2026-9999'

        def rewrite_case_history(manifest, mail, docs, calendars):
            record = manifest['records'][0]
            doc = next(d for d in docs if d['id'] == record['case_document'])
            doc['text'] += '\nA later sentence inserted into the retained history.\n'

        def premature_notice(manifest, mail, docs, calendars):
            record = next(r for r in manifest['records'] if r['status'] == 'closed_support')
            record['closed_at'] = record['last_activity']
            doc = next(d for d in docs if d['id'] == record['case_document'])
            import re
            doc['text'] = re.sub(r'\*\*Closed:\*\* [^\n]+', '**Closed:** ' + record['closed_at'], doc['text'])

        mutations = [no_customer_verification, delivery_before_authorization, unrelated_release,
                     unrelated_previous_decision, private_thread_to_customer, private_attachment_to_customer,
                     earlier_article_changed, premature_acceptance, false_test_result,
                     completed_future_session, workshop_finished, missing_parent,
                     rewrite_case_history, premature_notice]
        for mutate in mutations:
            with self.subTest(mutation=mutate.__name__), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / 'authoring').mkdir()
                (root / 'generated/calendars').mkdir(parents=True)
                shutil.copy(ROOT / 'generated/calendars/rillhaven-workshop.ics', root / 'generated/calendars')
                for filename in ('support-intake.yaml', 'product-quality.yaml', 'business-network.yaml'):
                    shutil.copy(AUTHOR / filename, root / 'authoring')
                manifest, mail, docs, calendars = copy.deepcopy((self.manifest, self.mail, self.docs, self.calendars))
                mutate(manifest, mail, docs, calendars)
                (root / 'authoring/customer-followup.yaml').write_text(yaml.safe_dump(manifest, sort_keys=False))
                with self.assertRaises(ValueError):
                    check_customer_followup(root, self.identity, self.roster, mail, docs, calendars)


if __name__ == '__main__':
    unittest.main()
