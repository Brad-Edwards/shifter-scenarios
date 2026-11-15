"""Protect ownership, original readers and inherited native access on import."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

with patch('runpy.run_path', return_value={name: Mock() for name in ('request', 'decode_ocs', 'dav', 'ocs')}):
    spec = importlib.util.spec_from_file_location('corporate_records', Path(__file__).with_name('seed-corporate-documents.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


class NativeDocumentImportTests(unittest.TestCase):
    def test_only_owned_unchanged_bytes_with_common_original_readers_are_selected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            content = b'ordinary original document'
            docs = [{'text': content.decode(), 'readers': ['alice', 'bob']},
                    {'content_base64': base64.b64encode(content).decode(), 'readers': ['bob', 'clara'], 'sha256': hashlib.sha256(content).hexdigest()}]
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'documents': docs}))
            with ZipFile(root / 'finance-records.zip', 'w') as archive:
                archive.writestr('record.md', content)
                archive.writestr('unassigned.md', b'other business data')
            real_path = Path
            with patch.object(module, 'SOURCE', root), patch.object(module, 'Path', side_effect=lambda p: manifest if p == '/seed/arwc-documents.json' else real_path(p)):
                selected = module.records()
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0][1], content)
            self.assertEqual(selected[0][2], {'bob'})

    def test_shared_parent_stops_import_before_users_or_file_contents(self):
        with patch.object(module, 'records', return_value=[('Retained corporate records/finance/record.md', b'data', {'alice'}, 'unused')]), \
             patch.object(module, 'shares', return_value=[{'share_type': 1}]), \
             patch.object(module, 'provision_users') as users, patch.object(module, 'import_record') as upload:
            with self.assertRaisesRegex(RuntimeError, 'parent is already shared'):
                module.seed()
            users.assert_not_called()
            upload.assert_not_called()

    def test_existing_record_cannot_have_public_or_excessive_access(self):
        content = b'ordinary original document'
        record = ('Retained corporate records/record.md', content, {'alice'}, hashlib.sha256(content).hexdigest())
        for share in ({'share_type': 3, 'permissions': 1}, {'share_type': 0, 'share_with': 'alice', 'permissions': 31},
                      {'share_type': 0, 'share_with': 'outsider', 'permissions': 1}):
            with patch.object(module, 'request', side_effect=[b'exists', content]) as request, \
                 patch.object(module, 'shares', return_value=[share]):
                with self.subTest(share=share), self.assertRaises(RuntimeError):
                    module.import_record(record)
                self.assertEqual([call.args[0] for call in request.call_args_list], ['HEAD', 'GET'])


if __name__ == '__main__':
    unittest.main()
