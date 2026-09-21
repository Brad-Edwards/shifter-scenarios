#!/usr/bin/env python3
"""Validate the finished retail population, opening ledger and restricted readbacks."""
from collections import Counter, defaultdict
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
from pathlib import Path
import yaml
import zipfile


def require(value, message):
    if not value:
        raise ValueError('Service accounts: ' + message)


def load_tables(root):
    with zipfile.ZipFile(root / 'documents/service-account-records.zip') as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())) == 17,
                'CSV member inventory')
        return {Path(name).stem: list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8'))))
                for name in archive.namelist()}


def amount(value):
    return Decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def check_population(tables, snapshot='2026-09-16T08:30:00-04:00'):
    t = tables
    keys = {'accounts': 'account_id', 'contacts': 'contact_id', 'service-points': 'service_point_id',
            'account-services': 'relationship_id', 'meters': 'meter_id', 'readings': 'reading_id',
            'tariffs': 'tariff_id', 'periods': 'period_id', 'invoices': 'invoice_id',
            'invoice-lines': 'line_id', 'receipts': 'receipt_id', 'allocations': 'allocation_id',
            'opening-balances': 'account_id', 'preferences': 'account_id', 'changes': 'change_id',
            'cases': 'case_id', 'statement-deliveries': 'delivery_id'}
    require(set(t) == set(keys), 'table inventory')
    ix = {}
    for table, key in keys.items():
        ix[table] = {r[key]: r for r in t[table]}
        require(len(ix[table]) == len(t[table]) and all(ix[table]), 'duplicate or empty ' + key)
        require(all(None not in r and all(v is not None for v in r.values()) for r in t[table]),
                'malformed CSV row')
    a, p, m, r = (ix[x] for x in ['accounts', 'service-points', 'meters', 'readings'])
    require(len(a) == 50100 and len(p) == 50460 and len(m) == 51330, 'population counts')
    require(Counter(x['account_class'] for x in a.values()) ==
            Counter(HOME=48000, MASTER=480, BUSINESS=1499, SEASONAL=1, MUNICIPAL=120), 'account classes')
    require(len({x['customer_id'] for x in a.values()}) == len(a), 'customer identity')
    require({c['account_id'] for c in t['contacts']} == set(a) and len(t['contacts']) == len(a), 'contacts coverage')
    require(set(ix['preferences']) == set(ix['opening-balances']) == set(a), 'opening/preference coverage')
    for c in t['contacts']:
        require(c['customer_id'] == a[c['account_id']]['customer_id'] and c['email'].endswith('.test')
                and c['phone'] == '' and c['authority_from'] <= '2026-07-01' and not c['authority_to'],
                'customer contact boundary')
    for district, dwellings, residents in [('PINE', 33750, 90000), ('RIVER', 26250, 70000)]:
        points = [x for x in p.values() if x['district'] == district]
        require(sum(int(x['occupied_dwellings']) for x in points) == dwellings and
                sum(int(x['estimated_residents']) for x in points) == residents, 'district population')
    require(all(x['service'] == 'drinking_water' and x['district'] in {'PINE', 'RIVER'} for x in p.values()),
            'service scope')
    require(len({x['address'] for x in p.values()}) == len(p), 'ambiguous connection addresses')
    links, point_account = defaultdict(list), {}
    for link in t['account-services']:
        aid, pid = link['account_id'], link['service_point_id']
        require(aid in a and pid in p and pid not in point_account, 'service responsibility overlap')
        require(a[aid]['home_district'] == p[pid]['district'] and link['share'] == '1.00', 'district responsibility')
        require(p[pid]['active_from'] <= link['effective_from'] <= '2026-04-01' and not link['effective_to'],
                'responsibility date')
        links[aid].append(pid); point_account[pid] = aid
    require(set(point_account) == set(p) and set(links) == set(a), 'unserved account or point')
    require(Counter(map(len, links.values())) == Counter({1: 49740, 2: 360}), 'multi-point relationships')
    by_point, by_meter = defaultdict(list), defaultdict(list)
    for meter in m.values():
        pid = meter['service_point_id']; by_point[pid].append(meter)
        require(pid in p and meter['register_unit'] == 'm3' and meter['multiplier'] == '1', 'meter units or point')
        require(meter['installed_at'] <= snapshot and meter['status'] in {'active', 'retired'}, 'meter installation')
        require((meter['removed_at'] != '') == (meter['status'] == 'retired'), 'retirement state')
        if meter['removed_at']:
            require(meter['installed_at'] < meter['removed_at'] <= snapshot, 'meter lifetime')
        parent = meter['parent_meter_id']
        if meter['role'] == 'check':
            require(parent in m and m[parent]['service_point_id'] == pid and m[parent]['role'] == 'billing'
                    and meter['owner'] == 'building_owner', 'check meter parent')
        else:
            require(meter['role'] == 'billing' and not parent and meter['owner'] == 'ARWC', 'supply meter scope')
        previous = meter['predecessor_id']
        if previous:
            require(previous in m and m[previous]['removed_at'] == meter['installed_at']
                    and m[previous]['supply_path'] == meter['supply_path']
                    and m[previous]['service_point_id'] == pid, 'replacement continuity')
    require(len({x['serial'] for x in m.values()}) == len(m), 'duplicate serial')
    require(Counter((x['status'], x['role']) for x in m.values()) ==
            Counter({('active', 'billing'): 51060, ('active', 'check'): 150, ('retired', 'billing'): 120}),
            'meter role counts')
    for pid, meters in by_point.items():
        active = [x for x in meters if x['status'] == 'active']
        supplies = [x for x in active if x['role'] == 'billing']
        require(len(supplies) == (2 if p[pid]['meter_arrangement'] == 'parallel_feeds' else 1),
                'supply arrangement')
        require(len({x['supply_path'] for x in active}) == len(active), 'overlapping active supply path')
    for read in r.values():
        mid = read['meter_id']
        require(mid in m, 'unknown reading meter')
        meter = m[mid]
        require(meter['installed_at'] <= read['read_at'] <= (meter['removed_at'] or snapshot)
                and read['quality'] == 'actual' and Decimal(read['register_m3']) >= 0, 'reading lifetime or quality')
        by_meter[mid].append(read)
    require(set(by_meter) == set(m), 'meter without opening history')
    for mid, reads in by_meter.items():
        ordered = sorted(reads, key=lambda x: x['read_at'])
        require(len({x['read_at'] for x in ordered}) == len(ordered), 'duplicate reading instant')
        require(ordered[0]['method'] == 'installation' and ordered[0]['register_m3'] == '0'
                and ordered[0]['read_at'] == m[mid]['installed_at'], 'installation zero')
        require(all(Decimal(x['register_m3']) <= Decimal(y['register_m3'])
                    for x, y in zip(ordered, ordered[1:])), 'register moved backwards')
        if m[mid]['removed_at']:
            require(ordered[-1]['method'] == 'removal' and ordered[-1]['read_at'] == m[mid]['removed_at'],
                    'missing removal read')
    invoices, receipts = ix['invoices'], ix['receipts']
    line_totals, usage, fixed = defaultdict(Decimal), defaultdict(list), defaultdict(list)
    for line in t['invoice-lines']:
        iid = line['invoice_id']; require(iid in invoices, 'orphan invoice line')
        inv = invoices[iid]; aid = inv['account_id']; tariff = ix['tariffs'][inv['tariff_id']]
        pid = line['service_point_id']; require(pid in links[aid], 'line billed to wrong account')
        qty = Decimal(line['quantity']); price = Decimal(line['unit_price_usd'])
        require(amount(qty * price) == Decimal(line['amount_usd']), 'line arithmetic')
        if line['charge'] == 'usage':
            mid, start, end = line['meter_id'], line['start_reading_id'], line['end_reading_id']
            require(mid in m and m[mid]['role'] == 'billing' and m[mid]['service_point_id'] == pid,
                    'check or unrelated meter billed')
            require(start in r and end in r and r[start]['meter_id'] == r[end]['meter_id'] == mid,
                    'reading/meter join')
            require(r[start]['read_at'] < r[end]['read_at'] and qty ==
                    Decimal(r[end]['register_m3']) - Decimal(r[start]['register_m3']), 'usage interval')
            period = ix['periods'][inv['period_id']]
            require(period['start'] <= r[start]['read_at'] < r[end]['read_at'] <= period['end_exclusive'],
                    'usage outside period')
            require(tariff['effective_from'] <= r[start]['read_at'][:10] and
                    r[end]['read_at'][:10] <= tariff['effective_to'], 'tariff interval')
            require(price == Decimal(tariff['unit_usd_per_m3']) and line['unit'] == 'm3', 'usage tariff')
            usage[(aid, mid)].append((r[start]['read_at'], r[end]['read_at']))
        else:
            require(line['charge'] == 'fixed' and not line['meter_id'] and not line['start_reading_id']
                    and not line['end_reading_id'], 'fixed meter fields')
            require(qty == (int(p[pid]['occupied_dwellings']) if a[aid]['account_class'] == 'MASTER' else 1)
                    and price == Decimal(tariff['fixed_usd']) and line['unit'] == tariff['fixed_unit'],
                    'fixed tariff basis')
            fixed[iid].append(pid)
        line_totals[iid] += Decimal(line['amount_usd'])
    for intervals in usage.values():
        ordered = sorted(intervals)
        require(all(x[1] <= y[0] for x, y in zip(ordered, ordered[1:])), 'double-billed interval')
    for inv in invoices.values():
        aid, iid = inv['account_id'], inv['invoice_id']
        require(aid in a and inv['tariff_id'] == a[aid]['tariff_id'] and inv['currency'] == 'USD', 'invoice authority')
        require(inv['tax_usd'] == '0.00' and line_totals[iid] == Decimal(inv['total_usd']) == Decimal(inv['net_usd']),
                'invoice reconciliation')
        require(inv['issued_on'] <= inv['due_on'] and inv['issued_on'] <= snapshot[:10], 'invoice dates')
        if a[aid]['account_class'] != 'SEASONAL':
            period = ix['periods'][inv['period_id']]
            require(inv['issued_on'] == period['invoice_date'] and inv['due_on'] == period['due_date'], 'invoice cadence')
            require(sorted(fixed[iid]) == sorted(links[aid]), 'fixed charge coverage')
    # Every installed supply has exactly its opening service interval represented, including exchanges.
    for mid, meter in m.items():
        if meter['role'] != 'billing': continue
        aid = point_account[meter['service_point_id']]
        if aid == 'A-B-002': continue
        period = ix['periods'][a[aid]['period_id']]
        require(usage[(aid, mid)] == [(max(period['start'], meter['installed_at']),
                                     min(period['end_exclusive'], meter['removed_at'] or period['end_exclusive']))],
                'missing opening consumption interval')
    allocated_invoice, allocated_receipt = defaultdict(Decimal), defaultdict(Decimal)
    for alloc in t['allocations']:
        iid, rid = alloc['invoice_id'], alloc['receipt_id']
        require(iid in invoices and rid in receipts and invoices[iid]['account_id'] == receipts[rid]['account_id'],
                'cross-account allocation')
        require(receipts[rid]['received_at'][:10] <= alloc['allocated_on'] <= snapshot[:10], 'allocation date')
        value = Decimal(alloc['amount_usd']); require(value > 0, 'nonpositive allocation')
        allocated_invoice[iid] += value; allocated_receipt[rid] += value
    opening_receipts = defaultdict(Decimal)
    for rec in receipts.values():
        require(rec['account_id'] in a and Decimal(rec['amount_usd']) > 0 and rec['received_at'] <= snapshot,
                'receipt boundary')
        require(allocated_receipt[rec['receipt_id']] <= Decimal(rec['amount_usd']), 'overallocated receipt')
        if rec['received_at'] <= '2026-07-01T18:00:00-04:00':
            opening_receipts[rec['account_id']] += Decimal(rec['amount_usd'])
    for bal in t['opening-balances']:
        aid = bal['account_id']; inv = invoices[bal['invoice_id']]; total = Decimal(inv['total_usd'])
        paid = opening_receipts[aid]; allocated = allocated_invoice[inv['invoice_id']]
        require(allocated <= total and inv['account_id'] == aid and bal['as_of'] == '2026-07-01T18:00:00-04:00',
                'opening boundary or overallocation')
        expected = dict(invoice_usd=total, received_usd=paid, allocated_usd=allocated,
                        unapplied_credit_usd=paid-allocated, outstanding_invoice_usd=total-allocated,
                        net_balance_usd=total-paid, overdue_usd=total-allocated if inv['due_on'] < '2026-07-01' else 0)
        require(all(Decimal(bal[k]) == v for k, v in expected.items()), 'opening balance arithmetic')
    require(a['A-B-001']['home_district'] == 'RIVER' and a['A-B-002']['home_district'] == 'PINE', 'named customer district')
    talvern = [x for x in invoices.values() if x['account_id'] == 'A-B-002']
    require({x['external_reference']: x['total_usd'] for x in talvern} ==
            {'TG-26-0612': '517.50', 'TG-26-0702': '713.00', 'TG-26-0720': '575.00'}, 'Talvern settled activity')
    require(all(allocated_invoice[x['invoice_id']] == Decimal(x['total_usd']) for x in talvern), 'Talvern settlement')
    require(ix['tariffs']['ARWC-W-SEASONAL-2026-v1']['unit_usd_per_m3'] == '1.15', 'Talvern price')
    for change in t['changes']:
        aid = change['account_id']; case = ix['cases'][change['case_id']]
        require(case['account_id'] == aid and change['before'] != change['after'] and
                case['opened_at'] < change['authorized_at'] < change['effective_at'] == case['closed_at'] <= snapshot,
                'change consent or chronology')
        require(ix[change['entity']][aid][change['field']] == change['after'], 'change not applied')
        require(ix[change['entity']][aid]['revision'] == change['revision_to'] == '2', 'change revision')
    for delivery in t['statement-deliveries']:
        c = ix['contacts'][delivery['contact_id']]
        require(c['account_id'] == delivery['account_id'] and c['email'] == delivery['recipient'] and
                delivery['consent_on'] < delivery['sent_at'][:10] <= snapshot[:10] and
                delivery['purpose'] == 'one_off_opening_statement', 'statement delivery privacy or consent')
    return ix


def check_service_accounts(root, identity, roster, mail, docs, tables=None):
    manifest = yaml.safe_load((root / 'authoring/service-accounts.yaml').read_text())
    t = tables if tables is not None else load_tables(root)
    ix = check_population(t, identity['snapshot'])
    messages = {x['id']: x for x in mail if x['id'].startswith('sa-')}
    documents = {d['id']: d for d in docs if d['story'] == 'service-accounts'}
    require(len(messages) == 1460 and len(documents) == 872, 'content counts')
    require(manifest['counts']['retained_copies'] == 2060, 'retained-copy count')
    require(manifest['counts']['business_records'] == sum(map(len, t.values())) == 696987, 'business record count')
    require(manifest['snapshot'] == identity['snapshot'] and
            manifest['native_source'] == 'cinder-typhoon/narrative/arwc-documents' and
            manifest['logical_owner'] == 'a-corporate.a-business', 'native ownership')
    require(set(manifest['tables']) == set(t), 'native table inventory')
    with zipfile.ZipFile(root / 'documents/service-account-records.zip') as archive:
        for name, entry in manifest['tables'].items():
            d = documents[entry['document']]; raw = archive.read(name+'.csv')
            require(hashlib.sha256(raw).hexdigest() == d['binary_sha256'] == entry['sha256'] and
                    entry['rows'] == len(t[name]), 'CSV source integrity')
            require(d['archive'] == 'documents/service-account-records.zip' and d['member'] == name+'.csv'
                    and d['media_type'] == 'text/csv' and d['audience'] == 'restricted', 'CSV native item')
            require(d['reader_keys'] == entry['readers'], 'CSV reader scope')
            # Exact independently specified business audiences, not just matching two manifests.
            base = {'rosa', 'awm182', 'awm183', 'awm184', 'awm197', 'awm198'}
            expected = base | {'theo', 'mina'} if name in {'service-points', 'meters', 'readings'} else (
                base | {'priya', 'theo', 'mina'} if name in {'tariffs', 'periods'} else base)
            require(set(d['reader_keys']) == expected, 'customer data exposed outside retail role')
            forbidden = ('world_release', 'scenario_overlay', 'required_base', 'seed', 'authoring', 'challenge_id')
            require(not any(x in t[name][0] for x in forbidden), 'author metadata leaked')
    staff = {r['key']: r for r in roster}
    seen = set()
    for case in manifest['cases']:
        require(ix['cases'][case['case_id']]['account_id'] == case['account_id'], 'case join')
        require(len(case['messages']) in {2, 4} and len(set(case['messages'])) == len(case['messages']), 'case message count')
        turns = [messages[x] for x in case['messages']]
        require([x['from'] for x in turns] == [case['customer_key'], case['owner_key']]*(len(turns)//2), 'case speaker order')
        require(all(x['to'] == [case['owner_key'] if i % 2 == 0 else case['customer_key']]
                    for i, x in enumerate(turns)), 'case audience')
        require(all(turns[i]['reply_to'] == turns[i-1]['id'] and turns[i-1]['date'] < turns[i]['date']
                    for i in range(1, len(turns))), 'case threading')
        require(turns[0]['date'] == case['opened_at'] and turns[-1]['date'] == case['closed_at'], 'case chronology')
        d = documents[case['document']]
        require(case['account_id'] in d['text'] and d['published_at'] == case['closed_at']
                and d['audience'] == 'restricted', 'case readback')
        if case['change_id']:
            change = ix['changes'][case['change_id']]
            require(change['authorized_at'] == turns[2]['date'] and change['recorded_by'] ==
                    staff[case['owner_key']]['email'] and change['after'] in d['text'], 'case authorization evidence')
        seen.update(case['messages'])
    contacts = identity['correspondents'] | identity['people']
    for notice in manifest['notices']:
        msg = messages[notice['message']]; aid = notice['account_id']; d = documents[notice['document']]
        require(msg['from'] == 'arwc_accounts' and msg['to'] == [notice['customer_key'], 'awm198'] and notice['staff_copy'] == 'awm198' and
                msg['attachments'] == [d['id']], 'statement recipient/attachment')
        c = next(x for x in t['contacts'] if x['account_id'] == aid)
        require(contacts[notice['customer_key']]['email'] == c['email'], 'wrong statement contact')
        balance = ix['opening-balances'][aid]; invoice = ix['invoices'][balance['invoice_id']]
        require(aid in d['text'] and invoice['invoice_id'] in d['text'] and
                'Net account balance: USD '+balance['net_balance_usd'] in d['text'] and
                'Net balance at opening: USD '+balance['net_balance_usd'] in msg['body'], 'statement amounts')
        require(all(x['account_id'] == aid for x in t['statement-deliveries'] if x['correspondence_id'] == msg['id']),
                'delivery join')
        seen.add(msg['id'])
    require(seen == set(messages), 'unowned or inflated messages')
    require(len({messages[c['messages'][0]]['body'] for c in manifest['cases']}) == 240,
            'duplicate customer prose')
    require(all(d['audience'] == 'restricted' and set(d['reader_keys']) <= set(staff) for d in documents.values()),
            'unrestricted retail document')
    print('PASS: 50,100 accounts / 160,000 residents; 696,987 joined business records; '
          '1,460 messages; exact tariffs, meter histories, balances, consent and reader scopes')


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1] / 'assets/narrative'
    identity = yaml.safe_load((root/'authoring/people.yaml').read_text())
    roster = yaml.safe_load((root/'authoring/workforce.yaml').read_text())['employees']
    mail = yaml.safe_load((root/'authoring/mail-service-accounts.yaml').read_text())['messages']
    docs = yaml.safe_load((root/'authoring/documents-service-accounts.yaml').read_text())['documents']
    check_service_accounts(root, identity, roster, mail, docs)
