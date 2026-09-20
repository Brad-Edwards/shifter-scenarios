"""Validate commercial authority, billing, capacity, and correspondence boundaries."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
import calendar
import csv
import hashlib
import io
import json
import re
import yaml


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def months(day, count):
    month = day.month - 1 + count
    year, month = day.year + month // 12, month % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def check_commercial(root, identity, roster, mail, documents, calendars):
    manifest = yaml.safe_load((root / 'authoring/commercial.yaml').read_text())
    network = yaml.safe_load((root / 'authoring/business-network.yaml').read_text())
    accounts = {o['key']: o for o in network['organizations'] if o['kind'] == 'utility_customer'}
    contacts = identity['people'] | identity['correspondents'] | {p['key']: p for p in roster}
    by_mail = {m['id']: m for m in mail}
    by_doc = {d['id']: d for d in documents}
    by_event = {e['id']: e for e in calendars}
    new_mail = {m['id']: m for m in mail if m['story'] == 'commercial'}
    new_docs = {d['id']: d for d in documents if d.get('story') == 'commercial'}
    new_events = {e['id']: e for e in calendars if e.get('story') == 'commercial'}
    calendar_items = {d['name']: d for d in json.loads(
        (root / 'generated/packages/keplerops-documents.json').read_text())['documents']
        if d['media_type'] == 'text/calendar'}
    records = manifest['records']
    snapshot = datetime.fromisoformat(identity['snapshot'])
    commercial = {p['key'] for p in roster if p['employer'] == 'keplerops' and p['department'] == 'Commercial'}
    require(manifest['snapshot'] == identity['snapshot'] and manifest['required_base'] == {
        'repository_commit': '8b75ce5', 'accepted_business_commit': 'ef9c89f', 'accepted_followup_commit': 'c34753e'},
        'Commercial accepted base drift')
    require(set(manifest['commercial_staff']) == commercial and len(commercial) == 6,
            'Commercial staff differs from accepted roster')
    require(len(records) == len({r['id'] for r in records}) == 60 and len(accounts) == 12
            and Counter(r['organization'] for r in records) == Counter({key: 5 for key in accounts}),
            'Commercial history/account inventory drift')
    require([r['id'] for r in records] == [f'COM-2026-{i:03}' for i in range(1, 61)],
            'Commercial history identity drift')
    require(len(new_mail) == manifest['counts']['messages'] == 1376
            and len(new_docs) == manifest['counts']['documents'] == 251
            and len(new_events) == manifest['counts']['calendars'] == 11,
            'Commercial asset inventory drift')
    require(Counter(r['status'] for r in records) == manifest['counts']['states'],
            'Commercial disposition inventory drift')
    require(sum(sum(contacts[k]['employer'] in {'arwc', 'keplerops'} for k in [m['from']] + m['to'])
                for m in new_mail.values()) == manifest['counts']['retained_copies'] == 2204,
            'Commercial retained-copy count drift')
    safe, private = set(manifest['customer_safe_documents']), set(manifest['private_documents'])
    require(not safe & private and safe | private == set(new_docs), 'Commercial document visibility inventory drift')
    allowed_staff = commercial | {'leah', 'kwm056', 'kwm057'} | {a['owner'] for a in accounts.values()}
    for d in new_docs.values():
        require(d['audience'] == 'restricted' and d['reader_keys'], 'Commercial document is not restricted')
        allowed = allowed_staff if d['employer'] == 'keplerops' else {'theo', 'clara', 'priya', 'luc'}
        require(set(d['reader_keys']) <= allowed, 'Unrelated commercial document reader')
        if d['id'].endswith('-arwc'):
            original = by_doc[d['id'].removesuffix('-arwc')]
            require(d['id'] in safe and d['text'] == original['text'] and d['published_at'] == original['published_at'],
                    'ARWC counterpart differs from agreed copy')
        if d['id'] in private:
            require(d['employer'] == 'keplerops', 'Private commercial document exported')
        require(datetime.fromisoformat(d['published_at']) <= snapshot, 'Commercial document after snapshot')

    seen = set()
    accepted_states = {'accepted_renewal', 'accepted_amendment', 'accepted_future', 'completed'}
    for r in records:
        account = accounts[r['organization']]
        require(r['account_id'] == account['account_id'] and r['agreement_id'] == account['agreement_id']
                and r['owner'] == account['commercial_owner'] and r['delivery_owner'] == account['owner']
                and r['contact'] in account['contact_keys'], 'Commercial account, owner, or contact join drift')
        require(set(r['documents']) <= set(new_docs), 'Missing commercial document')
        for boundary, thread in r['threads'].items():
            expected_parent = 'b-kepler-arwc-2' if r['id'] == 'COM-2026-005' and boundary == 'customer' else None
            require(thread['previous_last'] == expected_parent, 'Commercial thread lost or changed its original parent')
            previous = expected_parent
            for mid in thread['added']:
                require(mid in new_mail and mid not in seen, 'Missing or repeated commercial message')
                message = by_mail[mid]
                require(message.get('reply_to') == previous, 'Commercial reply crosses or detaches a thread')
                if previous:
                    require(datetime.fromisoformat(by_mail[previous]['date']) < datetime.fromisoformat(message['date']),
                            'Commercial reply predates its parent')
                expected_orgs = {'keplerops', r['organization']} if boundary in {'customer', 'scheduling'} else {
                    'arwc'} if boundary == 'customer_staff_time' else {'keplerops'}
                require({contacts[k]['employer'] for k in [message['from']] + message['to']} == expected_orgs,
                        'Commercial correspondence crosses audience boundary')
                for attachment in message.get('attachments', []):
                    d = by_doc[attachment]
                    require(datetime.fromisoformat(d['published_at']) <= datetime.fromisoformat(message['date']),
                            'Commercial attachment from future')
                    if boundary in {'customer', 'scheduling'}:
                        require(attachment in safe, 'Private commercial attachment sent to customer')
                    require(all(k in d['reader_keys'] for k in [message['from']] + message['to']
                                if contacts[k]['employer'] == d['employer']), 'Attachment recipient lacks document access')
                if boundary in {'customer', 'scheduling'}:
                    exposed = message['body'] + ''.join(by_doc[k]['text'] for k in message.get('attachments', []))
                    require(not any(marker in exposed for marker in ['Private planning note:', 'cost_per_hour_usd',
                                                                      'planned_contribution_usd']),
                            'Private commercial costing leaked into customer copy')
                require(datetime.fromisoformat(message['date']) <= snapshot, 'Commercial mail after snapshot')
                seen.add(mid)
                previous = mid
            require(thread['last'] == previous, 'Commercial last-message pointer drift')
        require(set(r['messages']) == {mid for t in r['threads'].values() for mid in t['added']},
                'Commercial messages detached from history')
        require(r['opened_at'] == min(by_mail[k]['date'] for k in r['messages'])
                and r['last_activity'] == max(by_mail[k]['date'] for k in r['messages']),
                'Commercial activity bound drift')
        accepted = r['status'] in accepted_states
        require(bool(r['accepted_at']) == accepted, 'Unaccepted commercial work claimed committed')
        if accepted:
            offer, signed = by_doc[r['offer_document']], by_doc[r['accepted_document']]
            require(offer['published_at'] < r['accepted_at'] == signed['published_at'] <= identity['snapshot']
                    and digest(offer['text']) in signed['text'] and r['offer_document'] in signed['text']
                    and '/s/ ' + contacts[r['contact']]['name'] in signed['text']
                    and '/s/ Leah Calder-Voss' in signed['text'], 'Accepted commercial version or authority drift')
            require(Decimal(r['accepted_amount_usd']) == Decimal(r['offered_amount_usd']),
                    'Accepted amount differs from signed offer')
        else:
            require(Decimal(r['accepted_amount_usd']) == 0 and r['billing_schedule'] is None
                    and not r['capacity_reservations'] and r['delivery_accepted_at'] is None,
                    'Draft, lost, or deferred work creates billing or delivery authority')
        if r['kind'] in {'renewal', 'account_review'}:
            fee = Decimal(account['terms'].split('USD ')[1].split(' annual')[0].replace(',', ''))
            require(Decimal(r['current_annual_fee_usd']) == fee and Decimal(r['current_quarterly_usd']) * 4 == fee
                    and r['current_term_end'] == account['end'], 'Standing commercial fee or term changed')
            if r['kind'] == 'renewal':
                start = date.fromisoformat(account['end']) + timedelta(days=1)
                require(r['next_term_start'] == start.isoformat()
                        and r['next_term_end'] == (months(start, 12) - timedelta(days=1)).isoformat(),
                        'Renewal overlaps or leaves gap after current term')
        if r['kind'] == 'amendment':
            require(Decimal(r['offered_amount_usd']) == 0 and not r['billing_schedule'],
                    'Administrative amendment invents a new fee')
        if r['kind'] == 'project':
            cost = by_doc[r['costing_document']]
            require(set(cost['reader_keys']) == {r['owner'], 'kwm047', 'kwm051'}, 'Private costing readers widened')
            rows = list(csv.DictReader(io.StringIO(cost['text'])))
            require(len(rows) == 2 and [x['version'] for x in rows] == ['draft-r1', 'offer-r2'], 'Costing versions drift')
            for row, extra in zip(rows, (4, 0)):
                hours = Decimal(row['hours'])
                fee, estimated = hours * Decimal(row['rate_usd']), hours * Decimal(row['cost_per_hour_usd'])
                require(hours == r['hours'] + extra and Decimal(row['rate_usd']) == Decimal(r['rate_usd']) == 150
                        and Decimal(row['cost_per_hour_usd']) == 90
                        and Decimal(row['fee_usd']) == fee and Decimal(row['planned_cost_usd']) == estimated
                        and Decimal(row['planned_contribution_usd']) == fee - estimated,
                        'Commercial pricing arithmetic drift')
                proposal = by_doc[r['draft_document'] if extra else r['offer_document']]['text']
                require(f'Offered service amount: USD {fee:,.2f}.' in proposal
                        and f'Fixed service fee USD {fee:,.2f} for {int(hours)} hours' in proposal,
                        'Proposal prose differs from pricing worksheet')
            require(Decimal(rows[1]['fee_usd']) == Decimal(r['offered_amount_usd']), 'Offer differs from pricing worksheet')
            if accepted:
                require(r['accepted_at'][:10] < r['work_start'] <= r['work_end'], 'Delivery begins before accepted order')
                event = by_event[r['calendar_id']]
                require(event['start'][:10] == r['work_end'] and event['organizer'] == r['delivery_owner']
                        and event['status'] == 'CONFIRMED', 'Commercial handover calendar drift')
                require(sum(x['new_project_hours'] for x in r['capacity_reservations']) == r['hours'],
                        'Accepted project lacks full reserved effort')
            if r['status'] == 'completed':
                require(r['initial_disposition'] == 'accepted_order'
                        and 'Disposition: accepted_order' in by_doc[r['decision_document']]['text']
                        and r['outcome'] not in by_doc[r['decision_document']]['text'],
                        'Project negotiation claims delivery complete')
                require(r['work_end'] < r['delivery_accepted_at'] <= identity['snapshot'], 'Completed project lacks dated acceptance')
                handover, artifact = by_doc[r['handover_document']], by_doc[r['deliverable_document']]
                require(handover['published_at'] == r['delivery_accepted_at'] and digest(artifact['text']) in handover['text']
                        and list(csv.DictReader(io.StringIO(artifact['text']))) ==
                        [{k: str(v) for k, v in row.items()} for row in r['sample_rows']],
                        'Accepted handover lost its delivered evidence')
            elif r['status'] == 'accepted_future':
                require(r['work_start'] > snapshot.date().isoformat() and r['delivery_accepted_at'] is None
                        and 'handover_document' not in r, 'Future commercial work claimed completed')
        if r['calendar_id']:
            event = by_event[r['calendar_id']]
            invitation = by_doc[r['invitation_document']]['text']
            require(invitation == calendar_items[event['id']]['text'],
                    'Commercial invitation differs from calendar bytes')
            require(by_doc[r['invitation_document']]['published_at'] == event['created_at'], 'Invitation date drift')
    require(seen == set(new_mail), 'Unjoined commercial messages')
    require(commercial <= {m['from'] for m in new_mail.values()}, 'Commercial employee has no authored voice')

    # Recompute every remaining standing-contract instalment from the accepted book.
    register = []
    require(len(manifest['billing_schedules']) == 24, 'Commercial billing schedule inventory drift')
    for schedule in manifest['billing_schedules']:
        r = next(r for r in records if r['id'] == schedule['record'])
        account = accounts[r['organization']]
        require(schedule['account_id'] == r['account_id'], 'Billing schedule belongs to another account')
        rows = schedule['rows']
        if schedule['kind'] == 'existing_service':
            day = date.fromisoformat(account['effective'])
            while day <= snapshot.date():
                day = months(day, 3)
            expected = []
            while day <= date.fromisoformat(account['end']):
                expected.append((day.isoformat(), min(months(day, 3) - timedelta(days=1), date.fromisoformat(account['end'])).isoformat()))
                day = months(day, 3)
            require(schedule['authority'] == account['agreement_id'] and schedule['accepted_at'] is None
                    and [(x['service_from'], x['service_to']) for x in rows] == expected
                    and all(x['billing_date'] == x['service_from'] and Decimal(x['amount_usd']) ==
                            Decimal(r['current_quarterly_usd']) for x in rows), 'Standing billing schedule or amount drift')
        else:
            require(r['status'] in accepted_states and schedule['authority'] == r['accepted_document']
                    and schedule['accepted_at'] == r['accepted_at']
                    and sum(Decimal(x['amount_usd']) for x in rows) == Decimal(r['accepted_amount_usd']),
                    'Billing lacks matching accepted commercial authority')
            require(list(csv.DictReader(io.StringIO(by_doc[schedule['document']]['text']))) == rows,
                    'Billing schedule bytes disagree with its authority register')
            if schedule['kind'] == 'renewal':
                start = date.fromisoformat(r['next_term_start'])
                require(len(rows) == 4 and all(x['billing_date'] == months(start, 3 * i).isoformat()
                        and x['service_from'] == x['billing_date']
                        and x['service_to'] == (months(start, 3 * i + 3) - timedelta(days=1)).isoformat()
                        and Decimal(x['amount_usd']) * 4 == Decimal(r['accepted_amount_usd'])
                        for i, x in enumerate(rows)), 'Renewal instalment arithmetic or period drift')
            else:
                require(schedule['kind'] == 'project' and len(rows) == 2
                        and all(Decimal(x['amount_usd']) * 2 == Decimal(r['accepted_amount_usd']) for x in rows)
                        and rows[0]['trigger_at'] == r['accepted_at'] and rows[0]['state'] == 'authorized'
                        and rows[0]['billing_date'] == r['accepted_at'][:10], 'Project order billing trigger drift')
                require(rows[1]['trigger_at'] == (r['delivery_accepted_at'] or '')
                        and rows[1]['state'] == ('authorized' if r['delivery_accepted_at'] else 'conditional')
                        and rows[1]['billing_date'] == (r['delivery_accepted_at'][:10] if r['delivery_accepted_at'] else ''),
                        'Undelivered project becomes unconditional billing')
        for i, row in enumerate(rows, 1):
            require(row['account'] == r['account_id'] and row['invoice_status'] == 'not evidenced here',
                    'Billing identity drift or invented invoice/payment')
            register.append({'schedule': schedule['id'], 'line': str(i), 'record': schedule['record'],
                'account': schedule['account_id'], 'authority': schedule['authority'], 'kind': schedule['kind'],
                'billing_date': row.get('billing_date', ''), 'service_from': row.get('service_from', ''),
                'service_to': row.get('service_to', ''), 'amount_usd': row['amount_usd'],
                'state': row.get('state', 'authorized'), 'trigger': row.get('milestone', row.get('trigger', '')),
                'trigger_at': row.get('trigger_at', ''), 'invoice_status': 'not evidenced here'})
    require(len(register) == manifest['counts']['billing_lines'] == 67
            and list(csv.DictReader(io.StringIO(by_doc[manifest['billing_register']]['text']))) == register,
            'Finance register differs from authoritative schedules')
    require(sum(Decimal(r['accepted_amount_usd']) for r in records) ==
            Decimal(manifest['counts']['accepted_new_amount_usd']) == 240000
            and sum(Decimal(x['amount_usd']) for x in register if x['kind'] == 'existing_service') ==
            Decimal(manifest['counts']['remaining_existing_service_usd']) == 1097750
            and sum(Decimal(x['amount_usd']) for x in register if x['state'] == 'conditional') ==
            Decimal(manifest['counts']['conditional_project_usd']) == 5400, 'Commercial portfolio amount drift')

    reservations = [row for r in records for row in r['capacity_reservations']]
    require(Counter(str(sorted(x.items())) for x in reservations) ==
            Counter(str(sorted(x.items())) for x in manifest['capacity']), 'Capacity differs from accepted orders')
    require(list(csv.DictReader(io.StringIO(by_doc[manifest['capacity_workbook']]['text']))) ==
            [{k: str(v) for k, v in row.items()} for row in manifest['capacity']], 'Capacity workbook bytes drift')
    allocated = defaultdict(int)
    for row in reservations:
        r = next(r for r in records if r['id'] == row['record'])
        week = date.fromisoformat(row['week_of'])
        require(row['owner'] == r['delivery_owner'] and week.weekday() == 0
                and row['weekly_hours'] == 40 and row['existing_work_and_leave_hours'] == 32
                and row['new_project_hours'] == 8 and row['remaining_hours'] == 0
                and r['work_start'] <= row['week_of'] <= r['work_end'], 'Commercial capacity or owner drift')
        allocated[(row['owner'], row['week_of'])] += row['new_project_hours']
    require(all(hours <= 8 for hours in allocated.values()), 'Accepted commercial work overbooks a delivery owner')
    for event in new_events.values():
        for other in calendars:
            if other['id'] == event['id'] or other['status'] == 'CANCELLED':
                continue
            overlap = max(event['start'], other['start']) < min(event['end'], other['end'])
            common = set([event['organizer']] + event['attendees']) & set([other['organizer']] + other['attendees'])
            require(not overlap or not common, 'Commercial appointment overlaps an existing participant booking')
    reference = next(r for r in records if r['id'] == 'COM-2026-005')
    event = by_event[reference['calendar_id']]
    require(reference['status'] == 'reference_planned' and reference['staff_minutes'] == 60
            and event['status'] == 'TENTATIVE' and event['start'] == reference['reference_start'] == '2026-09-29T10:00:00-04:00'
            and event['end'] == reference['reference_end'] == '2026-09-29T10:30:00-04:00'
            and set(event['attendees']) == {'theo', 'clara', 'maya', 'kwm048'}, 'ARWC reference hold or staff time drift')
    require(all(not re.search(r'\b(?:scenario|challenge|benchmark|author-only|generated-by)\b',
                             x.get('body', x.get('text', '')), re.I) for x in list(new_mail.values()) + list(new_docs.values())),
            'Authoring context leaked into commercial content')
    return manifest['counts']
