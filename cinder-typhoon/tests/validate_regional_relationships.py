"""Check regional correspondence against accepted work, audiences and appointments."""
from collections import Counter
from datetime import datetime
from decimal import Decimal
import hashlib
import html
from html.parser import HTMLParser
import re

import yaml


STORY = 'regional-relationships'
ORGANIZATIONS = {'arwc', 'veybridge', 'ardenvale', 'merewick', 'rillhaven',
                 'belvarn', 'talvern', 'orrenvale', 'ternwick'}
PRINCIPALS = {'arwc', 'keplerops'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def document_text(root, document):
    return document['text'] if 'text' in document else (root / document['file']).read_text()


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class Page(HTMLParser):
    """Reject executable/remote content and require a complete local reading page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.tags = Counter()

    def handle_starttag(self, tag, attrs):
        require(tag in {'html', 'head', 'meta', 'title', 'body', 'header', 'h1',
                        'p', 'br', 'table', 'tr', 'td', 'th', 'thead', 'tbody'},
                'Unexpected regional HTML element')
        require(all(k in {'lang', 'charset'} for k, _ in attrs),
                'Unexpected regional HTML attribute')
        self.tags[tag] += 1
        if tag not in {'meta', 'br'}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        require(self.stack and self.stack.pop() == tag, 'Unbalanced regional HTML')

    def handle_comment(self, data):
        raise ValueError('Regional HTML contains a hidden comment')


def check_regional_relationships(root, identity, roster, mail, documents, calendars,
                                 manifest=None):
    def load(name):
        return yaml.safe_load((root / 'authoring' / name).read_text())

    manifest = manifest if manifest is not None else load('regional-relationships.yaml')
    contacts = identity['people'] | identity['correspondents'] | {p['key']: p for p in roster}
    accounts = {o['key']: o for o in load('business-network.yaml')['organizations']}
    jobs = load('maintenance-engineering.yaml')['contractor_jobs']
    purchases = {h['id']: h for h in load('purchasing-stores.yaml')['histories']}
    snapshot = datetime.fromisoformat(identity['snapshot'])
    require(manifest['snapshot'] == identity['snapshot'], 'Regional snapshot drift')
    require(manifest['native_sources'] == {
        'keplerops': 'k-corporate.k-staff', 'arwc': 'a-corporate.a-business'},
        'Regional logical owner drift')
    require(contacts['jules']['employer'] == 'veybridge' and
            'jules' not in {p['key'] for p in roster}, 'Contractor became an employee')
    for name, expected in manifest['source_digests'].items():
        require(hashlib.sha256((root / 'authoring' / name).read_bytes()).hexdigest() == expected,
                'Accepted regional source changed: ' + name)
    by_mail = {m['id']: m for m in mail}
    by_doc = {d['id']: d for d in documents}
    by_event = {e['id']: e for e in calendars}
    new_mail = {k: m for k, m in by_mail.items() if m['story'] == STORY}
    new_docs = {k: d for k, d in by_doc.items() if d['story'] == STORY}
    new_events = {k: e for k, e in by_event.items() if e.get('story') == STORY}
    records = manifest['records']
    message_owners = {mid: r for r in records for mid in r['messages']}
    require(len(records) == len({r['id'] for r in records}) == 90 and
            Counter(r['organization'] for r in records) == Counter(dict.fromkeys(ORGANIZATIONS, 10)),
            'Regional relationship inventory drift')
    counts = manifest['counts']
    actual = {'relationship_records': len(records), 'original_documents': len(records),
              'source_documents': len(new_docs), 'counterpart_placements': len(new_docs) - len(records),
              'messages': len(new_mail), 'calendars': len(new_events), 'business_table_rows': 12,
              'retained_copies': sum(contacts[k]['employer'] in PRINCIPALS
                                     for m in new_mail.values() for k in [m['from']] + m['to']),
              'distinct_message_bodies': len({m['body'] for m in new_mail.values()}),
              'messages_by_relationship': dict(Counter(r['organization'] for r in records
                                                       for _ in r['messages']))}
    require(counts == actual and (len(new_mail), len(new_docs), len(new_events)) == (319, 95, 3),
            'Regional asset or retained-copy count drift')
    adjustment = manifest['volume_adjustment']
    require(adjustment['delivered'] == len(new_mail) and
            adjustment['initial_allocation'] - adjustment['unallocated_difference'] == len(new_mail) and
            adjustment['milestone_messages_after'] - adjustment['milestone_messages_before'] == len(new_mail),
            'Regional volume adjustment does not reconcile')
    seen_mail, seen_docs, seen_events = [], [], []
    for r in records:
        ref = r['id']
        account = accounts[r['organization']]
        require(r['account_id'] == account['account_id'] and
                r['agreement_id'] == account['agreement_id'], 'Regional account join drift')
        participants = set(r['participants'])
        require(len(participants) == len(r['participants']) and r['author'] in participants,
                'Regional correspondent inventory drift')
        employers = {contacts[k]['employer'] for k in participants}
        allowed = {account['holder'], r['organization']}
        if ref == 'rr-veybridge-08':
            allowed.add('ardenvale')  # The accepted three-party programme conversation.
        require(employers <= allowed, 'Unrelated regional correspondent')
        if r['private']:
            require(len(employers) == 1 and employers <= PRINCIPALS, 'Private regional thread escaped')
        primary = new_docs[ref]
        text = document_text(root, primary)
        visible = html.unescape(re.sub(r'<[^>]+>', ' ', text))
        numbers = re.sub(r'(?<=\d),(?=\d)', '', visible)
        require(len(visible.split()) >= 95, 'Regional record lacks its substantive content')
        require(primary['employer'] in PRINCIPALS, 'Supplier infrastructure introduced')
        for did in r['documents']:
            d = new_docs[did]
            require(d['audience'] == 'restricted' and set(d['reader_keys']) == {
                k for k in participants if contacts[k]['employer'] == d['employer']
            } and d['reader_keys'], 'Regional document readers widened or lost')
            require(d['text'] == primary['text'] and d['published_at'] == primary['published_at']
                    and d['media_type'] == primary['media_type'], 'Regional counterpart bytes differ')
            require(datetime.fromisoformat(d['published_at']) <= snapshot, 'Regional document after snapshot')
            seen_docs.append(did)
        if primary['media_type'] == 'text/html':
            page = Page()
            page.feed(text)
            page.close()
            require(not page.stack and all(page.tags[t] == 1 for t in ('html', 'head', 'body', 'title', 'h1')),
                    'Incomplete regional HTML page')
        for source in r['source_documents']:
            original = by_doc[source['document']]
            require(digest(document_text(root, original)) == source['sha256'],
                    'Accepted regional document rewritten')
            require(original['published_at'] <= primary['published_at'], 'Regional source from the future')
        previous = r['previous_message']
        for mid in r['messages']:
            m = new_mail[mid]
            require({m['from'], *m['to']} == participants and m['from'] not in m['to']
                    and len(m['to']) == len(set(m['to'])), 'Regional message audience drift')
            require(m.get('reply_to') == previous, 'Regional reply ancestry drift')
            when = datetime.fromisoformat(m['date'])
            require(when <= snapshot, 'Regional message after snapshot')
            require(all(not contacts[k].get('start_date') or contacts[k]['start_date'] <= m['date'][:10]
                        for k in participants), 'Regional speaker predates employment')
            if previous:
                require(previous in by_mail and datetime.fromisoformat(by_mail[previous]['date']) < when,
                        'Regional reply predates its parent')
                parent_employers = {contacts[k]['employer'] for k in
                                    [by_mail[previous]['from']] + by_mail[previous]['to']}
                parent_owner = message_owners.get(previous)
                require(not parent_owner or not parent_owner['private'] or
                        participants <= set(parent_owner['participants']),
                        'Regional reply discloses a private conversation')
                require(parent_employers <= allowed and
                        (not r['private'] or parent_employers == employers),
                        'Regional reply crosses a private boundary')
            permitted = {ref}
            if mid == 'rr-belvarn-09-m2':
                permitted.add('a-billing-explanation')
            require(set(m.get('attachments', [])) <= permitted, 'Regional attachment leaks unrelated content')
            for aid in m.get('attachments', []):
                require(by_doc[aid]['published_at'] <= m['date'], 'Regional attachment from the future')
            previous = mid
            seen_mail.append(mid)
        require(ref in new_mail[r['messages'][1]].get('attachments', []),
                'Regional relationship record is not delivered')
        combined = '\n'.join([text, primary['path'], primary['title']] +
                             [new_mail[mid]['body'] + new_mail[mid]['subject'] for mid in r['messages']])
        require(not re.search(r'(?i)ground.control|author.only|scenario.overlay|issue\s*#?\s*132|'
                              r'assets/narrative|docs/narrative|content-ownership|f208f42', combined),
                'Regional authoring metadata leaked')
        facts = r['facts']
        if r['kind'] == 'terms':
            term_numbers = re.sub(r'(?<=\d),(?=\d)', '', account['terms'])
            agreed = {Decimal(v) for v in re.findall(r'USD\s+(\d+(?:\.\d+)?)', term_numbers)}
            stated = {Decimal(v) for v in re.findall(r'USD\s+(\d+(?:\.\d+)?)', numbers)}
            require(stated and stated <= agreed, 'Regional agreement amount changed')
            if ref in {'rr-arwc-04', 'rr-rillhaven-03', 'rr-orrenvale-05',
                       'rr-orrenvale-08', 'rr-veybridge-10'}:
                end = datetime.fromisoformat(account['end'])
                require(f'{end.day} {end:%B %Y}' in text, 'Regional agreement end date changed')
        if r['kind'] == 'contractor':
            job = jobs[facts['job'] - 1]
            require(job['supplier'] == r['organization'], 'Regional contractor supplier mismatch')
            require({s['document'] for s in r['source_documents']} == {
                f"me-contractor-report-{facts['job']:03d}", f"me-contractor-receipt-{facts['job']:03d}"},
                'Regional contractor evidence join drift')
            require(all(job[k] in text for k in ('purchase_order', 'service_report')),
                    'Regional contractor reference changed')
            stated = re.findall(r'USD\s+(\d+(?:\.\d+)?)', numbers)
            require(all(Decimal(v) == Decimal(job['amount_usd']) for v in stated),
                    'Regional accepted service amount changed')
        if r['kind'] == 'bulk':
            activities = account['settled_activity']
            total = sum(a['quantity'] for a in activities)
            amount = sum(Decimal(a['accepted_amount_usd']) for a in activities)
            ceiling = 20000 if r['organization'] == 'merewick' else 7500
            if 'activity' in facts:
                item = next(a for a in activities if a['reference'] == facts['activity'])
                require(facts['quantity'] == item['quantity'] and
                        Decimal(facts['amount']) == Decimal(item['accepted_amount_usd']),
                        'Regional accepted delivery changed')
                require(item['reference'] in text and str(item['quantity']) in numbers and
                        item['accepted_amount_usd'] in numbers and item['date'] <= primary['published_at'][:10],
                        'Regional delivery prose or chronology drift')
            if 'total_quantity' in facts:
                require(facts['total_quantity'] == total and Decimal(facts['total_amount']) == amount
                        and facts['headroom'] == ceiling - total, 'Regional ceiling arithmetic drift')
                require(str(total) in numbers and f'{amount:.2f}' in numbers,
                        'Regional aggregate prose differs from accepted activity')
        if 'case' in facts:
            source = document_text(root, by_doc['rb-case-document-0001'])
            start, end, quantity = map(int, re.search(
                r'actual readings (\d+) and (\d+).*difference is (\d+) m3', source).groups())
            require(facts == {'case': 'ARWC-BC-2026-0001', 'reading_start': start,
                             'reading_end': end, 'quantity': quantity} and end - start == quantity,
                    'Regional retail reading arithmetic drift')
            require(all(str(v) in numbers for v in (start, end, quantity)) and
                    'ARWC-M-048751' in text and 'ARWC-INV-2026-048481' in text,
                    'Regional retail explanation changed')
        if r['kind'] == 'batch':
            h = purchases[facts['history']]
            pages = h['lines'][1]['quantity']
            require(h['supplier'] == 'ternwick' and h['amount_cents'] == 18000 + pages * 42,
                    'Regional scanning charge arithmetic drift')
            require(all(value in numbers for value in (h['batch_reference'], str(pages),
                        f"{Decimal(h['amount_cents']) / 100:.2f}", h['records_batch_acceptance'])),
                    'Regional scanning reference, page count or amount changed')
        if r['kind'] == 'batch-register':
            batches = [h for h in purchases.values() if h['supplier'] == 'ternwick' and h['batch_reference']]
            require(facts['histories'] == [h['id'] for h in batches] and
                    facts['total_pages'] == sum(h['lines'][1]['quantity'] for h in batches) and
                    facts['total_cents'] == sum(h['amount_cents'] for h in batches),
                    'Regional batch register total drift')
            for h in batches:
                row = (f"{h['batch_reference']} | {h['lines'][1]['quantity']} | "
                       f"{Decimal(h['amount_cents']) / 100:.2f} | {h['received_at'][:10]} | {h['paid_at'][:10]}")
                require(row in text and h['paid_at'] < primary['published_at'],
                        'Regional batch register row or payment chronology drift')
        if 'calendar' in r:
            e = new_events[r['calendar']]
            require(e['status'] == 'TENTATIVE' and set(e['responses'].values()) == {'TENTATIVE'} and
                    not e.get('attendance') and not e.get('minutes'), 'Regional future call falsely completed or confirmed')
            require({e['organizer'], *e['attendees']} == participants and e['employer'] == 'arwc'
                    and set(e['responses']) == set(e['attendees']), 'Regional calendar audience drift')
            require(e['created_at'] == e['updated_at'] == new_mail[r['messages'][1]]['date']
                    and snapshot < datetime.fromisoformat(e['start']) < datetime.fromisoformat(e['end']),
                    'Regional appointment chronology drift')
            start, end = datetime.fromisoformat(e['start']), datetime.fromisoformat(e['end'])
            require(f'{start.day} {start:%B}, {start:%H:%M}–{end:%H:%M}' in visible and
                    (end - start).total_seconds() == 1200,
                    'Regional calendar differs from the proposed time')
            for other in calendars:
                if other['id'] == e['id'] or other['status'] == 'CANCELLED':
                    continue
                busy = {other['organizer']} | {p for p in other['attendees']
                        if other.get('responses', {}).get(p) != 'DECLINED'}
                require(not (participants & busy and max(e['start'], other['start']) < min(e['end'], other['end'])),
                        'Regional appointment conflicts with an accepted calendar')
            seen_events.append(e['id'])
    for seen, expected, label in ((seen_mail, new_mail, 'mail'), (seen_docs, new_docs, 'documents'),
                                  (seen_events, new_events, 'calendars')):
        require(len(seen) == len(set(seen)) and set(seen) == set(expected),
                'Regional ownership is incomplete or duplicated: ' + label)
    require(by_event['commercial-arwc-reference-hold']['status'] == 'TENTATIVE' and
            by_event['commercial-arwc-reference-hold']['start'] == '2026-09-29T10:00:00-04:00',
            'Accepted reference hold changed')
    require(by_event['rillhaven-workshop']['start'] == '2026-09-24T10:00:00-04:00' and
            by_event['rillhaven-workshop']['organizer'] == 'talia', 'Accepted workshop changed')
    require(new_mail['rr-arwc-10-m1']['reply_to'] == 'cm-1376', 'Latest reference reply lost')
    require(new_mail['rr-belvarn-09-m2']['attachments'] == ['rr-belvarn-09', 'a-billing-explanation'],
            'Accepted billing explanation not delivered')
    worksheet = document_text(root, by_doc['rillhaven-workshop-example'])
    reminder = html.unescape(re.sub(r'<[^>]+>', ' ', new_docs['rr-rillhaven-09']['text']))
    for revision, state, reading in re.findall(r'\| RH-WORKSHOP-026 \| (r\d) \| (\w+) \| (\d+) units', worksheet):
        require(f'{revision} as {state} at {reading} units' in reminder,
                'Regional workshop reminder changes the issued example')
    return actual
