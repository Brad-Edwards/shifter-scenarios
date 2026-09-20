"""Adversarial tests for agreed commercial terms and customer visibility."""
import copy
import csv
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import yaml

from validate_commercial import check_commercial

ROOT = Path(__file__).resolve().parents[1] / 'assets/narrative'


class CommercialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        author = ROOT / 'authoring'
        def load(path):
            return yaml.safe_load(path.read_text())
        cls.identity = load(author / 'people.yaml')
        cls.roster = load(author / 'workforce.yaml')['employees']
        cls.mail = [m for p in author.glob('mail-*.yaml') for m in load(p)['messages']]
        cls.docs = [d for p in author.glob('documents*.yaml') for d in load(p)['documents']]
        cls.events = [e for p in author.glob('calendars*.yaml') for e in load(p)['events']]
        cls.manifest = load(author / 'commercial.yaml')
        cls.calendar_items = [d for d in json.loads(
            (ROOT / 'generated/packages/keplerops-documents.json').read_text())['documents']
            if d['name'] in {e['id'] for e in cls.events if e.get('story') == 'commercial'}]

    def test_shipped_commercial_content(self):
        counts = check_commercial(ROOT, self.identity, self.roster, self.mail, self.docs, self.events)
        self.assertEqual(counts['histories'], 60)

    def test_rejects_false_authority_and_leaks(self):
        def record(manifest, status):
            return next(r for r in manifest['records'] if r['status'] == status)

        def rewrite_csv(doc, rows):
            stream = io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
            doc['text'] = stream.getvalue()

        def unsigned_charge(m, mail, docs, events):
            record(m, 'quoted')['accepted_amount_usd'] = '1200'

        def overlapping_renewal(m, mail, docs, events):
            r = record(m, 'accepted_renewal')
            r['next_term_start'] = r['current_term_end']

        def standing_price_changed(m, mail, docs, events):
            m['records'][0]['current_quarterly_usd'] = '40000'

        def private_attachment(m, mail, docs, events):
            r = record(m, 'completed')
            mid = r['threads']['customer']['last']
            next(x for x in mail if x['id'] == mid)['attachments'] = [r['costing_document']]

        def internal_ancestry(m, mail, docs, events):
            r = m['records'][0]
            mid = r['threads']['customer']['added'][1]
            next(x for x in mail if x['id'] == mid)['reply_to'] = r['threads']['commercial']['added'][0]

        def margin_reader(m, mail, docs, events):
            r = record(m, 'completed')
            next(x for x in docs if x['id'] == r['costing_document'])['reader_keys'].append('kwm049')

        def another_customer(m, mail, docs, events):
            r = next(r for r in m['records'] if r['organization'] == 'rillhaven')
            mid = r['threads']['customer']['added'][0]
            next(x for x in mail if x['id'] == mid)['from'] = 'bc_davenmoor_3'

        def future_completion(m, mail, docs, events):
            record(m, 'accepted_future')['delivery_accepted_at'] = '2026-09-15T10:00:00-04:00'

        def changed_accepted_offer(m, mail, docs, events):
            r = record(m, 'accepted_renewal')
            next(x for x in docs if x['id'] == r['offer_document'])['text'] += '\nAn additional interface is included.\n'

        def missing_capacity(m, mail, docs, events):
            record(m, 'accepted_future')['capacity_reservations'].pop()

        def consuming_support_reserve(m, mail, docs, events):
            row = m['capacity'][0]
            row['existing_work_and_leave_hours'] = 33
            for r in m['records']:
                for item in r['capacity_reservations']:
                    if item['record'] == row['record'] and item['week_of'] == row['week_of']:
                        item['existing_work_and_leave_hours'] = 33
            rewrite_csv(next(d for d in docs if d['id'] == m['capacity_workbook']), m['capacity'])

        def premature_final_bill(m, mail, docs, events):
            r = record(m, 'accepted_future')
            schedule = next(s for s in m['billing_schedules'] if s['record'] == r['id'])
            schedule['rows'][1]['state'] = 'authorized'
            rewrite_csv(next(d for d in docs if d['id'] == schedule['document']), schedule['rows'])

        def finance_register_drift(m, mail, docs, events):
            doc = next(d for d in docs if d['id'] == m['billing_register'])
            rows = list(csv.DictReader(io.StringIO(doc['text'])))
            rows[0]['amount_usd'] = '1.00'
            rewrite_csv(doc, rows)

        def changed_billing_date(m, mail, docs, events):
            m['billing_schedules'][0]['rows'][0]['billing_date'] = '2026-09-01'

        def invented_payment(m, mail, docs, events):
            m['billing_schedules'][0]['rows'][0]['invoice_status'] = 'paid'

        def confirmed_reference(m, mail, docs, events):
            next(e for e in events if e['id'] == 'commercial-arwc-reference-hold')['status'] = 'CONFIRMED'

        def lost_original_reference(m, mail, docs, events):
            record(m, 'reference_planned')['threads']['customer']['previous_last'] = None

        def fabricated_handover(m, mail, docs, events):
            r = next(r for r in m['records'] if r['status'] == 'completed' and r['organization'] != 'arwc')
            next(d for d in docs if d['id'] == r['deliverable_document'])['text'] += 'extra,unaccepted,sample\n'

        def premature_completion(m, mail, docs, events):
            record(m, 'completed')['initial_disposition'] = 'completed'

        def wrong_pricing_margin(m, mail, docs, events):
            r = record(m, 'completed')
            doc = next(d for d in docs if d['id'] == r['costing_document'])
            rows = list(csv.DictReader(io.StringIO(doc['text'])))
            rows[1]['planned_contribution_usd'] = '99999.00'
            rewrite_csv(doc, rows)

        mutations = [
            (unsigned_charge, 'Draft, lost, or deferred work creates billing'),
            (overlapping_renewal, 'Renewal overlaps'),
            (standing_price_changed, 'Standing commercial fee'),
            (private_attachment, 'Private commercial attachment'),
            (internal_ancestry, 'Commercial reply crosses'),
            (margin_reader, 'Private costing readers widened'),
            (another_customer, 'Commercial correspondence crosses'),
            (future_completion, 'Future commercial work claimed completed'),
            (changed_accepted_offer, 'Accepted commercial version'),
            (missing_capacity, 'Accepted project lacks full reserved effort'),
            (consuming_support_reserve, 'Commercial capacity or owner drift'),
            (premature_final_bill, 'Undelivered project becomes unconditional billing'),
            (finance_register_drift, 'Finance register differs'),
            (changed_billing_date, 'Standing billing schedule'),
            (invented_payment, 'Billing identity drift or invented invoice'),
            (confirmed_reference, 'ARWC reference hold'),
            (lost_original_reference, 'Commercial thread lost'),
            (fabricated_handover, 'Accepted handover lost its delivered evidence'),
            (premature_completion, 'Project negotiation claims delivery complete'),
            (wrong_pricing_margin, 'Commercial pricing arithmetic drift'),
        ]
        for mutate, error in mutations:
            with self.subTest(mutation=mutate.__name__), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / 'authoring').mkdir()
                shutil.copy(ROOT / 'authoring/business-network.yaml', root / 'authoring')
                (root / 'generated/packages').mkdir(parents=True)
                (root / 'generated/packages/keplerops-documents.json').write_text(
                    json.dumps({'documents': self.calendar_items}))
                manifest, mail, docs, events = copy.deepcopy((self.manifest, self.mail, self.docs, self.events))
                mutate(manifest, mail, docs, events)
                (root / 'authoring/commercial.yaml').write_text(yaml.safe_dump(manifest, sort_keys=False))
                with self.assertRaisesRegex(ValueError, error):
                    check_commercial(root, self.identity, self.roster, mail, docs, events)


if __name__ == '__main__':
    unittest.main()
