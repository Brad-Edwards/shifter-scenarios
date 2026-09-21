"""Mutation checks for the chronology and access failures raised in the slice review."""
from pathlib import Path
import unittest
import yaml
from validate_field_operations import check_records, check_field_operations, load_tables, load_service

ROOT = Path(__file__).resolve().parents[1]/'assets/narrative'


class FieldOperationsIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = load_tables(ROOT)
        cls.service = load_service(ROOT)
        cls.workforce = yaml.safe_load((ROOT/'authoring/workforce.yaml').read_text())['employees']

    def reject(self, table, index, updates, error):
        row = self.tables[table][index]
        before = dict(row)
        try:
            row.update(updates)
            with self.assertRaisesRegex(ValueError, error):
                check_records(self.tables, self.workforce, self.service)
        finally:
            row.clear(); row.update(before)

    def test_finished_records(self):
        check_records(self.tables, self.workforce, self.service)

    def test_roster_and_observation_chronology(self):
        self.reject('roster-river-treatment', 0, {'employee': 'awm029'}, 'duty effective date')
        self.reject('observations-P', 0, {'observed_at': '2026-09-16T09:00:00-04:00'}, 'future handover observation')
        self.reject('shifts-P', 0, {'open_requests': 'ARWC-OMR-0001'}, 'handover request knowledge')
        row = self.tables['roster-pine-treatment'][0]
        self.reject('roster-pine-treatment', 1, {'employee': row['employee']}, 'overlapping duty')

    def test_field_identity_and_supervision(self):
        self.reject('visits-P', 0, {'account_id': 'A-B-001'}, 'meter/account join')
        self.reject('visits-P', 0, {'site_id': 'ARWC-RW'}, 'field district join')
        self.reject('visits-P', 0, {'lead': 'owen'}, 'apprentice supervision')
        self.reject('training-owen', 0, {'authorization': 'independent'}, 'training authority')
        self.reject('training-owen', 0, {'start': '2026-08-03T09:30:00-04:00',
                                      'end': '2026-08-03T10:00:00-04:00'}, 'training visit join|overlapping field')

    def test_resources_custody_stock_and_intake(self):
        self.reject('bookings-P', 2, {'resource_id': self.tables['bookings-P'][0]['resource_id']}, 'resource collision')
        self.reject('samples-P', 0, {'handed_over_at': '2026-08-03T09:00:00-04:00'}, 'sample custody chronology')
        self.reject('stock-P', 0, {'closing': '200'}, 'stock arithmetic')
        self.reject('maintenance', 0, {'received_at': '2026-08-01T11:20:00-04:00'}, 'maintenance chronology')
        self.reject('dispatch-P', 0, {'complete': '8'}, 'dispatch reconciliation')
        self.reject('appointments-P', 0, {'serial': 'AW-UNKNOWN'}, 'appointment field extract')

    def test_filter_run_history(self):
        self.reject('operating-P', 0, {'run_hours': '0.00'}, 'filter run arithmetic')
        washed = next(i for i, r in enumerate(self.tables['operating-P']) if r['wash_started_at'])
        self.reject('operating-P', washed, {'returned_to_duty_at': '2026-09-16T10:00:00-04:00'},
                    'filter wash chronology')

    def test_reader_and_calendar_boundaries(self):
        a = ROOT/'authoring'
        mail = yaml.safe_load((a/'mail-field-operations.yaml').read_text())['messages']
        docs = yaml.safe_load((a/'documents-field-operations.yaml').read_text())['documents']
        events = yaml.safe_load((a/'calendars-field-operations.yaml').read_text())['events']
        d = next(d for d in docs if d['id'].startswith('op-training-'))
        d['reader_keys'].append('rosa')
        with self.assertRaisesRegex(ValueError, 'private training audience'):
            check_field_operations(ROOT, self.workforce, mail, docs, events)
        d['reader_keys'].remove('rosa')
        events[0]['end'] = '2026-08-03T08:00:00-04:00'
        with self.assertRaisesRegex(ValueError, 'appointment calendar'):
            check_field_operations(ROOT, self.workforce, mail, docs, events)


if __name__ == '__main__':
    unittest.main()
