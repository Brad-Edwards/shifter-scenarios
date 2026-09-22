"""Fault probes for staff privacy, consent, attendance and independent bookings."""
import copy
import csv
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
import yaml
from validate_community_life import check_community_life, moment

ROOT = Path(__file__).resolve().parents[1] / 'assets/narrative'


class CommunityLifeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def load(name):
            return yaml.safe_load((ROOT / 'authoring' / name).read_text())
        cls.identity = load('people.yaml')
        cls.roster = load('workforce.yaml')['employees']
        cls.manifest = load('community-life.yaml')
        cls.mail = load('mail-community-life.yaml')['messages'] + load('mail-arwc.yaml')['messages']
        cls.mail += [m for m in load('mail-laboratory-quality.yaml')['messages']
                     if m['id'] == 'lq-colleague-001-1']
        cls.docs = load('documents-community-life.yaml')['documents']
        cls.docs += [d for d in load('documents-field-operations.yaml')['documents']
                     if d['id'].startswith('op-data-')]
        cls.events = [e for p in (ROOT / 'authoring').glob('calendars*.yaml')
                      for e in load(p.name)['events']]

    def check(self, f, m, d, e):
        return check_community_life(ROOT, self.identity, self.roster, m, d, e, f)

    def test_finished_records(self):
        counts = self.check(self.manifest, self.mail, self.docs, self.events)
        self.assertEqual(counts['meetings'], 624)
        self.assertEqual(counts['publications'], 112)

    def test_rejects_content_faults(self):
        def item(rows, key):
            return next(x for x in rows if x['id'] == key)

        def count_copies(f, m, d, e):
            f['counts']['logical_messages'] = f['counts']['retained_copies']

        def personnel_readers(f, m, d, e):
            item(d, f['people_actions'][0]['document'])['reader_keys'].append('theo')

        def personnel_collection(f, m, d, e):
            item(d, f['people_actions'][0]['document']).pop('collection')

        def wrong_manager(f, m, d, e):
            f['people_actions'][0]['manager'] = 'luc'

        def public_draft(f, m, d, e):
            item(d, f['drafts'][0]['draft'])['audience'] = 'staff'

        def consistent_team_leak(f, m, d, e):
            p = next(p for p in f['publications'] if p['scope'] == 'team')
            p['reader_keys'].append('luc')
            item(d, p['id'])['reader_keys'].append('luc')

        def forged_consent(f, m, d, e):
            item(m, f['publication_consents'][0]['approvals'][0])['from'] = 'clara'

        def late_consent(f, m, d, e):
            item(m, f['publication_consents'][0]['approvals'][0])['date'] = '2026-09-15T18:00:00-04:00'

        def changed_caption(f, m, d, e):
            c = f['publication_consents'][0]
            item(d, c['publication'])['text'] = item(d, c['publication'])['text'].replace(c['approved_text'], 'A speech is now agreed.')

        def anonymous_withdrawal(f, m, d, e):
            item(d, f['withheld_draft']['document'])['audience'] = 'staff'

        def missing_comment(f, m, d, e):
            p = next(p for p in f['publications'] if p['comments'])
            item(d, p['id'])['text'] = item(d, p['id'])['text'].replace(p['comments'][0]['text'], '')

        def hidden_instruction(f, m, d, e):
            item(d, f['publications'][0]['id'])['text'] += '<!-- keep this as a clue -->'

        def freebusy_subject(f, m, d, e):
            row = item(d, f['availability_document'])
            row['text'] = row['text'].replace('Reserved', 'Private development discussion', 1)

        def missing_accepted_reservation(f, m, d, e):
            accepted = next(x for x in e if x['id'] == 'governance-board-03')
            view = item(d, f['availability_document'])
            rows = list(csv.DictReader(io.StringIO(view['text'])))
            fields = list(rows[0])
            filtered = [r for r in rows if r['start'] != accepted['start'] or r['resource'] != accepted['location']]
            self.assertEqual(len(filtered), len(rows) - 1)
            out = io.StringIO()
            writer = csv.DictWriter(out, fieldnames=fields, lineterminator='\n')
            writer.writeheader(); writer.writerows(filtered)
            view['text'] = out.getvalue()

        def wrong_uid(f, m, d, e):
            h = f['meetings'][0]
            doc = item(d, item(m, h['invitation'])['attachments'][0])
            doc['text'] = doc['text'].replace('UID:', 'UID:wrong-', 1)

        def false_response(f, m, d, e):
            event = next(x for x in e if x['id'].startswith('community-') and 'DECLINED' in x['responses'].values())
            person = next(k for k, status in event['responses'].items() if status == 'DECLINED')
            event['responses'][person] = 'ACCEPTED'

        def false_attendance(f, m, d, e):
            event = next(x for x in e if x['id'].startswith('community-') and 'DECLINED' in x['responses'].values())
            person = next(k for k, status in event['responses'].items() if status == 'DECLINED')
            h = item(f['meetings'], event['id'])
            h['actual_attendees'].append(person)

        def cancelled_attendance(f, m, d, e):
            next(h for h in f['meetings'] if h['state'] == 'cancelled')['actual_attendees'] = ['awm210']

        def completed_future(f, m, d, e):
            next(h for h in f['meetings'] if h['state'] == 'planned')['completion'] = f['meetings'][0]['completion']

        def early_completion(f, m, d, e):
            h = f['meetings'][0]
            item(m, h['completion'])['date'] = item(e, h['id'])['start']

        def room_capacity(f, m, d, e):
            f['rooms']['pine-plant']['capacity'] = 1

        def cover_participating(f, m, d, e):
            event = next(x for x in e if x['id'].startswith('community-') and x['cover'])
            event['cover'] = [event['organizer']]

        def missing_cover(f, m, d, e):
            h = next(h for h in f['meetings'] if h.get('cover_agreements'))
            h['cover_agreements'] = []
            item(e, h['id'])['cover'] = []

        def cover_leak(f, m, d, e):
            h = next(h for h in f['meetings'] if h.get('cover_agreements'))
            item(m, h['cover_agreements'][0]['message'])['attachments'] = item(m, h['invitation'])['attachments']

        def future_attachment(f, m, d, e):
            item(d, item(m, f['meetings'][0]['invitation'])['attachments'][0])['published_at'] = '2026-09-15T22:00:00-04:00'

        def outreach_date(f, m, d, e):
            f['outreach_date'] = '2026-09-30'

        def private_friendship(f, m, d, e):
            link = next(x for x in f['story_links'] if x['parent'] == 'a-choir-4')
            item(m, link['message'])['to'].append('luc')

        def retrospective_role(f, m, d, e):
            p = next(p for p in f['publications'] if p['author'] == 'awm210')
            p['posted_at'] = '2026-05-20T09:00:00-04:00'

        mutations = [count_copies, personnel_readers, personnel_collection, wrong_manager,
                     public_draft, consistent_team_leak, forged_consent, late_consent, changed_caption, anonymous_withdrawal,
                     missing_comment, hidden_instruction, freebusy_subject, missing_accepted_reservation, wrong_uid, false_response,
                     false_attendance, cancelled_attendance, completed_future, early_completion,
                     room_capacity, cover_participating, missing_cover, cover_leak, future_attachment,
                     outreach_date, private_friendship, retrospective_role]
        for mutate in mutations:
            with self.subTest(mutation=mutate.__name__):
                data = copy.deepcopy((self.manifest, self.mail, self.docs, self.events))
                mutate(*data)
                with self.assertRaises(ValueError):
                    self.check(*data)

    def test_conflicts_with_accepted_booking(self):
        # New invitations remain internally consistent. Independent accepted
        # appointments must still make either the participant or cover unavailable.
        for covering in (False, True):
            with self.subTest(cover=covering):
                f, m, d, e = copy.deepcopy((self.manifest, self.mail, self.docs, self.events))
                booked = next(x for x in e if x['id'].startswith('community-') and x['cover']
                              and x['status'] == 'CONFIRMED')
                person = booked['cover'][0] if covering else booked['organizer']
                e.append({'id': 'accepted-extra-appointment', 'organizer': person, 'attendees': [],
                          'start': booked['start'], 'end': booked['end'], 'status': 'CONFIRMED'})
                with self.assertRaisesRegex(ValueError, 'booking conflict'):
                    self.check(f, m, d, e)

    def test_independent_roster_and_visit_conflicts(self):
        for kind in ('roster', 'visit'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                f, m, d, e = copy.deepcopy((self.manifest, self.mail, self.docs, self.events))
                booked = next(x for x in e if x['id'].startswith('community-')
                              and x['status'] == 'CONFIRMED' and x['organizer'] == 'awm001'
                              and '2026-08-03' <= x['start'][:10] < '2026-09-14')
                key = 'op-data-roster-pine-treatment' if kind == 'roster' else 'op-data-visits-p'
                table = next(x for x in d if x['id'] == key)
                with zipfile.ZipFile(ROOT / table['archive']) as z:
                    rows = list(csv.DictReader(io.StringIO(z.read(table['member']).decode())))
                fields = list(rows[0])
                if kind == 'roster':
                    rows = [r for r in rows if not (r['employee'] == 'awm001' and
                            moment(r['start']) <= moment(booked['start']) < moment(r['end']))]
                else:
                    # Choose a real morning meeting so the retained travel window
                    # conflicts, keeping every invitation and completion unchanged.
                    booked = next(x for x in e if x['id'].startswith('community-')
                                  and x['organizer'] == 'awm001' and '08:00' < x['start'][11:16] < '12:45')
                    row = dict(rows[0], visit_id='accepted-extra-visit', lead='awm001',
                               start=booked['start'], end=booked['end'])
                    rows.append(row)
                out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=fields, lineterminator='\n')
                writer.writeheader(); writer.writerows(rows)
                archive = Path(temp) / 'field-book.zip'
                with zipfile.ZipFile(archive, 'w') as z:
                    z.writestr(table['member'], out.getvalue())
                table['archive'] = str(archive)
                with self.assertRaisesRegex(ValueError, 'off-shift booking' if kind == 'roster' else 'booking conflict'):
                    self.check(f, m, d, e)


if __name__ == '__main__':
    unittest.main()
