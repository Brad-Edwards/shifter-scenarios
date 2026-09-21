"""Reject broken retail joins and financial or privacy boundaries in finished records."""
from pathlib import Path
import unittest
import yaml
from validate_service_accounts import check_population, check_service_accounts, load_tables

ROOT = Path(__file__).resolve().parents[1] / 'assets/narrative'


class ServiceAccountsIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = load_tables(ROOT)

    def reject(self, table, position, updates, error):
        row = self.tables[table][position]
        before = dict(row)
        try:
            row.update(updates)
            with self.assertRaisesRegex(ValueError, error):
                check_population(self.tables)
        finally:
            row.clear(); row.update(before)

    def test_complete_population(self):
        check_population(self.tables)

    def test_population_and_identity_boundaries(self):
        self.reject('accounts', 0, {'customer_id': self.tables['accounts'][1]['customer_id']}, 'customer identity')
        self.reject('contacts', 0, {'email': 'private@example.com'}, 'contact boundary')
        self.reject('service-points', 0, {'estimated_residents': '4'}, 'district population')
        self.reject('account-services', 0, {'account_id': 'ARWC-A-H30000'}, 'district responsibility')
        self.reject('account-services', 0, {'effective_from': '2026-05-01'}, 'responsibility date')

    def test_meter_lifetimes_and_billing(self):
        self.reject('readings', 0, {'read_at': '2000-01-01T00:00:00-04:00'}, 'reading lifetime')
        self.reject('readings', 1, {'register_m3': '-1'}, 'reading lifetime')
        self.reject('meters', 1, {'predecessor_id': 'ARWC-M-999999'}, 'replacement continuity')
        index = next(i for i, x in enumerate(self.tables['invoice-lines']) if x['charge'] == 'usage')
        check = next(x for x in self.tables['meters'] if x['role'] == 'check')
        self.reject('invoice-lines', index, {'meter_id': check['meter_id']}, 'check or unrelated meter billed')
        self.reject('invoice-lines', index, {'end_reading_id': self.tables['invoice-lines'][index]['start_reading_id']},
                    'usage interval')

    def test_invoice_receipt_and_balance_reconciliation(self):
        self.reject('invoice-lines', 0, {'amount_usd': '25.00'}, 'line arithmetic')
        self.reject('invoice-lines', 0, {'unit_price_usd': '25.00', 'amount_usd': '25.00'}, 'fixed tariff basis')
        self.reject('invoices', 0, {'tax_usd': '1.00'}, 'invoice reconciliation')
        self.reject('invoices', 0, {'due_on': '2026-07-22'}, 'invoice cadence')
        self.reject('allocations', 0, {'invoice_id': self.tables['invoices'][0]['invoice_id']}, 'cross-account allocation')
        self.reject('allocations', 0, {'amount_usd': '999999.00'}, 'overallocated receipt')
        self.reject('opening-balances', 0, {'net_balance_usd': '0.00'}, 'opening balance arithmetic')

    def test_changes_and_customer_delivery(self):
        self.reject('changes', 0, {'authorized_at': '2026-09-16T09:00:00-04:00'}, 'change consent')
        self.reject('changes', 0, {'after': 'email'}, 'change not applied|change consent')
        self.reject('statement-deliveries', 0, {'recipient': 'wrong@customers.arwc.test'}, 'delivery privacy')

    def test_private_table_audience(self):
        identity = yaml.safe_load((ROOT/'authoring/people.yaml').read_text())
        roster = yaml.safe_load((ROOT/'authoring/workforce.yaml').read_text())['employees']
        mail = yaml.safe_load((ROOT/'authoring/mail-service-accounts.yaml').read_text())['messages']
        docs = yaml.safe_load((ROOT/'authoring/documents-service-accounts.yaml').read_text())['documents']
        item = next(d for d in docs if d['id'] == 'service-data-contacts')
        item['reader_keys'].append('priya')
        with self.assertRaisesRegex(ValueError, 'CSV reader scope'):
            check_service_accounts(ROOT, identity, roster, mail, docs, self.tables)


if __name__ == '__main__':
    unittest.main()
