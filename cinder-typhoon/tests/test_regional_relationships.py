"""Adversarial checks for relationship archives, not fictional runtime execution."""
import copy
from pathlib import Path
import unittest

import yaml

from validate_regional_relationships import check_regional_relationships


ROOT = Path(__file__).resolve().parents[1] / 'assets/narrative'


class RegionalRelationshipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        author = ROOT / 'authoring'

        def load(path):
            return yaml.safe_load(path.read_text())

        cls.identity = load(author / 'people.yaml')
        cls.roster = load(author / 'workforce.yaml')['employees']
        cls.manifest = load(author / 'regional-relationships.yaml')
        cls.mail = load(author / 'mail-regional-relationships.yaml')['messages']
        cls.docs = load(author / 'documents-regional-relationships.yaml')['documents']
        needed_docs = {s['document'] for r in cls.manifest['records'] for s in r['source_documents']}
        needed_docs.add('a-billing-explanation')
        needed_mail = {r['previous_message'] for r in cls.manifest['records']} - {
            m['id'] for m in cls.mail} - {None}
        for path in author.glob('documents*.yaml'):
            if path.name != 'documents-regional-relationships.yaml':
                cls.docs.extend(d for d in load(path)['documents'] if d['id'] in needed_docs)
        for path in author.glob('mail-*.yaml'):
            if path.name != 'mail-regional-relationships.yaml':
                cls.mail.extend(m for m in load(path)['messages'] if m['id'] in needed_mail)
        cls.events = [e for p in author.glob('calendars*.yaml') for e in load(p)['events']]

    def check(self, manifest, mail, docs, events):
        return check_regional_relationships(ROOT, self.identity, self.roster, mail, docs,
                                            events, manifest=manifest)

    def test_shipped_archives(self):
        counts = self.check(self.manifest, self.mail, self.docs, self.events)
        self.assertEqual(counts['original_documents'], 90)
        self.assertEqual(counts['retained_copies'], 421)

    def test_rejects_corrupted_authority_and_audiences(self):
        def doc(items, key):
            return next(d for d in items if d['id'] == key)

        def record(manifest, key):
            return doc(manifest['records'], key)

        def wrong_delivery(m, mail, docs, events):
            record(m, 'rr-merewick-01')['facts']['quantity'] = 601

        def wrong_ceiling(m, mail, docs, events):
            record(m, 'rr-talvern-03')['facts']['headroom'] = 7500

        def changed_service_amount(m, mail, docs, events):
            d = doc(docs, 'rr-veybridge-01')
            d['text'] = d['text'].replace('1,240.00', '1,250.00')

        def changed_term(m, mail, docs, events):
            d = doc(docs, 'rr-orrenvale-05')
            d['text'] = d['text'].replace('30 September 2027', '30 September 2028')

        def changed_annual_fee(m, mail, docs, events):
            d = doc(docs, 'rr-rillhaven-03')
            d['text'] = d['text'].replace('89,000', '98,000')

        def wrong_reading(m, mail, docs, events):
            record(m, 'rr-belvarn-01')['facts']['reading_end'] += 1

        def rewritten_reading_explanation(m, mail, docs, events):
            d = doc(docs, 'rr-belvarn-01')
            d['text'] = d['text'].replace('218731', '218732')

        def wrong_scanning_pages(m, mail, docs, events):
            d = doc(docs, 'rr-ternwick-01')
            d['text'] = d['text'].replace('120', '121')

        def wrong_batch_payment_date(m, mail, docs, events):
            d = doc(docs, 'rr-ternwick-10')
            d['text'] = d['text'].replace('2026-09-14', '2026-09-16')

        def forged_batch_total(m, mail, docs, events):
            record(m, 'rr-ternwick-10')['facts']['total_cents'] += 18000

        def rewritten_accepted_report(m, mail, docs, events):
            doc(docs, 'me-contractor-report-001')['text'] += '\nFurther work completed.\n'

        def private_attachment(m, mail, docs, events):
            doc(mail, 'rr-arwc-10-m2')['attachments'] = ['rr-arwc-09']

        def private_ancestry(m, mail, docs, events):
            record(m, 'rr-arwc-10')['previous_message'] = 'rr-arwc-09-m3'
            doc(mail, 'rr-arwc-10-m1')['reply_to'] = 'rr-arwc-09-m3'

        def altered_counterpart(m, mail, docs, events):
            doc(docs, 'rr-arwc-01-arwc')['text'] += '\nWeekly updates promised.\n'

        def widened_reader(m, mail, docs, events):
            doc(docs, 'rr-belvarn-08')['reader_keys'].append('mina')

        def future_attachment(m, mail, docs, events):
            doc(docs, 'rr-orrenvale-01')['published_at'] = '2026-06-25T09:00:00-04:00'

        def detached_reply(m, mail, docs, events):
            doc(mail, 'rr-veybridge-02-m3').pop('reply_to')

        def unrelated_contact(m, mail, docs, events):
            # Keep copy counts unchanged so the audience check must catch this.
            r = record(m, 'rr-veybridge-01')
            r['participants'][r['participants'].index('jules')] = 'bc_talvern_2'

        def false_confirmation(m, mail, docs, events):
            doc(events, 'rr-merewick-09-call')['status'] = 'CONFIRMED'

        def future_minutes(m, mail, docs, events):
            doc(events, 'rr-ternwick-09-call')['minutes'] = 'Proposal agreed.'

        def conflicting_booking(m, mail, docs, events):
            event = copy.deepcopy(doc(events, 'rr-merewick-09-call'))
            event.update(id='another-accepted-call', story='earlier-content', status='CONFIRMED')
            events.append(event)

        def changed_time(m, mail, docs, events):
            event = doc(events, 'rr-talvern-10-call')
            event['start'] = event['start'].replace('10:00', '11:00')
            event['end'] = event['end'].replace('10:20', '11:20')

        def invented_reference_confirmation(m, mail, docs, events):
            doc(events, 'commercial-arwc-reference-hold')['status'] = 'CONFIRMED'

        def changed_workshop_example(m, mail, docs, events):
            d = doc(docs, 'rr-rillhaven-09')
            d['text'] = d['text'].replace('r3 as Draft at 19 units', 'r3 as Accepted at 19 units')

        def hidden_author_note(m, mail, docs, events):
            doc(docs, 'rr-talvern-01')['text'] += '<!-- issue 132 author-only -->\n'

        def omitted_explanation(m, mail, docs, events):
            doc(mail, 'rr-belvarn-09-m2')['attachments'].remove('a-billing-explanation')

        mutations = [
            (wrong_delivery, 'accepted delivery changed'),
            (wrong_ceiling, 'ceiling arithmetic'),
            (changed_service_amount, 'accepted service amount'),
            (changed_term, 'agreement end date'),
            (changed_annual_fee, 'agreement amount'),
            (wrong_reading, 'retail reading arithmetic'),
            (rewritten_reading_explanation, 'retail explanation changed'),
            (wrong_scanning_pages, 'scanning reference, page count or amount'),
            (wrong_batch_payment_date, 'batch register row or payment chronology'),
            (forged_batch_total, 'batch register total'),
            (rewritten_accepted_report, 'Accepted regional document rewritten'),
            (private_attachment, 'attachment leaks'),
            (private_ancestry, 'discloses a private conversation'),
            (altered_counterpart, 'counterpart bytes differ'),
            (widened_reader, 'document readers'),
            (future_attachment, 'attachment from the future'),
            (detached_reply, 'reply ancestry'),
            (unrelated_contact, 'correspondent inventory|Unrelated regional correspondent'),
            (false_confirmation, 'future call falsely'),
            (future_minutes, 'future call falsely'),
            (conflicting_booking, 'conflicts with an accepted calendar'),
            (changed_time, 'calendar differs from the proposed time'),
            (invented_reference_confirmation, 'Accepted reference hold changed'),
            (changed_workshop_example, 'reminder changes the issued example'),
            (hidden_author_note, 'hidden comment'),
            (omitted_explanation, 'billing explanation not delivered'),
        ]
        for mutate, error in mutations:
            with self.subTest(mutation=mutate.__name__):
                args = copy.deepcopy((self.manifest, self.mail, self.docs, self.events))
                mutate(*args)
                with self.assertRaisesRegex(ValueError, error):
                    self.check(*args)


if __name__ == '__main__':
    unittest.main()
