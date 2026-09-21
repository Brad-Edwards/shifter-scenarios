"""Adversarial checks for publications, invitations, privacy and office continuity."""
import copy
from datetime import datetime
from pathlib import Path
import unittest
import yaml
from validate_office_life import check_office_life

ROOT = Path(__file__).resolve().parents[1] / 'assets/narrative'


class OfficeLifeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def load(name):
            return yaml.safe_load((ROOT / 'authoring' / name).read_text())
        cls.identity = load('people.yaml')
        cls.roster = load('workforce.yaml')['employees']
        cls.manifest = load('office-life.yaml')
        cls.mail = load('mail-office-life.yaml')['messages']
        cls.docs = load('documents-office-life.yaml')['documents']
        cls.events = [e for path in (ROOT / 'authoring').glob('calendars*.yaml')
                      for e in yaml.safe_load(path.read_text())['events']]

    def check(self, f, m, d, e):
        return check_office_life(ROOT, self.identity, self.roster, m, d, e, f)

    def test_finished_office_records(self):
        result = self.check(self.manifest, self.mail, self.docs, self.events)
        self.assertEqual(result['meetings'], 458)
        self.assertEqual(result['publications'], 92)

    def test_rejects_semantic_errors(self):
        def doc(d, key): return next(x for x in d if x['id'] == key)
        def msg(m, key): return next(x for x in m if x['id'] == key)
        def event(e, key): return next(x for x in e if x['id'] == key)
        def history(f, state): return next(h for h in f['meetings'] if h['state'] == state)
        def private_note(f, m, d, e):
            h = next(h for h in f['meetings'] if h['category'] == 'check-in')
            doc(d, h['minutes'])['reader_keys'].append('kwm055')
        def personal_staff_post(f, m, d, e): doc(d, f['publications'][0]['id'])['text'] += '<p>My sister enjoyed the dinner.</p>'
        def comment_missing(f, m, d, e):
            p = next(p for p in f['publications'] if p['comments'])
            doc(d, p['id'])['text'] = doc(d, p['id'])['text'].replace(p['comments'][0]['text'], '')
        def comment_early(f, m, d, e):
            p = next(p for p in f['publications'] if p['comments'])
            p['comments'][0]['date'] = '2026-06-01T09:00:00-04:00'
        def comment_wrong_reader(f, m, d, e):
            p = next(p for p in f['publications'] if p['comments'] and p['scope'] != 'staff')
            p['comments'][0]['author'] = 'leah'
        def draft_staff(f, m, d, e): doc(d, f['drafts'][0]['draft'])['audience'] = 'staff'
        def late_approval(f, m, d, e): msg(m, f['drafts'][0]['approval'])['date'] = '2026-09-15T09:00:00-04:00'
        def wrong_consent(f, m, d, e): msg(m, f['publication_consents'][0]['approvals'][0])['from'] = 'kwm055'
        def late_consent(f, m, d, e): msg(m, f['publication_consents'][0]['approvals'][1])['date'] = '2026-09-15T09:00:00-04:00'
        def wrong_uid(f, m, d, e):
            h = history(f, 'completed'); key = msg(m, h['invitation'])['attachments'][0]
            doc(d, key)['text'] = doc(d, key)['text'].replace('UID:', 'UID:wrong-', 1)
        def wrong_reply(f, m, d, e):
            h = next(h for h in f['meetings'] if h['responses'])
            r = next(iter(h['responses'].values()))
            doc(d, r['document'])['text'] = doc(d, r['document'])['text'].replace('METHOD:REPLY', 'METHOD:REQUEST')
        def false_response(f, m, d, e):
            x = next(x for x in e if x['id'].startswith('office-') and 'NEEDS-ACTION' in x['responses'].values())
            k = next(k for k, v in x['responses'].items() if v == 'NEEDS-ACTION'); x['responses'][k] = 'ACCEPTED'
        def early_completion(f, m, d, e):
            h = history(f, 'completed'); msg(m, h['completion'])['date'] = event(e, h['id'])['start']
        def cancelled_attendance(f, m, d, e):
            h = history(f, 'cancelled'); h['actual_attendees'] = [event(e, h['id'])['organizer']]
        def declined_attendance(f, m, d, e):
            h = next(h for h in f['meetings'] if h['state'] == 'completed' and
                     any(r['status'] == 'DECLINED' for r in h['responses'].values()))
            h['actual_attendees'].append(next(k for k, r in h['responses'].items() if r['status'] == 'DECLINED'))
        def cancellation_late(f, m, d, e):
            h = history(f, 'cancelled'); msg(m, h['cancellation'])['date'] = event(e, h['id'])['end']
        def cancelled_revision(f, m, d, e): event(e, history(f, 'cancelled')['id'])['sequence'] = 0
        def lost_reschedule(f, m, d, e): next(h for h in f['meetings'] if 'replaces' in h)['replaces'] = f['meetings'][0]['id']
        def room_capacity(f, m, d, e): f['rooms']['small']['capacity'] = 1
        def room_storage(f, m, d, e): event(e, f['meetings'][0]['id'])['location'] = 'Storage room'
        def cover_attending(f, m, d, e):
            x = next(x for x in e if x.get('cover')); x['cover'] = [x['organizer']]
        def cover_removed(f, m, d, e): next(x for x in e if x.get('cover'))['cover'] = []
        def cover_late(f, m, d, e):
            h = next(h for h in f['meetings'] if 'cover_agreement' in h)
            msg(m, h['cover_agreement'])['date'] = event(e, h['id'])['end']
        def freebusy_leak(f, m, d, e):
            doc(d, f['availability_document'])['text'] = doc(d, f['availability_document'])['text'].replace('Reserved', 'Private career discussion', 1)
        def future_minutes(f, m, d, e):
            h = history(f, 'planned'); h['completion'] = history(f, 'completed')['completion']
        def note_collection(f, m, d, e):
            h = next(h for h in f['meetings'] if h['category'] == 'check-in'); doc(d, h['minutes']).pop('collection')
        def wrong_manager(f, m, d, e): f['people_actions'][0]['manager'] = 'leah'
        def seat_overuse(f, m, d, e):
            l = next(l for l in f['learning'] if l['kind'] == 'purchased'); l['participants'].append(l['participants'][0])
        def wrong_rail_claim(f, m, d, e): next(l for l in f['learning'] if l['kind'] == 'internal-visit')['claim'] = 'EX-26-001'
        def missing_example(f, m, d, e): doc(d, f['working_examples'][0]['document'])['text'] = 'Discuss the example.\n'
        def private_rota(f, m, d, e): doc(d, f['support_swap']['document'])['text'] += 'Maya is seeing her sister.\n'
        def future_attachment(f, m, d, e):
            h = history(f, 'completed'); doc(d, msg(m, h['invitation'])['attachments'][0])['published_at'] = '2026-09-15T22:00:00-04:00'
        cases = [private_note, personal_staff_post, comment_missing, comment_early, comment_wrong_reader,
                 draft_staff, late_approval, wrong_consent, late_consent, wrong_uid, wrong_reply,
                 false_response, early_completion, cancelled_attendance, declined_attendance,
                 cancellation_late, cancelled_revision, lost_reschedule, room_capacity, room_storage,
                 cover_attending, cover_removed, cover_late, freebusy_leak, future_minutes,
                 note_collection, wrong_manager, seat_overuse, wrong_rail_claim, missing_example,
                 private_rota, future_attachment]
        for mutate in cases:
            with self.subTest(mutation=mutate.__name__):
                f, m, d, e = copy.deepcopy((self.manifest, self.mail, self.docs, self.events))
                mutate(f, m, d, e)
                with self.assertRaises(ValueError): self.check(f, m, d, e)

    def test_existing_calendar_and_cover_conflicts(self):
        # These deliberately keep every new invitation and record consistent;
        # conflict detection must compare against the accepted calendar corpus.
        for use_cover in (False, True):
            with self.subTest(cover=use_cover):
                f, m, d, e = copy.deepcopy((self.manifest, self.mail, self.docs, self.events))
                booked = next(x for x in e if x['id'].startswith('office-') and x.get('cover') and x['status'] != 'CANCELLED')
                actor = booked['cover'][0] if use_cover else booked['organizer']
                e.append({'id': 'accepted-conflicting-appointment', 'organizer': actor,
                          'attendees': [], 'start': booked['start'], 'end': booked['end'], 'status': 'CONFIRMED'})
                with self.assertRaisesRegex(ValueError, 'booking conflict'):
                    self.check(f, m, d, e)

    def test_room_conflict_even_with_consistent_invitations(self):
        f, m, d, e = copy.deepcopy((self.manifest, self.mail, self.docs, self.events))
        active = [x for x in e if x['id'].startswith('office-') and x['room'] != 'remote' and x['status'] != 'CANCELLED']
        target, other = next((a, b) for a in active for b in active
                             if a['id'] != b['id'] and a['room'] != b['room'] and
                             datetime.fromisoformat(a['start']) < datetime.fromisoformat(b['end']) and
                             datetime.fromisoformat(b['start']) < datetime.fromisoformat(a['end']) and
                             len(a['in_person']) <= f['rooms'][b['room']]['capacity'])
        before, after = target['location'], other['location']
        target['room'], target['location'] = other['room'], after
        h = next(h for h in f['meetings'] if h['id'] == target['id'])
        for item in d:
            if item['id'] in h['documents']:
                item['text'] = item['text'].replace('LOCATION:' + before, 'LOCATION:' + after)
        with self.assertRaisesRegex(ValueError, 'booking conflict for room:'):
            self.check(f, m, d, e)


if __name__ == '__main__':
    unittest.main()
