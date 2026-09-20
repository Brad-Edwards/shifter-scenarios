"""Reconcile the finished finance records, binary documents, and restricted readers."""
from __future__ import annotations
import ast
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import csv
import hashlib
import io
import re
import xml.etree.ElementTree as ET
import zipfile
import yaml
from pypdf import PdfReader

FIN = {'kwm056', 'kwm057'}
BOARD = FIN | {'kwm053', 'leah'}
PAY = FIN | {'kwm054', 'kwm055', 'leah'}
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def require(ok, why):
    if not ok:
        raise ValueError('Finance: ' + why)


def rounded(value):
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def usd(cents):
    return f'{Decimal(cents) / 100:,.2f}'


def normalized(text):
    return ' '.join(text.split())


def workbook_cells(raw):
    """Read actual Office XML, including cached formula results and sheet visibility."""
    sheets = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(archive.testzip() is None, 'corrupt Office archive')
        require('[Content_Types].xml' in archive.namelist(), 'not an Office workbook')
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            for item in ET.fromstring(archive.read('xl/sharedStrings.xml')):
                strings.append(''.join(item.itertext()))
        book = ET.fromstring(archive.read('xl/workbook.xml'))
        for n, sheet in enumerate(book.find('s:sheets', NS), 1):
            require(sheet.get('state', 'visible') == 'visible', 'hidden finance sheet')
            tree = ET.fromstring(archive.read(f'xl/worksheets/sheet{n}.xml'))
            cells = {}
            for cell in tree.findall('.//s:c', NS):
                value = cell.find('s:v', NS)
                formula = cell.find('s:f', NS)
                text = value.text if value is not None else ''
                if cell.get('t') == 's':
                    value = strings[int(text)]
                elif text:
                    value = Decimal(text)
                else:
                    value = ''
                cells[cell.get('r')] = (value, formula.text if formula is not None else None)
            sheets[sheet.get('name')] = cells
    return sheets


def formula_value(formula, cells):
    """Evaluate only the small arithmetic/SUM subset used by these two workbooks."""
    def value(key):
        item = cells[key][0]
        require(isinstance(item, Decimal), 'formula references nonnumeric cell')
        return item
    def sum_range(match):
        a, start, b, end = match.groups()
        require(a == b, 'unexpected formula range')
        return str(sum(value(f'{a}{r}') for r in range(int(start), int(end) + 1)))
    expression = re.sub(r'SUM\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)', sum_range, formula)
    expression = re.sub(r'\b[A-Z]+\d+\b', lambda m: str(value(m.group())), expression)
    def calc(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return Decimal(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -calc(node.operand)
        if isinstance(node, ast.BinOp):
            a, b = calc(node.left), calc(node.right)
            if isinstance(node.op, ast.Add): return a + b
            if isinstance(node.op, ast.Sub): return a - b
            if isinstance(node.op, ast.Mult): return a * b
            if isinstance(node.op, ast.Div): return a / b
        raise ValueError('Finance: unsupported workbook formula')
    return calc(ast.parse(expression, mode='eval').body)


def check_finance(root, identity, roster, mail, docs, manifest=None):
    manifest = manifest or yaml.safe_load((root / 'authoring/finance.yaml').read_text())
    f = manifest
    require(f['snapshot'] == identity['snapshot'] and f['period_start'] == '2026-07-01'
            and f['period_end'] == '2026-09-15' and f['currency'] == 'USD', 'reporting boundary drift')
    start, end = f['period_start'], f['period_end']
    staff = {p['key']: p for p in roster}
    contacts = identity['people'] | staff | identity['correspondents']
    fm = {m['id']: m for m in mail if m['story'] == 'finance'}
    fd = {d['id']: d for d in docs if d['story'] == 'finance'}
    require(len(fm) == f['counts']['messages'] == 1133, 'message inventory')
    require(len(fd) == f['counts']['documents'] == 562, 'document inventory')
    network = yaml.safe_load((root / 'authoring/business-network.yaml').read_text())
    orgs = {o['key']: o for o in network['organizations'] if o['kind'] == 'utility_customer'}
    commercial = yaml.safe_load((root / 'authoring/commercial.yaml').read_text())
    records = {r['id']: r for r in commercial['records']}
    quarter = {o['key']: rounded(Decimal(re.search(r'USD ([\d,]+) annual', o['terms'])[1].replace(',', '')) * 25)
               for o in orgs.values()}
    vendors = {v['key']: v for v in f['vendors']}
    require(len(vendors) == 8 and all(v['profile'] and v['sample'] for v in vendors.values()), 'supplier profiles')
    require(all(contacts[v['speaker']]['employer'] == key and v['domain'].endswith('.test')
                for key, v in vendors.items()), 'supplier identities')
    expected_readers = {key: set(BOARD) for key in fd}
    external_readers = {}
    expected_readers['finance-purchasing-rules'] |= {'kwm054', 'kwm055', 'kwm058'}
    expected_readers['finance-quarter-payment-authority'] = FIN | {'leah', 'kwm053'}
    expected_readers['finance-payroll-control'] = PAY
    licences = {l['id']: l for l in f['licences']}
    require(len(licences) == 12 and {l['organization'] for l in licences.values()} == set(orgs), 'licence inventory')
    for l in licences.values():
        o = orgs[l['organization']]
        require(l['accepted_at'] < l['start'] == '2026-01-01' and l['end'] == '2026-12-31'
                and l['monthly_cents'] * 12 == l['annual_cents'] and l['agreement'] == o['agreement_id'], 'licence authority')
        d = fd[l['document']]
        require(all(token in normalized(d['text']) for token in
                    (l['id'], usd(l['annual_cents']), usd(l['monthly_cents']), '/s/ Leah Calder-Voss',
                     '/s/ ' + contacts[l['contact']]['name'], 'does not replace or increase')), 'signed licence terms')
        expected_readers[d['id']] = FIN | {'leah', o['commercial_owner']}
        external_readers[d['id']] = {o['key']}
    invoices = {i['id']: i for i in f['invoices']}
    require(len(invoices) == 69 and len(invoices) == len(f['invoices']), 'invoice inventory')
    invoice_keys = set()
    for inv in invoices.values():
        o = orgs[inv['organization']]
        issued = date.fromisoformat(inv['issued'])
        require(inv['account'] == o['account_id'] and inv['issued'] <= end and
                date.fromisoformat(inv['due']) == issued + timedelta(days=30), 'invoice date/account')
        require(inv['tax_cents'] == 0 and 0 <= inv['opening_paid_cents'] <= inv['amount_cents'], 'invoice tax/opening allocation')
        kind = inv['kind']
        if kind == 'service':
            require(inv['authority'] == o['agreement_id'] and inv['amount_cents'] == quarter[o['key']]
                    and (issued.month - int(o['effective'][5:7])) % 3 == 0 and issued.day == 1,
                    'standing service amount or anniversary')
        elif kind == 'licence':
            l = licences[inv['authority']]
            require(l['organization'] == o['key'] and inv['amount_cents'] == l['monthly_cents']
                    and l['start'] <= inv['issued'] <= l['end'] and issued.day == 1, 'licence invoice authority')
        else:
            r = records[inv['authority']]
            require(r['kind'] == 'project' and r['status'] in ('completed', 'accepted_future')
                    and r['organization'] == o['key'] and inv['amount_cents'] * 2 == rounded(Decimal(r['accepted_amount_usd']) * 100)
                    and inv['issued'] >= r['accepted_at'][:10], 'unaccepted project invoice')
            if kind == 'project_acceptance':
                require(r['status'] == 'completed' and inv['issued'] >= r['delivery_accepted_at'][:10], 'premature acceptance invoice')
            else:
                require(kind == 'project_order', 'unknown invoice kind')
        unique = (inv['authority'], kind, inv['issued'])
        require(unique not in invoice_keys, 'duplicate billing milestone')
        invoice_keys.add(unique)
        d = fd[inv['document']]
        require(all(v in normalized(d['text']) for v in (inv['id'], inv['authority'], inv['issued'], inv['due'],
                    'TOTAL DUE USD ' + usd(inv['amount_cents']))), 'invoice PDF/ledger mismatch')
        expected_readers[d['id']] = FIN | {o['commercial_owner']}
        external_readers[d['id']] = {o['key']}
        if o['key'] == 'arwc': expected_readers[d['id'] + '-arwc'] = {'priya', 'theo'}
    require(Counter(i['kind'] for i in invoices.values()) ==
            {'service': 17, 'licence': 36, 'project_order': 10, 'project_acceptance': 6}, 'billing coverage')
    paid = Counter()
    for a in f['allocations']:
        i = invoices[a['invoice']]
        require(max(start, i['issued']) <= a['date'] <= end and a['amount_cents'] > 0, 'cash allocation chronology')
        paid[i['id']] += a['amount_cents']
        require(paid[i['id']] + i['opening_paid_cents'] <= i['amount_cents'], 'overallocated customer payment')
    require(sum(i['amount_cents'] - i['opening_paid_cents'] for i in invoices.values() if i['issued'] < start)
            == f['opening_balances_cents']['Receivables'], 'opening AR')
    opening_service = 0
    for i in invoices.values():
        if i['kind'] == 'service' and i['issued'] < start:
            third = rounded(Decimal(i['amount_cents']) / 3)
            opening_service += i['amount_cents'] - third * (7 - int(i['issued'][5:7]))
    require(opening_service == -f['opening_balances_cents']['Deferred service'], 'opening unearned service')
    require(sum(i['amount_cents'] for i in invoices.values() if i['issued'] < start and i['kind'] == 'project_order')
            == -f['opening_balances_cents']['Deferred project'], 'opening project advances')
    for o in orgs.values():
        key = 'statement-' + o['key']
        expected_readers[key] = FIN | {o['commercial_owner']}
        external_readers[key] = {o['key']}
        rows = [i for i in invoices.values() if i['organization'] == o['key']]
        opening = sum(i['amount_cents'] - i['opening_paid_cents'] for i in rows if i['issued'] < start)
        billed = sum(i['amount_cents'] for i in rows if i['issued'] >= start)
        cash = sum(paid[i['id']] for i in rows)
        require(all(t in normalized(fd[key]['text']) for t in
                    ('Opening receivable USD ' + usd(opening), 'Invoices this period USD ' + usd(billed),
                     'Cash allocated USD ' + usd(cash), 'CLOSING RECEIVABLE USD ' + usd(opening + billed - cash))),
                'customer statement reconciliation')
    expected_readers['statement-arwc-arwc'] = {'priya', 'theo'}
    require(len(f['purchases']) == 84 and len(f['claims']) == 96, 'transaction volume')
    for p in f['purchases']:
        require(p['vendor'] in vendors and p['owner'] != p['approver'] and p['approver'] == 'kwm053', 'purchase approval identity')
        require(p['approved'] <= p['ordered'] <= p['received'] <= p['invoiced'] <= end, 'purchase/receipt chronology')
        require(p['quantity'] * p['unit_cents'] == p['amount_cents'] and
                0 < p['received_quantity'] <= p['quantity'], 'purchase line arithmetic')
        if p['paid_on']:
            require(p['approved'] <= p['received'] <= p['paid_on'] <= end and
                    p['payment_cents'] == p['amount_cents'] and p['received_quantity'] == p['quantity'], 'payment before approval/receipt')
        else:
            require(p['payment_cents'] == 0, 'unpaid purchase has cash')
        for key in p['documents']:
            expected_readers[key] = FIN | {p['owner'], p['approver']}
            if not key.endswith('-receipt'): external_readers[key] = {p['vendor']}
        require('TOTAL USD ' + usd(p['amount_cents']) in normalized(fd[p['id'].lower() + '-invoice']['text']), 'supplier invoice amount')
        require(usd(p['unit_cents']) in fd[p['id'].lower()]['text'] and
                usd(p['amount_cents']) in fd[p['id'].lower()]['text'], 'order price authority')
        if p['vendor'] == 'orrenvale':
            require(p['amount_cents'] == 190000 and 'no FieldKest production' in fd[p['id'].lower()]['text'], 'internal IT contract drift')
    for c in f['claims']:
        require(c['manager'] == staff[c['employee']]['manager'] and c['employee'] != c['manager'], 'claim self-approval')
        require(staff[c['employee']]['start_date'] <= c['incurred'] <= c['submitted'] <= c['approved'] <= end, 'claim employment/approval chronology')
        require(c['receipt_cents'] - c['excluded_cents'] == c['amount_cents'] > 0, 'claim arithmetic')
        if c['paid_on']: require(c['approved'] <= c['paid_on'] <= end, 'claim paid before approval')
        require('REIMBURSE USD ' + usd(c['amount_cents']) in fd[c['id'].lower()]['text'], 'claim document amount')
        require('TOTAL PAID USD ' + usd(c['receipt_cents']) in normalized(fd[c['id'].lower() + '-receipt']['text']), 'merchant receipt amount')
        for key in c['documents']: expected_readers[key] = FIN | {c['employee'], c['manager']}
    for p in f['opening_payables']:
        require(p['approved'] <= p['received'] < start <= p['paid_on'] <= end, 'opening AP receipt/payment')
        expected_readers[p['document']] = FIN | {'kwm053'}
    require(sum(p['amount_cents'] for p in f['opening_payables']) == -f['opening_balances_cents']['Payables'], 'opening AP amount')
    require(len(f['payroll_runs']) == 2, 'future payroll marked paid')
    for p in f['payroll_runs']:
        require(p['headcount'] == len([x for x in roster if x['employer'] == 'keplerops']) == 64
                and p['gross_cents'] == f['monthly_gross_cents'], 'payroll roster/gross')
        require(p['net_cents'] + p['withheld_cents'] == p['gross_cents'] and
                p['withheld_cents'] * 5 == p['gross_cents'] and p['employer_cents'] * 100 == p['gross_cents'] * 15
                and p['total_cash_cents'] == p['gross_cents'] + p['employer_cents'], 'payroll arithmetic')
        require(start <= p['approved'] < p['paid_on'] <= end and p['month'] in (7, 8), 'payroll payment chronology')
        expected_readers[p['document']] = PAY
        expected_readers[p['document'] + '-proposal'] = PAY
        require('TOTAL CASH USD ' + usd(p['total_cash_cents']) in normalized(fd[p['document']]['text']), 'payroll PDF arithmetic')
    # Independent postings reconstructed from business events, not just a balanced debit/credit total.
    expected = []
    def post(ref, day, debit, credit, amount):
        if amount: expected.append((ref, day, debit, credit, amount))
    for i in invoices.values():
        if i['issued'] >= start:
            post(i['id'], i['issued'], 'Receivables', {'service': 'Deferred service', 'licence': 'Deferred licence',
                 'project_order': 'Deferred project', 'project_acceptance': 'Project revenue'}[i['kind']], i['amount_cents'])
    for r in records.values():
        if r['kind'] == 'project' and r['status'] == 'completed':
            post(r['id'], r['delivery_accepted_at'][:10], 'Deferred project', 'Project revenue', rounded(Decimal(r['accepted_amount_usd']) * 50))
    for a in f['allocations']: post(a['id'], a['date'], 'Cash', 'Receivables', a['amount_cents'])
    monthly_vendors = {'orrenvale': 190000, 'velquorin': 600000, 'darsovell': 420000, 'pelravin': 74000}
    for p in f['purchases']:
        post(p['id'], p['invoiced'], 'Prepaid services' if p['vendor'] in monthly_vendors else 'Operating expense', 'Payables', p['amount_cents'])
        if p['paid_on']: post(p['id'] + '-PAY', p['paid_on'], 'Payables', 'Cash', p['payment_cents'])
        if p['received_quantity'] < p['quantity']:
            post(p['id'] + '-HOLD', p['received'], 'Goods awaiting receipt', 'Operating expense',
                 (p['quantity'] - p['received_quantity']) * p['unit_cents'])
    for c in f['claims']:
        post(c['id'], c['approved'], 'Operating expense', 'Employee payable', c['amount_cents'])
        if c['paid_on']: post(c['id'] + '-PAY', c['paid_on'], 'Employee payable', 'Cash', c['amount_cents'])
    for p in f['opening_payables']: post(p['id'], p['paid_on'], 'Payables', 'Cash', p['amount_cents'])
    for p in f['payroll_runs']: post(p['id'], p['paid_on'], 'Payroll expense', 'Cash', p['total_cash_cents'])
    post('PAY-SEP-ACCRUAL', end, 'Payroll expense', 'Payroll accrued', f['monthly_gross_cents'] * 115 // 200)
    for month, day in ((7, '2026-07-31'), (8, '2026-08-31'), (9, end)):
        fraction = Decimal('.5') if month == 9 else Decimal(1)
        for o in orgs.values():
            q = quarter[o['key']]; third = rounded(Decimal(q) / 3)
            amount = q - 2 * third if (month - int(o['effective'][5:7])) % 3 == 2 else third
            post(o['agreement_id'] + f'-E{month}', day, 'Deferred service', 'Service revenue', rounded(amount * fraction))
        for l in licences.values(): post(l['id'] + f'-E{month}', day, 'Deferred licence', 'Licence revenue', rounded(l['monthly_cents'] * fraction))
        for vendor, amount in monthly_vendors.items(): post(vendor + f'-E{month}', day, 'Operating expense', 'Prepaid services', rounded(amount * fraction))
        post(f'DEP-2026-{month:02d}', day, 'Operating expense', 'Fixed assets net', rounded(250000 * fraction))
    actual = [(j['reference'], j['date'], j['debit'], j['credit'], j['amount_cents']) for j in f['journals']]
    require(Counter(expected) == Counter(actual), 'journal does not match business events')
    opening = f['opening_balances_cents']
    require(sum(opening.values()) == 0 and opening['Cash'] == 120000000, 'opening trial balance')
    balance = Counter(opening)
    for j in f['journals']:
        require(start <= j['date'] <= end and j['amount_cents'] > 0, 'journal period/amount')
        balance[j['debit']] += j['amount_cents']; balance[j['credit']] -= j['amount_cents']
    require(dict(balance) == f['closing_balances_cents'] and sum(balance.values()) == 0, 'closing trial balance')
    require(balance['Receivables'] == sum(i['amount_cents'] - i['opening_paid_cents'] - paid[i['id']] for i in invoices.values()), 'AR subledger')
    require(-balance['Payables'] == sum(p['amount_cents'] - p['payment_cents'] for p in f['purchases']), 'AP subledger')
    profit = -sum(v for k, v in balance.items() if k.endswith('revenue')) - sum(v for k, v in balance.items() if k.endswith('expense'))
    require(profit == f['operating_profit_cents'] > 0 and balance['Cash'] > 0, 'profitability and cash')
    require('OPERATING PROFIT BEFORE CORPORATE TAX USD ' + usd(profit) in normalized(fd['finance-management-accounts']['text']), 'management PDF profit')
    require('CLOSING CASH USD ' + usd(balance['Cash']) in normalized(fd['finance-cash-statement']['text']), 'cash statement')
    require(all(f'{account}: USD {usd(amount)}' in fd['finance-opening']['text'] for account, amount in opening.items()), 'opening PDF amounts')
    require('TOTAL SUPPLIER PAYABLE USD ' + usd(-balance['Payables']) in normalized(fd['finance-supplier-statement']['text']), 'supplier statement')
    # Every financial record has an exact audience, including binary counterpart copies.
    for key, d in fd.items():
        require(d['audience'] == 'restricted' and set(d['reader_keys']) == expected_readers[key], 'reader leak: ' + key)
        require(d.get('collection') == 'employment' if key.startswith(('pay-2026-', 'finance-payroll')) else d.get('collection', 'documents') == 'documents', 'personnel collection: ' + key)
    for m in fm.values():
        actors = [m['from']] + m['to']
        require(all(a not in staff or staff[a]['start_date'] <= m['date'][:10] for a in actors), 'speaker predates employment')
        outsiders = {contacts[a]['employer'] for a in actors if contacts[a]['employer'] != 'keplerops'}
        require(len(outsiders) <= 1, 'cross-customer/supplier correspondence')
        for key in m.get('attachments', []):
            require(outsiders <= external_readers.get(key, set()), 'private attachment sent outside finance: ' + key)
            if not outsiders:
                require(set(actors) <= expected_readers[key], 'private attachment recipient: ' + key)
        if outsiders:
            ancestor = m.get('reply_to')
            while ancestor:
                parent = fm[ancestor]
                parent_out = {contacts[a]['employer'] for a in [parent['from']] + parent['to'] if contacts[a]['employer'] != 'keplerops'}
                require(parent_out == outsiders, 'private reply ancestry exposed')
                ancestor = parent.get('reply_to')
    # Parse every real PDF and every sheet, compare extracted search text and content digests.
    with zipfile.ZipFile(root / 'documents/finance-records.zip') as archive:
        require(archive.testzip() is None and len(archive.namelist()) == f['counts']['binary_members'] == 283, 'binary archive inventory')
        require(set(archive.namelist()) == {d['member'] for d in fd.values() if 'archive' in d}, 'unbound binary')
        for d in fd.values():
            if 'archive' not in d: continue
            raw = archive.read(d['member'])
            require(hashlib.sha256(raw).hexdigest() == d['binary_sha256'], 'binary digest: ' + d['id'])
            if d['media_type'] == 'application/pdf':
                require(raw.startswith(b'%PDF-'), 'fake PDF')
                pdf = PdfReader(io.BytesIO(raw), strict=True)
                require(not pdf.is_encrypted and len(pdf.pages) > 0, 'unreadable PDF')
                text = '\n'.join(p.extract_text() for p in pdf.pages).rstrip() + '\n'
                require(text == d['text'], 'PDF search text differs')
                require(pdf.metadata.creation_date.date().isoformat() == d['published_at'][:10], 'PDF metadata date')
                require(all(word not in str(pdf.metadata).lower() for word in ('scenario', 'issue 120', 'codex', 'openai')), 'PDF provenance leak')
            else:
                sheets = workbook_cells(raw)
                actual_formulas = {}
                for name, cells in sheets.items():
                    for cell, (value, formula) in cells.items():
                        if formula:
                            require(abs(formula_value(formula, cells) - value) < Decimal('.000001'), 'workbook cached formula mismatch')
                            actual_formulas[f'{name}!{cell}'] = {'formula': formula, 'value': float(value)}
                require(actual_formulas == f['workbook_formulae'][d['id']], 'workbook formula inventory')
                if d['id'] == 'finance-accounts-budget':
                    tb = sheets['Trial balance']
                    for row in range(2, len(balance) + 2):
                        account = tb[f'A{row}'][0]
                        require(tb[f'E{row}'][0] * 100 == balance[account], 'workbook/TB mismatch')
                    require(sheets['Budget']['C5'][0] * 100 == profit, 'workbook/PDF profit mismatch')
                    for n, inv in enumerate(invoices.values(), 2):
                        cells = sheets['Receivables']
                        require(cells[f'A{n}'][0] == inv['id'] and cells[f'F{n}'][0] * 100 == inv['amount_cents'] - inv['opening_paid_cents'] - paid[inv['id']], 'workbook/AR mismatch')
                    for n, purchase in enumerate(f['purchases'], 2):
                        cells = sheets['Payables']
                        require(cells[f'A{n}'][0] == purchase['id'] and cells[f'E{n}'][0] * 100 == purchase['amount_cents'] - purchase['payment_cents'], 'workbook/AP mismatch')
                else:
                    cells = sheets['Department control']
                    require(cells['C8'][0] * 100 == f['monthly_gross_cents'] and cells['B8'][0] == 64, 'workbook/payroll mismatch')
    for key, rows in [('finance-journal', f['journals']), ('finance-cash-allocations', f['allocations'])]:
        parsed = list(csv.DictReader(io.StringIO(fd[key]['text'])))
        require(parsed == [{k: str(v) for k, v in row.items()} for row in rows], 'CSV/ledger mismatch')
    return f['counts']
