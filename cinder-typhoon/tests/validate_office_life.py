"""Check office publications, private records, actual attendance and booking history."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
import csv
import html
import io
import uuid
import yaml


def require(ok, why):
    if not ok:
        raise ValueError('Office life: ' + why)


def moment(value):
    return datetime.fromisoformat(value)


class Page(HTMLParser):
    """Read the shipped HTML, including its publication and comment timestamps."""
    def __init__(self, text):
        super().__init__()
        self.times, self.words, self.comments = [], [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == 'time':
            self.times.append(dict(attrs).get('datetime'))

    def handle_data(self, data):
        self.words.append(data)

    def handle_comment(self, data):
        self.comments.append(data)


def calendar(text):
    require(text.endswith('\r\n') and '\n' not in text.replace('\r\n', ''), 'calendar line endings')
    require(all(len(line.encode()) <= 75 for line in text.split('\r\n')), 'calendar folding')
    lines = text.replace('\r\n ', '').split('\r\n')
    result = defaultdict(list)
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            result[key].append(value)
    require(result['BEGIN'] == ['VCALENDAR', 'VEVENT'] and
            result['END'] == ['VEVENT', 'VCALENDAR'], 'calendar structure')
    return result


def check_calendar_part(part):
    """iMIP requires the MIME method parameter to match the scheduling object."""
    if part.get_content_type() != 'text/calendar':
        return
    methods = calendar(part.get_payload(decode=True).decode('utf-8'))['METHOD']
    parameter = part.get_param('method')
    require(methods == ([parameter.upper()] if parameter else []), 'scheduling MIME method')


def check_office_life(root, identity, roster, mail, docs, events, manifest=None):
    def load(name):
        return yaml.safe_load((root / 'authoring' / name).read_text())
    f = manifest if manifest is not None else load('office-life.yaml')
    people = {p['key']: p for p in roster}
    staff = {k for k, p in people.items() if p['employer'] == 'keplerops'}
    source_mail = {m['id']: m for m in mail}
    messages = {k: m for k, m in source_mail.items() if k.startswith('ol-')}
    documents = {d['id']: d for d in docs if d.get('story') == 'office-life'}
    calendars = {e['id']: e for e in events if e['id'].startswith('office-2026-')}
    histories = {h['id']: h for h in f['meetings']}
    snapshot = moment(identity['snapshot'])
    require(f['snapshot'] == identity['snapshot'] and f['required_base'] == '877bd6b' and
            f['accepted_finance_commit'] == '437f1e9', 'base or snapshot drift')
    require(set(calendars) == set(histories) and 400 <= len(calendars) <= 700,
            'meeting inventory')
    require(80 <= len(f['publications']) <= 140 and len(f['references']) >= 12,
            'publication coverage')
    require(set(f['support_keys']) == {k for k in staff if people[k]['team'] == 'Customer support'},
            'support roster drift')
    counts = f['counts']
    observed = {'publications': len(f['publications']),
                'comments': sum(len(p['comments']) for p in f['publications']),
                'reference_pages': len(f['references']), 'drafts': len(f['drafts']),
                'meetings': len(calendars), 'meeting_states': dict(Counter(h['state'] for h in histories.values())),
                'categories': dict(Counter(h['category'] for h in histories.values())),
                'formal_notes': sum('minutes' in h for h in histories.values()),
                'preparation_agendas': sum('agenda' in h for h in histories.values()),
                'learning_arrangements': len(f['learning']), 'people_actions': len(f['people_actions']),
                'logical_messages': len(messages), 'documents': len(documents),
                'retained_copies': sum(1 + len(m['to']) for m in messages.values())}
    require(counts == observed, 'count reconciliation')

    def readers(d):
        return staff if d['audience'] == 'staff' else set(d['reader_keys'])

    def restricted(d, audience):
        require(d['audience'] == 'restricted' and readers(d) == set(audience),
                'private readers: ' + d['id'])

    for m in messages.values():
        require({m['from'], *m['to']} <= staff and m['from'] not in m['to'], 'mail participants')
        require(moment(m['date']) < snapshot and m['body'].endswith('\n'), 'mail date or body')
        if 'reply_to' in m:
            # Original accepted private-story parents may be outside the office slice.
            parent = source_mail.get(m['reply_to'])
            if parent:
                require(moment(parent['date']) < moment(m['date']), 'reply precedes parent')
        for key in m.get('attachments', []):
            d = documents.get(key)
            require(d is not None, 'unknown office attachment')
            require(moment(d['published_at']) <= moment(m['date']), 'future attachment')
            require({m['from'], *m['to']} <= readers(d), 'attachment audience')
    for d in documents.values():
        require(moment(d['published_at']) <= snapshot and readers(d) <= staff, 'document date or audience')
        require(d['employer'] == 'keplerops' and d.get('text'), 'empty document')
        if d['audience'] == 'staff':
            text = html.unescape(d['text']).lower()
            require(not any(s in text for s in ('housemates', 'clarinet', 'my sister', 'family dinner',
                                               '1,329,726', '311,900', '135,945.51')),
                    'private detail in staff publication')

    quiet = 0
    for p in f['publications']:
        d = documents[p['id']]
        require(d.get('media_type') == 'text/html', 'publication is not HTML')
        require(readers(d) == set(p['reader_keys']) and p['author'] in readers(d), 'publication readers')
        require((p['scope'] == 'staff') == (d['audience'] == 'staff'), 'publication scope')
        require(d['published_at'] == p['published_at'] and
                moment(p['posted_at']) <= moment(p['published_at']) <= snapshot, 'publication chronology')
        if 'after_event' in p:
            require(histories[p['after_event']]['state'] == 'completed' and
                    moment(calendars[p['after_event']]['end']) <= moment(p['posted_at']),
                    'public recap precedes completed event')
        page = Page(d['text'])
        require(not page.comments and len(' '.join(page.words).split()) >= 45, 'empty or hidden publication')
        require(page.times == [p['posted_at']] + [c['date'] for c in p['comments']], 'HTML comment dates')
        require(people[p['author']]['name'] in d['text'] and 'DRAFT' not in d['text'], 'publication authorship/state')
        quiet += not p['comments']
        for c in p['comments']:
            require(c['author'] in readers(d) and
                    moment(p['posted_at']) <= moment(c['date']) <= moment(p['published_at']), 'comment audience or time')
            require(html.escape(c['text']) in d['text'] and people[c['author']]['name'] in d['text'],
                    'comment missing from actual page')
    require(quiet >= len(f['publications']) // 2, 'unrealistically universal comments')
    for r in f['references']:
        d = documents[r['id']]
        require(d['audience'] == 'staff' and d.get('media_type') == 'text/html' and
                len(' '.join(Page(d['text']).words).split()) >= 140, 'reference page lacks substance')
    for draft in f['drafts']:
        d, p = documents[draft['draft']], documents[draft['publication']]
        restricted(d, draft['permitted_readers'])
        approval = messages[draft['approval']]
        require('DRAFT' in d['text'] and approval['from'] == draft['author'] and
                moment(approval['date']) < moment(p['published_at']), 'draft approval chronology')
        require(all(k in messages for k in draft['messages']), 'missing editorial exchange')
    for consent in f['publication_consents']:
        approvals = [messages[k] for k in consent['approvals']]
        p = next(p for p in f['publications'] if p['id'] == consent['publication'])
        require({m['from'] for m in approvals} == set(consent['people']) and
                all(moment(m['date']) < moment(p['posted_at']) for m in approvals), 'publication consent')

    # Preserve full invitation/cancellation/response bytes with an independently
    # reconstructed UID, time, revision and attendee-state contract.
    def check_ics(d, e, method, when, status, respondent=None):
        c = calendar(d['text'])
        uid = str(uuid.uuid5(uuid.NAMESPACE_URL, 'urn:cinder-workplace:' + e['id'])) + '@keplerops.com'
        utc = lambda s: moment(s).astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        require(c['UID'] == [uid] and c['METHOD'] == [method], 'calendar UID or method')
        require(c['DTSTART'] == [utc(e['start'])] and c['DTEND'] == [utc(e['end'])] and
                c['DTSTAMP'] == [utc(when)], 'invitation time')
        require(c['STATUS'] == [status] and c['SEQUENCE'] == ['1' if method == 'CANCEL' else '0'],
                'calendar status or sequence')
        require(c['ORGANIZER'] == ['mailto:' + people[e['organizer']]['email']], 'calendar organizer')
        actual = {k: v for k, v in c.items() if k.startswith('ATTENDEE')}
        expected = defaultdict(list)
        for k in ([respondent] if respondent else e['attendees']):
            part = e['responses'][k] if respondent else 'NEEDS-ACTION'
            field = ('ATTENDEE' if method == 'CANCEL' else
                     'ATTENDEE;PARTSTAT=' + part + (';RSVP=TRUE' if method == 'REQUEST' else ''))
            expected[field].append('mailto:' + people[k]['email'])
        require(actual == dict(expected), 'calendar response participants')
        escaped = lambda s: s.replace('\\', '\\\\').replace('\n', '\\n').replace(',', '\\,').replace(';', '\\;')
        require(c['SUMMARY'] == [escaped(e['summary'])] and c['LOCATION'] == [escaped(e['location'])] and
                c['DESCRIPTION'] == [escaped(e['description'])], 'calendar content')

    bookings = defaultdict(list)
    for e in events:
        if e['id'] in calendars or e['status'] == 'CANCELLED':
            continue
        for k in {e['organizer'], *e['attendees']}:
            bookings[k].append((moment(e['start']), moment(e['end']), e['id']))
    all_support = set(f['support_keys'])
    for key, e in calendars.items():
        h = histories[key]
        start, end, created = map(moment, (e['start'], e['end'], e['created_at']))
        audience = {e['organizer'], *e['attendees']}
        require(audience == set(h['invitees']) and audience <= staff, 'meeting people')
        require(created < start < end and created < snapshot and
                created <= moment(e['updated_at']) <= snapshot, 'meeting chronology')
        require(set(e['responses']) == set(e['attendees']) and
                set(e['responses'].values()) <= {'ACCEPTED', 'DECLINED', 'TENTATIVE', 'NEEDS-ACTION'}, 'response inventory')
        require(all(people[k]['start_date'] <= e['start'][:10] for k in audience), 'meeting before employment')
        room = f['rooms'].get(e['room'])
        require(room and 'storage' not in e['location'].lower() and e['location'].startswith(room['name']), 'unbookable room')
        require(set(e['in_person']) <= audience and len(e['in_person']) <= room['capacity'], 'room capacity')
        require(e['room'] != 'remote' or not e['in_person'], 'remote event has physical seats')
        require(all(e['responses'].get(k) != 'DECLINED' for k in e['in_person']), 'declined physical attendee')
        invitation = messages[h['invitation']]
        require(invitation['from'] == e['organizer'] and set(invitation['to']) == set(e['attendees']) and
                invitation['date'] == e['created_at'], 'invitation routing')
        request = documents[invitation['attachments'][0]]
        restricted(request, audience)
        check_ics(request, e, 'REQUEST', e['created_at'], 'CONFIRMED' if h['state'] == 'cancelled' else e['status'])
        require(set(h['responses']) == {k for k, v in e['responses'].items() if v != 'NEEDS-ACTION'},
                'response lacks evidence')
        for k, response in h['responses'].items():
            m, d = messages[response['message']], documents[response['document']]
            require(m['from'] == k and m['to'] == [e['organizer']] and response['status'] == e['responses'][k] and
                    created < moment(m['date']) < start and response['document'] in m['attachments'], 'RSVP evidence')
            restricted(d, [k, e['organizer']])
            check_ics(d, e, 'REPLY', m['date'], 'CONFIRMED', k)
        if h['state'] == 'cancelled':
            require(e['status'] == 'CANCELLED' and e['sequence'] == 1 and not h['actual_attendees'] and
                    'minutes' not in h and 'completion' not in h, 'cancelled meeting has completion')
            m = messages[h['cancellation']]
            require(created < moment(m['date']) < start and m['date'] == e['updated_at'], 'cancellation chronology')
            d = documents[m['attachments'][0]]
            restricted(d, audience)
            check_ics(d, e, 'CANCEL', m['date'], 'CANCELLED')
        elif h['state'] == 'completed':
            require(e['status'] == 'CONFIRMED' and end < snapshot and h['actual_attendees'], 'false completed meeting')
            actual = set(h['actual_attendees'])
            require(actual <= audience and e['organizer'] in actual and
                    all(e['responses'].get(k) != 'DECLINED' for k in actual), 'false attendance')
            m = messages[h['completion']]
            require(end <= moment(m['date']) < snapshot and m['from'] == e['organizer'], 'completion chronology')
            require(all(people[k]['name'] in m['body'] for k in actual), 'completion lacks attendance evidence')
        else:
            require(h['state'] == 'planned' and start > snapshot and 'completion' not in h and
                    'minutes' not in h and not h['actual_attendees'], 'future meeting has completion')
        if 'minutes' in h:
            d = documents[h['minutes']]
            restricted(d, audience)
            require(h['state'] == 'completed' and end <= moment(d['published_at']) <= snapshot and
                    d['text'] == messages[h['completion']]['body'], 'minutes do not match completed evidence')
            require(d.get('collection') == ('employment' if h['private'] else None), 'private note collection')
        if 'agenda' in h:
            d = documents[h['agenda']]
            restricted(d, audience)
            require(moment(d['published_at']) < start, 'late agenda')
        if h['category'] == 'check-in':
            require(people[h['employee']]['manager'] == h['manager'] == e['organizer'] and
                    audience == {h['employee'], h['manager']} and h['private'], 'check-in reporting line')
        if 'replacement' in h:
            other = histories[h['replacement']]
            require(h['state'] == 'cancelled' and other['replaces'] == key and
                    moment(calendars[other['id']]['created_at']) > moment(messages[h['cancellation']]['date']),
                    'reschedule lacks preserved cancellation')
        if 'replaces' in h:
            require(histories[h['replaces']].get('replacement') == key, 'orphan replacement')
        cover = set(e['cover'])
        require(not (cover & audience) and cover <= set(f['cover_pool']), 'cover is attending or unqualified')
        if audience & all_support:
            require(cover, 'support meeting lacks cover')
            agreement = messages[h['cover_agreement']]
            require(agreement['from'] in cover and agreement['to'] == [e['organizer']] and
                    moment(agreement['date']) < start, 'cover lacks prior agreement')
        if h['state'] != 'cancelled':
            active = {e['organizer']} | {k for k, v in e['responses'].items() if v != 'DECLINED'} | cover
            require(not set(f['cover_pool']) <= (active - cover), 'all support unavailable')
            if e['room'] != 'remote':
                active.add('room:' + e['room'])
            for k in active:
                for a, b, other in bookings[k]:
                    require(not (start < b and a < end), f'booking conflict for {k}: {key} / {other}')
                bookings[k].append((start, end, key))

    # The shared room view is computed from actual bookings and reveals no subjects.
    d = documents[f['availability_document']]
    require(d['audience'] == 'staff' and d.get('media_type') == 'text/csv', 'availability audience or format')
    rows = list(csv.DictReader(io.StringIO(d['text'])))
    expected = [{'room': f['rooms'][e['room']]['name'], 'start': e['start'], 'end': e['end'], 'status': 'Reserved'}
                for e in sorted(calendars.values(), key=lambda e: (e['room'], e['start']))
                if e['room'] != 'remote' and e['status'] != 'CANCELLED']
    require(rows == expected, 'availability leaks details or retains cancelled reservation')

    finance = load('finance.yaml')
    purchases = {p['id']: p for p in finance['purchases']}
    claims = {c['id']: c for c in finance['claims']}
    paid, visits = set(), set()
    for learning in f['learning']:
        e, h = calendars[learning['event']], histories[learning['event']]
        require(h['category'] == 'learning' and set(learning['participants']) <= set(h['actual_attendees']),
                'learning attendance')
        if learning['kind'] == 'purchased':
            p = purchases[learning['purchase']]
            require(p['vendor'] == 'orvessan' and learning['purchase'] not in paid and
                    len(learning['participants']) == p['quantity'] and p['received'] <= e['start'][:10], 'learning purchase join')
            restricted(documents[learning['administration']], learning['participants'] + [p['owner']])
            paid.add(learning['purchase'])
        elif learning['kind'] == 'internal-visit':
            c = claims[learning['claim']]
            require(learning['claim'] not in visits and learning['participants'] == [c['employee']] and
                    c['incurred'] == e['start'][:10] and 'Rail to internal learning' in c['description'] and
                    c['employee'] in e['in_person'], 'learning travel join')
            visits.add(learning['claim'])
    require(paid == {p['id'] for p in purchases.values() if p['vendor'] == 'orvessan'} and len(visits) == 8,
            'accepted learning coverage')
    for action in f['people_actions']:
        require(people[action['employee']]['manager'] == action['manager'], 'people reporting line')
        d = documents[action['document']]
        restricted(d, [action['employee'], action['manager'], action['contact']])
        require(d.get('collection') == 'employment' and all(k in messages for k in action['messages']), 'people record')
        require(action['document'] in messages[action['messages'][-1]].get('attachments', []), 'people final attachment')
    for example in f['working_examples']:
        d = documents[example['document']]
        restricted(d, example['readers'])
        require(len(d['text'].split()) >= 100, 'working example missing')
        for h in histories.values():
            if h.get('group') == example['group']:
                require(h.get('working_example') == d['id'] and
                        moment(d['published_at']) < moment(calendars[h['id']]['start']), 'working example chronology')
    swap = f['support_swap']
    require(swap['original'] == 'maya' and swap['cover'] == 'kwm023' and swap['date'] == '2026-09-12' and
            messages[swap['approval']]['from'] == 'kwm022' and
            messages[swap['approval']]['date'][:10] < swap['date'] <= messages[swap['handback']]['date'][:10],
            'accepted family cover continuity')
    start = moment(swap['date'] + 'T' + swap['start'] + ':00-04:00')
    end = moment(swap['date'] + 'T' + swap['end'] + ':00-04:00')
    require(all(not (start < b and a < end) for a, b, _ in bookings[swap['cover']]), 'family cover conflict')
    require('sister' not in documents[swap['document']]['text'].lower(), 'family detail in shared rota')
    rehearsal = next(calendars[h['id']] for h in histories.values() if h.get('tag') == 'rehearsal')
    require(rehearsal['start'][:10] == '2026-09-09' and rehearsal['organizer'] == 'talia' and
            moment(rehearsal['created_at']) > moment('2026-09-08T11:20:00-04:00') and
            rehearsal['end'] < '2026-09-09T14:08:00-04:00', 'accepted rehearsal chronology')
    lunch = next(calendars[h['id']] for h in histories.values() if h.get('tag') == 'lunch')
    require(lunch['start'][:10] == '2026-09-10' and
            moment(lunch['created_at']) > moment('2026-09-08T13:02:00-04:00'), 'accepted lunch chronology')
    require(not any(e['start'].startswith('2026-10-01') and {e['organizer'], *e['attendees']} == {'evan', 'noor'}
                    for e in calendars.values()), 'duplicated accepted October lunch')
    require(all(histories[e['id']]['state'] == 'planned' and e['status'] == 'TENTATIVE'
                for e in calendars.values() if e['start'].startswith('2026-11')), 'anniversary already completed')
    return observed
