"""Targeted corruption checks for retained correspondence and source artifacts."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import validate_narrative as validator


class NarrativeIntegrityTests(unittest.TestCase):
    def test_rejects_corrupted_content(self):
        def alter_attachment(root):
            p = root / 'generated/messages/k-workshop-1.eml'
            p.write_bytes(p.read_bytes().replace(b'Content-Disposition: attachment', b'Content-Disposition: inline'))

        def add_unrelated_mailbox_copy(root):
            p = root / 'generated/packages/keplerops-mail.json'
            data = json.loads(p.read_text())
            coverage = json.loads((root / 'story-coverage.json').read_text())
            private = coverage['messages']['k-lunch-2']['message_id']
            self.assertNotIn(private, data['mailboxes']['rowan.ito@keplerops.com']['folders']['INBOX'])
            data['mailboxes']['rowan.ito@keplerops.com']['folders']['INBOX'].append(private)
            p.write_text(json.dumps(data))
            # Rebind the catalog to the mutated bytes, so the audience check must fail.
            import hashlib
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            catalog_path = root / 'artifact-catalog.json'
            catalog = json.loads(catalog_path.read_text())
            for entry in catalog['artifacts']:
                if entry['content_ref'] == 'narrative-keplerops.mail':
                    entry['sha256'] = digest
                    entry['source']['version'] = 'sha256-' + digest
            catalog_path.write_text(json.dumps(catalog))

        def change_source(root):
            p = root / 'generated/packages/arwc-documents.json'
            p.write_bytes(p.read_bytes() + b' ')

        def detach_reply(root):
            p = root / 'generated/messages/k-bike-3.eml'
            p.write_bytes(p.read_bytes().replace(b'In-Reply-To:', b'X-Previous-Message:'))

        for mutate in (alter_attachment, add_unrelated_mailbox_copy, change_source, detach_reply):
            with self.subTest(mutation=mutate.__name__), tempfile.TemporaryDirectory() as temp:
                pack = Path(temp)
                root = pack / 'assets/narrative'
                shutil.copytree(validator.ROOT, root)
                mutate(root)
                with patch.object(validator, 'ROOT', root), patch.object(validator, 'PACK', pack):
                    with self.assertRaises(ValueError):
                        validator.check_assets()


if __name__ == '__main__':
    unittest.main()
