"""Validate customer disposition, versioned evidence, and private/public continuity."""
from collections import Counter
from datetime import datetime
import csv
import hashlib
import io
import json
import re
import yaml


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def text(root, document):
    return document['text'] if 'text' in document else (root / document['file']).read_text()


def check_customer_followup(root, identity, roster, mail, documents, calendars):
    def load(name):
        return yaml.safe_load((root / 'authoring' / name).read_text())
    manifest = load('customer-followup.yaml')
    intake = {c['id']: c for c in load('support-intake.yaml')['cases']}
    quality = {q['id']: q for q in load('product-quality.yaml')['records']}
    network = {o['key']: o for o in load('business-network.yaml')['organizations']}
    by_doc = {d['id']: d for d in documents}
    by_mail = {m['id']: m for m in mail}
    by_calendar = {e['id']: e for e in calendars}
    new_mail = {m['id']: m for m in mail if m['story'] == 'customer-followup'}
    new_docs = {d['id']: d for d in documents if d['story'] == 'customer-followup'}
    contacts = identity['people'] | identity['correspondents'] | {p['key']: p for p in roster}
    snapshot = datetime.fromisoformat(identity['snapshot'])
    records = manifest['records']
    fixes = {f['id']: f for f in manifest['engineering_resolutions']}
    releases = {r['id']: r for r in manifest['releases']}
    require(manifest['snapshot'] == identity['snapshot'] and
            manifest['required_base'] == {'repository_commit': 'fbf4cdc', 'support_commit': 'aa48fa8',
             'product_quality_commit': '1ac57ee', 'release_platform_commit': 'a8b7a61'},
            'Follow-up accepted base drift')
    require(len(records) == len({r['case_id'] for r in records}) == 290
            and len(fixes) == 10 and len(releases) == 5,
            'Follow-up business record inventory drift')
    require(len(new_mail) == manifest['counts']['messages'] == 2504
            and len(new_docs) == manifest['counts']['documents'] == 310,
            'Follow-up content inventory drift')
    require(Counter(r['status'] for r in records) == manifest['counts']['states'],
            'Follow-up disposition count drift')
    require(sum(sum(contacts[k]['employer'] in {'keplerops', 'arwc'} for k in [m['from']] + m['to'])
                for m in new_mail.values()) == manifest['counts']['retained_copies'] == 3850,
            'Follow-up retained copy count drift')
    require([r['case_id'] for r in records if r['kind'] == 'child_followup'] ==
            [f'SUP-2026-{n:04d}' for n in range(501, 561)], 'Child case identifiers drift')
    safe_documents = {k['current_document'] for k in manifest['knowledge']}
    safe_documents.update(d for r in records for d in r['documents']
                          if d.startswith(('handover-', 'customer-', 'decision-')))
    safe_documents.update({'k-workshop-outline-v3', 'rillhaven-workshop-example',
                           'rillhaven-workshop-invitation'})
    require(set(manifest['customer_safe_documents']) == safe_documents,
            'Customer-safe attachment inventory widened')

    # Old article versions still supply the old attachments. Only revision 2 is new.
    require(len(manifest['knowledge']) == 24, 'Knowledge revision inventory drift')
    for article in manifest['knowledge']:
        previous = by_doc[article['previous_document']]
        current = by_doc[article['current_document']]
        require(sha(text(root, previous)) == article['previous_sha256'],
                'Historical knowledge attachment changed')
        require(article['article_id'] == previous['id'] and article['revision'] == 2
                and current['id'] == previous['id'] + '-v2'
                and current['published_at'] == article['published_at']
                and text(root, current).startswith(text(root, previous).rstrip()),
                'Knowledge version relationship drift')

    linked_assessments = []
    for fix in fixes.values():
        decisions = [quality[k] for k in fix['previous_quality_records']]
        linked_assessments.extend(fix['assessments'])
        require([q['engineering_work'] for q in decisions] == fix['assessments']
                and [q['support_case'] for q in decisions] == fix['support_cases']
                and [q['decision'] for q in decisions] == ['deferred', 'deferred', 'declined']
                and all(q['topic'] == fix['topic'] for q in decisions),
                'Fix does not join its earlier assessments')
        require(all(datetime.fromisoformat(q['decided_at']) < datetime.fromisoformat(fix['opened_at'])
                    < datetime.fromisoformat(fix['accepted_at']) <= snapshot for q in decisions),
                'Fix acceptance predates its assessment or correction')
        require(fix['product_version'] == '4.9.2' and fix['revision'].endswith('-r3'),
                'Follow-up fix product/revision drift')
        delta = by_doc[fix['id'].lower() + '-delta']
        fixture = by_doc[fix['id'].lower() + '-fixtures']
        require(sha(text(root, delta)) == fix['delta_sha256']
                and sha(text(root, fixture)) == fix['fixture_sha256'], 'Fix evidence bytes drift')
        delta_data = json.loads(text(root, delta))
        require(delta_data['revision'] == fix['revision'] and delta_data['repository'] == fix['repository']
                and delta_data['behavior'] == fix['topic'], 'Fix delta identity drift')
        rows = list(csv.DictReader(io.StringIO(text(root, fixture))))
        require(rows == fix['fixture_rows'] and len(rows) == 3
                and {row['check'] for row in rows} ==
                    {'reported-path', 'unchanged-ordinary-path', 'reader-boundary'}
                and all(row['work_item'] == fix['id'] and row['revision'] == fix['revision']
                        and row['observed'] == row['expected'] and row['result'] == 'PASS' for row in rows)
                and rows[0]['before'] != rows[0]['observed'], 'Fix lacks bounded passing evidence')
        decision = by_doc[fix['quality_id'].lower() + '-decision']
        require(decision['published_at'] == fix['accepted_at'] and fix['fixture_sha256'] in text(root, decision),
                'Quality decision does not bind its evidence')
    require(Counter(linked_assessments) == Counter(f'ENG-2026-{n:03d}' for n in range(1, 31)),
            'Engineering assessment coverage drift')
    released_fixes = []
    for release in releases.values():
        artifact = text(root, by_doc[release['manifest_document']])
        require(sha(artifact) == release['manifest_sha256'], 'Release manifest bytes drift')
        payload = json.loads(artifact)
        require(payload['release'] == release['id'] and payload['product_version'] == '4.9.2'
                and payload['repository'] == release['repository'], 'Follow-up release identity drift')
        linked = [fixes[k] for k in release['changes']]
        require(payload['changes'] == [{'work_item': f['id'], 'revision': f['revision'],
                'quality_id': f['quality_id'], 'accepted_at': f['accepted_at'],
                'fixture_sha256': f['fixture_sha256'], 'delta_sha256': f['delta_sha256']} for f in linked],
                'Release accepted-evidence join drift')
        times = [datetime.fromisoformat(release[k]) for k in
                 ('approved_at', 'built_at', 'published_at', 'qualified_at')]
        require(all(datetime.fromisoformat(f['accepted_at']) < times[0] for f in linked)
                and all(a < b for a, b in zip(times, times[1:])) and times[-1] <= snapshot,
                'Release precedes acceptance or successful build')
        log = json.loads(text(root, by_doc[release['events_document']]))
        require([e['at'] for e in log] == [release[k] for k in
                ('approved_at', 'built_at', 'published_at', 'qualified_at')]
                and [e['result'] for e in log] == ['APPROVED', 'PASS', 'PUBLISHED', 'MATCH']
                and all(e['sha256'] == release['manifest_sha256'] for e in log[2:]),
                'Release event/readback drift')
        released_fixes.extend(release['changes'])
    require(Counter(released_fixes) == Counter(fixes.keys()), 'Fix omitted or duplicated in releases')

    seen_mail = set()
    def check_thread(record, boundary, thread, expected_previous=None):
        current = thread['previous_last']
        require(current == expected_previous, 'Follow-up lost or bridged its original thread')
        for mid in thread['added']:
            require(mid in new_mail and mid not in seen_mail, 'Duplicate or absent follow-up message')
            m = by_mail[mid]
            require(m.get('reply_to') == current, 'Follow-up reply chain drift')
            if current:
                require(datetime.fromisoformat(by_mail[current]['date']) < datetime.fromisoformat(m['date']),
                        'Follow-up reply precedes its parent')
            employers = {contacts[k]['employer'] for k in [m['from']] + m['to']}
            if boundary == 'internal':
                require(employers == {'keplerops'}, 'Customer copied into private follow-up')
            else:
                require(employers == {'keplerops', record['organization']},
                        'Customer follow-up crossed account boundary')
            for attachment in m.get('attachments', []):
                d = by_doc[attachment]
                require(datetime.fromisoformat(d['published_at']) <= datetime.fromisoformat(m['date']),
                        'Follow-up attachment from future')
                if boundary == 'customer_visible':
                    require(attachment in manifest['customer_safe_documents'],
                            'Internal follow-up material attached to customer reply')
            require(datetime.fromisoformat(m['date']) <= snapshot, 'Follow-up mail after snapshot')
            seen_mail.add(mid); current = mid
        require(current == thread['last'], 'Follow-up last-message pointer drift')

    for record in records:
        cid = record['case_id']; parent = intake.get(cid)
        org = network[record['organization']]
        require(org['account_id'] == record['account_id']
                and record['customer_contact'] in org['contact_keys'], 'Follow-up account/contact join drift')
        require(record['owner'] in contacts and contacts[record['owner']]['employer'] == 'keplerops',
                'Follow-up owner drift')
        start, end = map(datetime.fromisoformat, (record['opened_at'], record['last_activity']))
        require(start < end <= snapshot, 'Follow-up chronology exceeds snapshot')
        require(record['parent_case'] is None if parent else record['parent_case'] in intake,
                'Child case lacks stable parent')
        if parent:
            require(record['previous_status'] == parent['status']
                    and record['previous_activity'] == parent['last_activity']
                    and datetime.fromisoformat(parent['last_activity']) < start,
                    'Follow-up rewrote or predates intake history')
        else:
            require(intake[record['parent_case']]['organization'] == record['organization']
                    and record['kind'] == 'child_followup' and record['customer_record']
                    and record['customer_revision'] == 'r1', 'Child case identity/scope drift')
        for boundary, thread in record['threads'].items():
            check_thread(record, boundary, thread, parent['threads'][boundary]['last'] if parent else None)
        require(set(record['messages']) == {mid for thread in record['threads'].values() for mid in thread['added']},
                'Follow-up message inventory detached from threads')
        require(max(by_mail[mid]['date'] for mid in record['messages']) == record['last_activity'],
                'Follow-up activity bounds drift')
        current = by_doc[record['case_document']]
        current_text = text(root, current)
        require(current['published_at'] == record['last_activity'] and record['status'].replace('_', ' ') in current_text
                and record['outcome'] in current_text and record['next_action'] in current_text,
                'Current case document disagrees with disposition')
        if parent:
            # The existing object now shows its latest state and the exact earlier narrative.
            require(record['case_document'] == parent['case_document'], 'Existing case was cloned')
            earlier = current_text.split('## Earlier intake, retained as recorded\n\n', 1)[1]
            restored = current_text.split('\n', 1)[0] + '\n' + earlier.replace('\n### ', '\n## ')
            require(sha(restored) == record['previous_document_sha256'], 'Earlier case narrative changed')
        closed = record['status'] in {'closed_verified', 'closed_support', 'closed_declined',
                                     'handover_accepted', 'followup_closed'}
        require((record['closed_at'] is not None and start < datetime.fromisoformat(record['closed_at']) <= end)
                if closed else record['closed_at'] is None, 'Follow-up closure state drift')
        if closed and record['status'] != 'closed_declined':
            require(record['verified_at'] and start < datetime.fromisoformat(record['verified_at']) <=
                    datetime.fromisoformat(record['closed_at']),
                    'Closure lacks customer verification')
        if closed:
            require('**Closed:** ' + record['closed_at'] in current_text,
                    'Current case closure timestamp drift')
            notices = [by_mail[mid] for mid in record['messages']
                       if by_mail[mid]['from'] == 'k_case_updates']
            require(all(record['status'] in m['body'] and datetime.fromisoformat(record['closed_at']) <=
                        datetime.fromisoformat(m['date']) for m in notices),
                    'Closure notice precedes recorded closure')
        if record['kind'] == 'child_followup':
            require(record['customer_record'] in current_text and record['expected_result'] in current_text
                    and record['observed_result'] == (record['expected_result'] if closed else None),
                    'Child follow-up lacks separate batch evidence')
        if record['kind'] == 'planned_work':
            event = by_calendar[record['appointment_id']]
            require(record['status'] == 'planned' and record['work_occurred_at'] is None
                    and record['verified_at'] is None and datetime.fromisoformat(event['start']) > snapshot,
                    'Future appointment claimed completed')
        elif record['kind'] == 'accepted_handover':
            require(datetime.fromisoformat(record['work_occurred_at']) < start,
                    'Handover accepted before work occurred')
        elif record['kind'] == 'reopening':
            require(parent['closed_at'] and datetime.fromisoformat(parent['closed_at']) <
                    datetime.fromisoformat(record['reopened_at']) == start and record['reopen_reason'],
                    'Reopening lacks earlier closure or new cause')
        elif record['kind'] == 'engineering_followup':
            previous = quality[record['previous_quality_id']]
            require(previous['support_case'] == cid and previous['engineering_work'] == record['assessment_id'],
                    'Engineering follow-up decision join drift')
            require(previous['decision'] in {'deferred', 'declined'}, 'Unexpected earlier assessment state')
            fix = fixes[record['fix_id']]; release = releases[record['release_id']]
            require(cid in fix['support_cases'] and fix['release_id'] == release['id']
                    and record['release_manifest_sha256'] == release['manifest_sha256'],
                    'Customer delivery uses unrelated release')
            require(datetime.fromisoformat(release['qualified_at']) < start <
                    datetime.fromisoformat(record['authorized_at']) < datetime.fromisoformat(record['delivered_at']) < end,
                    'Customer delivery lacks prior acceptance, release, or authorization')
            delivery = json.loads(text(root, by_doc[record['delivery_document']]))
            require(delivery['case'] == cid and delivery['account'] == record['account_id']
                    and delivery['revision'] == fix['revision'] and delivery['to_version'] == '4.9.2'
                    and delivery['manifest_sha256'] == release['manifest_sha256']
                    and delivery['authorized_at'] == record['authorized_at']
                    and delivery['selected_at'] == record['delivered_at']
                    and delivery['customer_verified_at'] == record['verified_at'],
                    'Customer delivery artifact drift')
            require(record['status'] in {'closed_verified', 'awaiting_verification'}
                    and bool(record['verified_at']) == closed,
                    'Customer selection mistaken for verified closure')
            if closed:
                require(datetime.fromisoformat(record['delivered_at']) < datetime.fromisoformat(record['verified_at']),
                        'Customer verification precedes delivery')
    for record in manifest['engineering_threads']:
        check_thread(record, 'internal', record['threads']['internal'])

    workshop = manifest['workshop']
    workshop['organization'] = 'rillhaven'
    check_thread(workshop, 'internal', workshop['threads']['internal'], 'k-rehearsal-1')
    check_thread(workshop, 'customer_visible', workshop['threads']['customer_visible'])
    require(seen_mail == set(new_mail), 'Unjoined customer-follow-up mail')
    event = by_calendar[workshop['calendar_id']]
    require(workshop['status'] == 'prepared_future' and workshop['calendar_id'] == 'rillhaven-workshop'
            and event['start'] == workshop['session_start'] == '2026-09-24T10:00:00-04:00'
            and event['end'] == workshop['session_end'] == '2026-09-24T11:30:00-04:00'
            and event['status'] == 'CONFIRMED' and event['organizer'] == workshop['lead'] == 'talia'
            and workshop['support_questions'] == 'maya' and set(event['attendees']) == {'maya', 'rillhaven'},
            'Rillhaven identity, date, or agreed roles drift')
    invitation = text(root, by_doc[workshop['invitation_document']])
    require(invitation.encode() == (root / 'generated/calendars/rillhaven-workshop.ics').read_bytes(),
            'Workshop invitation differs from retained calendar')
    require(workshop['current_outline'] == 'k-workshop-outline-v3'
            and workshop['previous_outline'] == 'k-workshop-outline', 'Workshop outline version chain drift')
    require(not any('minutes' in d['id'] or 'attendance' in d['id'] for d in new_docs.values()
                    if 'rillhaven' in d['id'] or 'workshop' in d['id']),
            'Future workshop has minutes or attendance records')
    visible = '\n'.join(text(root, d) + d.get('path', '') for d in new_docs.values()) + '\n'.join(
        m['body'] + m['subject'] for m in new_mail.values())
    require(not re.search(r'cinder.typhoon|issue[ -]118|author.only|scenario.overlay|'
                          r'opening snapshot|TEN-ARWC-047|FLK-7\.4\.2|SUP-2841|flag\{', visible, re.I),
            'Follow-up content leaks authoring or campaign evidence')
    return manifest['counts']
