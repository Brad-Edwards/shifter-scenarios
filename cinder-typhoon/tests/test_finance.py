"""Adversarial finance tests: authority, settlement, privacy, and real binary values."""
import copy
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
import yaml
from validate_finance import check_finance

ROOT = Path(__file__).resolve().parents[1] / 'assets/narrative'


class FinanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def load(name):
            return yaml.safe_load((ROOT / 'authoring' / name).read_text())
        cls.identity = load('people.yaml')
        cls.roster = load('workforce.yaml')['employees']
        cls.mail = load('mail-finance.yaml')['messages']
        cls.docs = load('documents-finance.yaml')['documents']
        cls.manifest = load('finance.yaml')

    def check(self, manifest, mail, docs, root=ROOT):
        return check_finance(root, self.identity, self.roster, mail, docs, manifest)

    def test_finished_finance_records(self):
        result = self.check(self.manifest, self.mail, self.docs)
        self.assertEqual(result['supplier_transactions'] + result['expense_claims'], 180)

    def test_rejects_financial_and_audience_errors(self):
        def invoice(f, kind):
            return next(i for i in f['invoices'] if i['kind'] == kind)
        def doc(docs, key):
            return next(d for d in docs if d['id'] == key)
        def service_price(f, m, d): invoice(f, 'service')['amount_cents'] += 100
        def licence_unsigned(f, m, d): f['licences'][0]['accepted_at'] = '2026-07-01'
        def licence_price(f, m, d): invoice(f, 'licence')['amount_cents'] += 100
        def premature_acceptance(f, m, d): invoice(f, 'project_acceptance')['issued'] = '2026-07-01'
        def future_project(f, m, d): invoice(f, 'project_acceptance')['authority'] = 'COM-2026-007'
        def wrong_account(f, m, d): f['invoices'][0]['account'] = 'K-C-002'
        def cash_early(f, m, d): f['allocations'][0]['date'] = '2026-06-01'
        def cash_excess(f, m, d): f['allocations'][0]['amount_cents'] = 100000000
        def purchase_early(f, m, d): f['purchases'][0]['paid_on'] = '2026-06-01'
        def partial_paid(f, m, d):
            p = next(p for p in f['purchases'] if p['state'] == 'held_partial_delivery')
            p['paid_on'] = '2026-09-01'; p['payment_cents'] = p['amount_cents']
        def purchase_total(f, m, d): f['purchases'][0]['quantity'] += 1
        def self_approval(f, m, d): f['claims'][0]['manager'] = f['claims'][0]['employee']
        def receipt_math(f, m, d): f['claims'][0]['excluded_cents'] = 0
        def claim_early(f, m, d): f['claims'][0]['paid_on'] = '2026-07-01'
        def payroll_tax(f, m, d): f['payroll_runs'][0]['withheld_cents'] += 100
        def payroll_future(f, m, d): f['payroll_runs'][0]['paid_on'] = '2026-09-28'
        def payroll_reader(f, m, d): doc(d, 'finance-payroll-control')['reader_keys'].append('rowan')
        def payroll_attachment(f, m, d):
            next(x for x in m if x['to'] == ['priya'])['attachments'] = ['finance-payroll-control']
        def internal_ancestry(f, m, d):
            next(x for x in m if x['to'] == ['priya'])['reply_to'] = next(x['id'] for x in m if x['to'] == ['kwm057'])
        def journal_missing(f, m, d): f['journals'].pop()
        def false_opening(f, m, d): f['opening_balances_cents']['Deferred service'] += 1
        def statement(f, m, d): doc(d, 'statement-arwc')['text'] = 'Balance zero.\n'
        def pdf_text(f, m, d): doc(d, 'ko-26-0001')['text'] += 'Wrong extra line\n'
        def pdf_hash(f, m, d): doc(d, 'ko-26-0001')['binary_sha256'] = '0' * 64
        def formula_manifest(f, m, d):
            formulas = f['workbook_formulae']['finance-accounts-budget']
            next(iter(formulas.values()))['value'] += 1
        cases = [service_price, licence_unsigned, licence_price, premature_acceptance, future_project,
                 wrong_account, cash_early, cash_excess, purchase_early, partial_paid, purchase_total,
                 self_approval, receipt_math, claim_early, payroll_tax, payroll_future, payroll_reader,
                 payroll_attachment, internal_ancestry, journal_missing, false_opening, statement,
                 pdf_text, pdf_hash, formula_manifest]
        for mutate in cases:
            with self.subTest(mutation=mutate.__name__):
                f, m, d = copy.deepcopy((self.manifest, self.mail, self.docs))
                mutate(f, m, d)
                with self.assertRaises(ValueError): self.check(f, m, d)

    def test_rejects_changed_office_bytes_even_with_updated_digest(self):
        # Corrupt the cached total while keeping a valid ZIP and updating the author digest.
        # This must be caught by actual formula evaluation, not a checksum mismatch.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'authoring').symlink_to(ROOT / 'authoring', target_is_directory=True)
            (root / 'documents').mkdir()
            with zipfile.ZipFile(ROOT / 'documents/finance-records.zip') as archive:
                members = {n: archive.read(n) for n in archive.namelist()}
            name = 'finance-accounts-budget.xlsx'
            with zipfile.ZipFile(io.BytesIO(members[name])) as office:
                parts = {n: office.read(n) for n in office.namelist()}
            sheet = 'xl/worksheets/sheet1.xml'
            before = parts[sheet]
            parts[sheet] = before.replace(b'<f>B2+C2-D2</f><v>', b'<f>B2+C2-D2+100</f><v>', 1)
            self.assertNotEqual(before, parts[sheet])
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
                for key, value in parts.items(): archive.writestr(key, value)
            members[name] = output.getvalue()
            with zipfile.ZipFile(root / 'documents/finance-records.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
                for key, value in members.items(): archive.writestr(key, value)
            docs = copy.deepcopy(self.docs)
            d = next(d for d in docs if d['id'] == 'finance-accounts-budget')
            d['binary_sha256'] = hashlib.sha256(members[name]).hexdigest()
            with self.assertRaisesRegex(ValueError, 'cached formula mismatch'):
                self.check(self.manifest, self.mail, docs, root)


if __name__ == '__main__':
    unittest.main()
