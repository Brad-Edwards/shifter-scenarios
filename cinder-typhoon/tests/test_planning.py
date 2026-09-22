"""Planning regression tests, including checksum-consistent Office corruption."""
import copy
from decimal import Decimal
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from validate_planning import ROOT, check_planning, formula_value, load, sha


class PlanningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = load(ROOT, 'workforce.yaml')['employees']
        cls.identity = load(ROOT, 'people.yaml')
        cls.content = (load(ROOT, 'planning.yaml'), load(ROOT, 'mail-planning.yaml')['messages'],
                       load(ROOT, 'documents-planning.yaml')['documents'], load(ROOT, 'calendars-planning.yaml')['events'])

    def check(self, content, root=ROOT):
        f, m, d, e = content
        return check_planning(root, self.roster, self.identity, m, d, e, f)

    def test_finished_records(self):
        self.assertEqual(self.check(self.content)['planning_histories'], 40)

    def test_rounding_and_formula_subset(self):
        self.assertEqual(formula_value('ROUND(B2*Inputs!B5,2)', {'B2':'436.5','Inputs!B5':'.95'}), Decimal('414.68'))
        self.assertEqual(formula_value('ROUND(-1.005,2)', {}), Decimal('-1.01'))
        with self.assertRaises(ValueError):
            formula_value('__import__("os")', {})

    def test_rejects_source_chronology_privacy_and_lineage_errors(self):
        def source(f,m,d,e): f['cases'][0]['inputs'][0]['value'] += 1
        def period(f,m,d,e): f['cases'][0]['selector']['period'] = 'ARWC-2026-M06'
        def unit(f,m,d,e): f['cases'][0]['inputs'][0]['unit'] = 'litres'
        def classification(f,m,d,e): f['cases'][0]['inputs'][0]['kind'] = 'assumption'
        def source_return(f,m,d,e): d[0]['text'] = d[0]['text'].replace('1133746','1133747')
        def future(f,m,d,e): m[0]['date'] = '2026-09-17T09:00:00-04:00'
        def audience(f,m,d,e): d[0]['reader_keys'].append('rowan')
        def attachment(f,m,d,e): m[0]['attachments'] = [f['cases'][0]['issued_document']]
        def parent(f,m,d,e): m[1]['reply_to'] = m[5]['id']
        def draft(f,m,d,e):
            ref = 'pl-arwc-pln-26-01-recommendation-p1'
            next(x for x in d if x['id']==ref)['text'] = 'Later workbook supersedes this draft.'
        def summary(f,m,d,e):
            next(x for x in d if x['id']==f['cases'][0]['issued_document'])['text'] = 'Approved. No conditions.'
        def late_workbook(f,m,d,e):
            next(x for x in d if x['id']==f['cases'][0]['current_workbook'])['published_at'] = '2026-09-09T09:00:00-04:00'
        def meeting(f,m,d,e): e[0]['end'] = '2026-09-14T11:45:00-04:00'
        def leak(f,m,d,e): m[0]['body'] += '\nIssue 128 is now complete.'
        mutations = [source,period,unit,classification,source_return,future,audience,attachment,parent,draft,summary,late_workbook,meeting,leak]
        for mutate in mutations:
            with self.subTest(mutation=mutate.__name__):
                content = copy.deepcopy(self.content)
                mutate(*content)
                with self.assertRaises(ValueError): self.check(content)

    def test_corruption_with_updated_checksums(self):
        for corruption in ('formula', 'cache', 'action'):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/'authoring').symlink_to(ROOT/'authoring', target_is_directory=True)
                (root/'documents').mkdir()
                for path in (ROOT/'documents').iterdir():
                    if path.name != 'planning-records.zip': (root/'documents'/path.name).symlink_to(path)
                content = copy.deepcopy(self.content)
                f,m,d,e = content
                with zipfile.ZipFile(ROOT/'documents/planning-records.zip') as archive:
                    members = {n:archive.read(n) for n in archive.namelist()}
                if corruption == 'action':
                    member = 'registers/actions.csv'
                    members[member] = members[member].replace(b',open\n', b',complete\n', 1)
                    f['tables']['actions']['sha256'] = sha(members[member])
                    expected = 'future action state'
                else:
                    member = 'workbooks/ARWC-PLN-26-01-v1.xlsx'
                    with zipfile.ZipFile(io.BytesIO(members[member])) as office:
                        parts = {n:office.read(n) for n in office.namelist()}
                    sheet = 'xl/worksheets/sheet3.xml'
                    before = parts[sheet]
                    if corruption == 'formula':
                        parts[sheet] = before.replace(b'ROUND(Inputs!B2/Inputs!B3,2)', b'ROUND(Inputs!B2/Inputs!B3,2)+1', 1)
                    else:
                        parts[sheet] = before.replace(b'</f><v>12458.75</v>', b'</f><v>12459.75</v>', 1)
                    self.assertNotEqual(before, parts[sheet])
                    output = io.BytesIO()
                    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as office:
                        for n,raw in parts.items(): office.writestr(n,raw)
                    members[member] = output.getvalue()
                    expected = 'cached formula mismatch'
                next(x for x in d if x.get('member')==member)['binary_sha256'] = sha(members[member])
                with zipfile.ZipFile(root/'documents/planning-records.zip','w',zipfile.ZIP_DEFLATED) as archive:
                    for n,raw in members.items(): archive.writestr(n,raw)
                with self.assertRaisesRegex(ValueError, expected): self.check(content,root)


if __name__ == '__main__':
    unittest.main()
