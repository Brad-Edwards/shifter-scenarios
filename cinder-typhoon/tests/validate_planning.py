#!/usr/bin/env python3
"""Check finished planning records against source facts and actual Office cells."""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
import csv
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile
import yaml

SNAPSHOT = '2026-09-16T08:30:00-04:00'
CUTOFF = '2026-08-31T23:59:59-04:00'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ROOT = Path(__file__).resolve().parents[1] / 'assets/narrative'

# Expected models are separate from the authored formula/cache manifest.
MODELS = {
    'demand': (['ROUND(Inputs!B2/Inputs!B3,2)', 'ROUND(B2*Inputs!B5,2)', 'ROUND(B2*Inputs!B6,2)'], ['m³/day']*3),
    'renewal': (['ROUND(Inputs!B5*Inputs!B8,2)', 'ROUND(Inputs!B4+Inputs!B7+Inputs!B6*Inputs!B8,2)', 'ROUND(B3-B2,2)', 'Inputs!B2-Inputs!B3'], ['USD']*3+['orders']),
    'laboratory': (['ROUND(Inputs!B3*Inputs!B6/60,2)', 'ROUND(Inputs!B2*Inputs!B7/60,2)', 'ROUND(Inputs!B5*Inputs!B8/60,2)', 'ROUND(SUM(B2:B4),2)'], ['staff-hours']*4),
    'project': (['ROUND(Inputs!B2-Inputs!B3,2)', 'ROUND(B2/Inputs!B2*100,2)', 'ROUND(Inputs!B3*Inputs!B4,2)'], ['USD','percent','USD']),
    'bulk': (['Inputs!B2-Inputs!B3', 'ROUND(Inputs!B3*Inputs!B4,2)', 'ROUND(Inputs!B3/Inputs!B2*100,2)'], ['m³','USD','percent']),
    'seasonal': ([f'ROUND(Inputs!B{2+2*i}/Inputs!B{3+2*i},2)' for i in range(4)]+['ROUND(SUM(B2:B5),2)', 'ROUND(B6*Inputs!B10,2)', 'ROUND(B6*Inputs!B11,2)'], ['m³/day']*7),
    'field': (['ROUND(Inputs!B3/Inputs!B2,2)', 'ROUND(Inputs!B4*Inputs!B5/60,2)'], ['visits/day','staff-hours']),
    'equipment': (['ROUND(Inputs!B3/Inputs!B2,2)', 'ROUND(Inputs!B3*Inputs!B4,2)'], ['hours/service','staff-hours']),
    'staffing': (['Inputs!B2*Inputs!B3', 'Inputs!B2*(Inputs!B4+Inputs!B5)', 'Inputs!B2*Inputs!B6', 'B2-B3-B4'], ['staff-hours/week']*4),
}


def require(value, message):
    if not value:
        raise ValueError('Planning: ' + message)


def load(root, filename):
    return yaml.safe_load((root / 'authoring' / filename).read_text())


def stamp(value):
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None, 'timestamp without offset')
    return result


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def table(root, archive, member):
    with zipfile.ZipFile(root / 'documents' / archive) as z:
        return list(csv.DictReader(io.StringIO(z.read(member).decode())))


def formula_value(formula, cells):
    """Evaluate this slice's arithmetic subset; never execute workbook code."""
    expression = re.sub(r'SUM\(B(\d+):B(\d+)\)',
                        lambda m: '(' + '+'.join(f'B{i}' for i in range(int(m[1]), int(m[2])+1)) + ')', formula.lstrip('='))
    expression = re.sub(r'(?:Inputs!)?B\d+', lambda m: 'V_' + m[0].replace('!', '_'), expression)
    values = {'V_' + k.replace('!', '_'): Decimal(str(v)) for k, v in cells.items()}

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float): return Decimal(str(node.value))
        if isinstance(node, ast.Name) and node.id in values: return values[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub): return -visit(node.operand)
        if isinstance(node, ast.BinOp):
            a, b = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): return a + b
            if isinstance(node.op, ast.Sub): return a - b
            if isinstance(node.op, ast.Mult): return a * b
            if isinstance(node.op, ast.Div): return a / b
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'ROUND' and len(node.args) == 2 and not node.keywords):
            return visit(node.args[0]).quantize(Decimal(10) ** -int(visit(node.args[1])), rounding=ROUND_HALF_UP)
        raise ValueError('Planning: unsupported formula expression')

    return visit(ast.parse(expression, mode='eval').body)


class Sources:
    """Reconstruct aggregates without trusting planning totals."""
    def __init__(self, root):
        self.root = root
        self.maintenance = load(root, 'maintenance-engineering.yaml')
        self.network = {o['key']: o for o in load(root, 'business-network.yaml')['organizations']}
        archive = 'service-account-records.zip'
        accounts = {r['account_id']: r for r in table(root, archive, 'accounts.csv')}
        invoices = {r['invoice_id']: r for r in table(root, archive, 'invoices.csv')}
        points = {r['service_point_id']: r for r in table(root, archive, 'service-points.csv')}
        self.periods = {r['period_id']: r for r in table(root, archive, 'periods.csv')}
        self.usage = defaultdict(list)
        for row in table(root, archive, 'invoice-lines.csv'):
            if row['charge'] != 'usage': continue
            invoice = invoices[row['invoice_id']]
            require(invoice['issued_on'][:10] <= CUTOFF[:10], 'future invoice source')
            require(row['unit'] == 'm3', 'source consumption unit')
            self.usage[(points[row['service_point_id']]['district'], accounts[invoice['account_id']]['account_class'])].append((row, invoice['period_id']))
        self.samples = table(root, 'laboratory-quality-records.zip', 'registers/samples.csv')
        self.results = table(root, 'laboratory-quality-records.zip', 'registers/results.csv')
        self.reviews = table(root, 'laboratory-quality-records.zip', 'registers/reviews.csv')

    def demand(self, district, account_class):
        rows = self.usage[(district, account_class)]
        periods = {period for _, period in rows}
        require(len(periods) == 1, 'mixed billing periods within class')
        period = self.periods[next(iter(periods))]
        days = (datetime.fromisoformat(period['end_exclusive']) - datetime.fromisoformat(period['start'])).days
        return sum(int(r['quantity']) for r, _ in rows), days, len(rows), next(iter(periods))

    def inputs(self, c):
        kind, s = c['kind'], c['selector']
        if kind == 'demand':
            volume, days, lines, period = self.demand(s['district'], s['account_class'])
            require(s['period'] == period, 'source period selection')
            return {'volume': (volume, 'm³'), 'days': (days, 'days'), 'lines': (lines, 'lines')}
        if kind == 'seasonal':
            values = {}
            for cls in ('HOME', 'MASTER', 'BUSINESS', 'MUNICIPAL'):
                volume, days, _, _ = self.demand(s['district'], cls)
                values.update({cls+'_volume': (volume, 'm³'), cls+'_days': (days, 'days')})
            return values
        if kind == 'renewal':
            assets = {a['asset_id']: a for a in self.maintenance['assets']}
            require(s['asset'] in assets and c['asset_name'] == assets[s['asset']]['name'], 'asset identity')
            rows = [w for w in self.maintenance['work_orders'] if w['asset_id'] == s['asset'] and stamp(w['updated_at']) <= stamp(CUTOFF)]
            require(c['source_record_ids'] == [w['work_order'] for w in rows], 'maintenance source selection')
            return {'orders': (len(rows), 'orders'), 'complete': (sum(w['status'] == 'completed' for w in rows), 'orders')}
        if kind == 'laboratory':
            ids = {r['sample_id'] for r in self.samples if r['collected_at'].startswith(s['month']) and stamp(r['received_at']) <= stamp(CUTOFF)}
            rows = [r for r in self.reviews if r['sample_id'] in ids and stamp(r['reviewed_at']) <= stamp(CUTOFF)]
            require(c['source_record_ids'] == sorted(ids) and len(rows) == len(ids), 'sample selection or contemporary review')
            return {'samples': (len(ids), 'samples'),
                    'runs': (sum(r['sample_id'] in ids and stamp(r['analysed_at']) <= stamp(CUTOFF) for r in self.results), 'result rows'),
                    'accepted': (sum(r['disposition'] in ('accepted', 'accepted after repeat') for r in rows), 'samples'),
                    'open': (sum(r['disposition'] == 'resample requested' for r in rows), 'samples')}
        if kind == 'project':
            p = next(p for p in self.maintenance['projects'] if p['id'] == s['project'])
            require(p['handover'] < CUTOFF[:10], 'future historical handover')
            return {'estimate': (p['estimate'], 'USD'), 'accepted': (p['accepted'], 'USD')}
        if kind == 'bulk':
            org = self.network[s['organization']]
            merewick = s['organization'] == 'merewick'
            return {'ceiling': (20000 if merewick else 7500, 'm³'),
                    'delivered': (sum(r['quantity'] for r in org['settled_activity']), 'm³'),
                    'rate': (.92 if merewick else 1.15, 'USD/m³')}
        if kind == 'field':
            rows = [r for r in table(self.root, 'field-operations-records.zip', f'dispatch-{s["district"]}.csv') if stamp(r['recorded_at']) <= stamp(CUTOFF)]
            return {'days': (len(rows), 'days'), 'complete': (sum(int(r['complete']) for r in rows), 'visits'),
                    'follow': (sum(int(r['follow_up']) + int(r['no_access']) for r in rows), 'visits')}
        if kind == 'equipment':
            rows = [r for r in table(self.root, 'laboratory-quality-records.zip', 'registers/equipment-services.csv') if stamp(r['completed_at']) <= stamp(CUTOFF)]
            hours = sum((stamp(r['completed_at']) - stamp(r['scheduled_for'])).total_seconds()/3600 for r in rows)
            return {'visits': (len(rows), 'services'), 'hours': (hours, 'hours')}
        require(kind == 'staffing', 'unknown planning calculation')
        return {'people': (8, 'staff')}


def check_workbook(raw, w, c, document, people):
    formulas, units = MODELS[c['kind']]
    require([v['formula'] for v in w['calculation']] == ['='+f for f in formulas]
            and [v['unit'] for v in w['calculation']] == units, 'work-specific calculation model')
    with zipfile.ZipFile(io.BytesIO(raw)) as office:
        require(office.testzip() is None and not any('externalLink' in n for n in office.namelist()), 'invalid or externally linked workbook')
        sheets = ET.fromstring(office.read('xl/workbook.xml')).findall('s:sheets/s:sheet', NS)
        require([s.attrib['name'] for s in sheets] == ['Read me', 'Inputs', 'Calculation']
                and all(s.get('state', 'visible') == 'visible' for s in sheets), 'workbook sheet visibility')
        strings = [''.join(n.itertext()) for n in ET.fromstring(office.read('xl/sharedStrings.xml'))]
        parsed = [ET.fromstring(office.read(f'xl/worksheets/sheet{i}.xml')) for i in range(1, 4)]
        def cell(sheet, ref):
            node = parsed[sheet-1].find(f'.//s:c[@r="{ref}"]', NS)
            require(node is not None and node.find('s:v', NS) is not None, f'missing workbook cell {ref}')
            text = node.find('s:v', NS).text
            return strings[int(text)] if node.get('t') == 's' else Decimal(text)
        require(cell(1, 'B4') == people[c['owner']]['name'] and cell(1, 'B5') == CUTOFF
                and cell(1, 'B6') == document['published_at'] and cell(1, 'B8') == c['input_document'], 'workbook provenance')
        values = {}
        for row, item in enumerate(w['inputs'], 2):
            require(cell(2, f'A{row}') == item['label'] and cell(2, f'B{row}') == Decimal(str(item['value']))
                    and cell(2, f'C{row}') == item['unit'] and cell(2, f'D{row}') == item['kind'], 'workbook input or unit')
            values[f'Inputs!B{row}'] = cell(2, f'B{row}')
        require(sum(len(s.findall('.//s:f', NS)) for s in parsed) == len(w['calculation']), 'formula inventory')
        for row, item in enumerate(w['calculation'], 2):
            ref = f'B{row}'
            node = parsed[2].find(f'.//s:c[@r="{ref}"]/s:f', NS)
            require(node is not None, 'missing calculation formula')
            calculated = formula_value(node.text, values)
            require(calculated == cell(3, ref), f'cached formula mismatch: {document["id"]} {ref}')
            require('='+node.text == item['formula'] and calculated == Decimal(str(item['value']))
                    and cell(3, f'C{row}') == item['unit'] and cell(3, f'A{row}') == item['label'], 'workbook calculation or unit')
            values[ref] = calculated


def result_lines(calculations):
    return [f"| Calculation!B{i+2} | {v['label']} | {v['value']:.2f} | {v['unit']} |" for i, v in enumerate(calculations)]


def check_planning(root, workforce, identity, mail, docs, events, manifest=None):
    manifest = manifest or load(root, 'planning.yaml')
    require(manifest['snapshot'] == SNAPSHOT and manifest['cutoff'] == CUTOFF, 'snapshot or cut-off drift')
    require(manifest['required_base'] == dict(repository_commit='4a3386c', accepted_maintenance_engineering_commit='0b7f0b2',
            accepted_laboratory_quality_commit='f16aec0', accepted_purchasing_stores_commit='46b6980',
            accepted_retail_billing_commit='58c1396'), 'accepted-base drift')
    require(manifest['native_sources'] == dict(mail='cinder-typhoon/narrative/arwc-mail',
            documents='cinder-typhoon/narrative/arwc-documents', logical_owner='a-corporate.a-business')
            and manifest['ownership_release'] == 'planning-2026-09-16/v1', 'native ownership drift')
    for path, digest in manifest['source_digests'].items():
        require(sha((root / path).read_bytes()) == digest, f'upstream source digest: {path}')
    people = {p['key']: p for p in workforce}
    planners = {p['key'] for p in workforce if p['team'] == 'Resource planning'}
    require(len(planners) == 8 and set(manifest['resource_planners']) == planners
            and sum(p['department'] == 'Planning, quality, and compliance' for p in workforce) == 32, 'department membership')
    messages = {m['id']: m for m in mail if m.get('story') == 'planning'}
    documents = {d['id']: d for d in docs if d.get('story') == 'planning'}
    calendars = {e['id']: e for e in events if e['id'].startswith('planning-')}
    cases = {c['id']: c for c in manifest['cases']}
    workbooks = {w['document']: w for w in manifest['workbooks']}
    counts = manifest['counts']
    require(counts == dict(messages=232, retained_copies=760, planning_histories=40, documents=230,
            calendars=8, workbooks=48, registers=5, archive_members=53), 'declared count drift')
    require((len(messages), len(documents), len(calendars), len(cases), len(workbooks)) == (232,230,8,40,48), 'actual inventory')
    require(Counter(c['kind'] for c in cases.values()) == Counter(demand=8, renewal=12, laboratory=8, project=4, bulk=2, seasonal=2, field=2, equipment=1, staffing=1), 'case coverage')
    require({c['owner'] for c in cases.values()} == planners, 'planner ownership coverage')
    adjustment = manifest['volume_adjustment']
    require(adjustment['initial_messages'] == 5000 and adjustment['delivered_messages'] == len(messages)
            and adjustment['difference'] == -4768 and adjustment['reason'], 'message adjustment')
    require(len({m['body'] for m in messages.values()}) == len(messages), 'duplicate correspondence')
    require(sum(1+len(m['to']) for m in messages.values()) == counts['retained_copies'], 'retained-copy count')
    for d in documents.values():
        require(d['audience'] == 'restricted' and set(d['reader_keys']) <= people.keys()
                and stamp(d['published_at']) <= stamp(SNAPSHOT), 'document audience or chronology')
    for m in messages.values():
        audience = {m['from'], *m['to']}
        require(audience <= people.keys() and m['from'] not in m['to'] and len(m['to']) == len(set(m['to'])), 'mail participants')
        require(stamp(m['date']) <= stamp(SNAPSHOT)
                and all(people[p]['effective_date'] <= m['date'][:10] for p in audience), 'mail employment or date')
        if m.get('reply_to'):
            parent = messages.get(m['reply_to'])
            require(parent is not None and stamp(parent['date']) < stamp(m['date'])
                    and audience == {parent['from'], *parent['to']}, 'thread ancestry or audience')
        for ref in m.get('attachments', []):
            require(ref in documents and audience <= set(documents[ref]['reader_keys'])
                    and stamp(documents[ref]['published_at']) <= stamp(m['date']), 'attachment audience or chronology')
    sources = Sources(root)
    with zipfile.ZipFile(root / 'documents/planning-records.zip') as archive:
        members = {d['member'] for d in documents.values() if 'member' in d}
        require(archive.testzip() is None and len(archive.namelist()) == len(members) == 53
                and set(archive.namelist()) == members, 'archive inventory')
        for d in documents.values():
            if 'member' in d:
                require(d['archive'] == 'documents/planning-records.zip' and sha(archive.read(d['member'])) == d['binary_sha256'], 'binary digest')
        registers = {}
        for name, info in manifest['tables'].items():
            raw = archive.read(info['member'])
            rows = list(csv.DictReader(io.StringIO(raw.decode())))
            require(len(rows) == info['rows'] and len({r[info['primary_key']] for r in rows}) == len(rows)
                    and sha(raw) == info['sha256'] and documents[info['document']]['member'] == info['member'], 'register integrity')
            registers[name] = rows
        for c in cases.values():
            cid = c['id']; expected = sources.inputs(c)
            require(c['cutoff'] == CUTOFF and c['owner'] != c['reviewer'], 'case cut-off or self-review')
            require({i['key'] for i in c['inputs'] if i['kind'] == 'source'} == set(expected), 'source/assumption classification')
            for item in c['inputs']:
                if item['key'] in expected:
                    value, unit = expected[item['key']]
                    require(Decimal(str(item['value'])) == Decimal(str(value)) and item['unit'] == unit, f'source input or unit: {cid}')
                    require(f"| {item['label']} | {item['value']} | {unit} |" in documents[c['input_document']]['text'], 'visible source return')
                else:
                    require(item['kind'] == 'assumption' and item['basis'] and item['unit'], 'unlabelled assumption')
            readers = planners | {c['steward'], 'luc'}
            require(set(c['readers']) == readers and all(set(documents[d]['reader_keys']) == readers for d in c['documents']), 'case readers')
            initial, current = workbooks[c['initial_workbook']], workbooks[c['current_workbook']]
            require(current['inputs'] == c['inputs'] and current['calculation'] == c['calculation'], 'current workbook lineage')
            require(initial['version'] == 1 and current['version'] == (2 if c['change'] else 1), 'workbook versions')
            if c['change']:
                differing = [(a['key'], a['value'], b['value']) for a, b in zip(initial['inputs'], current['inputs']) if a['value'] != b['value']]
                require(differing == [('high', 1.08, 1.1)] and c['change']['reason'], 'revision assumption or reason')
            order = [c['input_document'], c['initial_workbook'], 'pl-'+cid.lower()+'-recommendation-p1', c['review_document'], c['issued_document']]
            require(all(stamp(documents[a]['published_at']) < stamp(documents[b]['published_at']) for a,b in zip(order, order[1:])), 'document lifecycle chronology')
            require(stamp(documents[c['current_workbook']]['published_at']) < stamp(documents[c['review_document']]['published_at']), 'review precedes workbook')
            require(all(line in documents[order[2]]['text'] for line in result_lines(initial['calculation'])), 'draft summary lineage')
            for d in (c['review_document'], c['issued_document']):
                require(all(line in documents[d]['text'] for line in result_lines(c['calculation']))
                        and c['condition'] in documents[d]['text'] and c['recommendation'] in documents[d]['text'], 'issued summary or open condition')
            require(c['state'] in documents[c['issued_document']]['text'] and c['question'] in documents[c['review_document']]['text']
                    and c['answer'] in documents[c['review_document']]['text'], 'review disposition')
            thread = [messages[key] for key in c['messages']]
            require(len(thread) == 5 and thread[0]['from'] == c['steward']
                    and all(m.get('reply_to') == p['id'] for p,m in zip(thread,thread[1:])), 'case correspondence')
        for w in workbooks.values():
            d = documents[w['document']]
            check_workbook(archive.read(d['member']), w, cases[w['case']], d, people)
            require(all(line in d['text'] for line in result_lines(w['calculation'])), 'workbook preview lineage')
        require(registers['cases'] == [dict(planning_id=c['id'],title=c['title'],owner=people[c['owner']]['name'],state=c['state'],input_return=c['input_document'],current_workbook=c['current_workbook'],review=c['review_document'],issued=c['issued_document']) for c in cases.values()], 'case register join')
        require(registers['actions'] == [dict(action_id=c['id']+'-A1',planning_id=c['id'],owner=people[c['owner']]['name'],action=c['condition'],due_on='2026-09-30',status='open') for c in cases.values()], 'future action state')
        require(registers['results'] == [dict(result_id=c['id']+f'-R{i+1}', planning_id=c['id'], workbook=c['current_workbook'], cell=f'Calculation!B{i+2}',measure=v['label'],value=f"{v['value']:.2f}",unit=v['unit']) for c in cases.values() for i,v in enumerate(c['calculation'])], 'results register join')
        require(registers['versions'] == [dict(document=w['document'],planning_id=w['case'],version=str(w['version']),published_at=documents[w['document']]['published_at'],supersedes=w['document'][:-1]+'1' if w['version']==2 else '') for w in workbooks.values()], 'version register join')
        require(registers['meetings'] == [dict(meeting_id=g['id'],calendar=g['calendar'],pack=g['pack'],record=g['record'],cases=';'.join(g['cases'])) for g in manifest['meetings']], 'meeting register join')
    covered = []
    for group in manifest['meetings']:
        event = calendars[group['calendar']]
        start, end = stamp(event['start']), stamp(event['end'])
        pack, record = documents[group['pack']], documents[group['record']]
        require({event['organizer'], *event['attendees']} == planners and event['status'] == 'CONFIRMED'
                and stamp(pack['published_at']) <= stamp(event['created_at']) <= start < end <= stamp(record['published_at']) <= stamp(SNAPSHOT), 'meeting audience or chronology')
        require(set(pack['reader_keys']) == set(record['reader_keys']) == planners
                and f'{start:%H:%M}–{end:%H:%M}' in record['text'], 'meeting record time or readers')
        for cid in group['cases']:
            require(cases[cid]['issued_document'] in pack['text'] and cases[cid]['condition'] in record['text'], 'meeting paper/action join')
        covered.extend(group['cases'])
    require(Counter(covered) == Counter(cases.keys()), 'meeting coverage')
    visible = '\n'.join([m['subject']+'\n'+m['body'] for m in messages.values()]+[d['text'] for d in documents.values()])
    require(not any(s in visible.lower() for s in ('issue 128','scenario layer','author-only','openrae','shifter-scenarios','alloc-2026-09-w3','mwo-7742','crr-og2')), 'visible provenance or scenario evidence')
    return counts


if __name__ == '__main__':
    print('Planning records validated:', check_planning(ROOT, load(ROOT, 'workforce.yaml')['employees'], load(ROOT, 'people.yaml'),
          load(ROOT, 'mail-planning.yaml')['messages'], load(ROOT, 'documents-planning.yaml')['documents'], load(ROOT, 'calendars-planning.yaml')['events']))
