"""Check that native history import cannot pass on missing or unrelated data."""
import importlib.util
from pathlib import Path
import os
import unittest
from unittest.mock import patch

with patch.dict(os.environ, {"DOCUMENTS_ADMIN_PASSWORD": "unused-test-value"}):
    spec = importlib.util.spec_from_file_location("documents_seed", Path(__file__).with_name("seed-documents.py"))
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)


class HistoryImportTests(unittest.TestCase):
    def test_reads_only_versions_of_selected_native_file(self):
        base = "/remote.php/dav/versions/records-admin/versions/42/"
        metadata = b'<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><oc:fileid>42</oc:fileid></d:multistatus>'
        listing = f'<d:multistatus xmlns:d="DAV:"><d:response><d:href>{base}123</d:href></d:response><d:response><d:href>/unrelated/123</d:href></d:response></d:multistatus>'.encode()
        with patch.object(seed, "request", side_effect=(metadata, listing, b"P1")) as request:
            result = seed.version_digests("Drawing.svg")
        self.assertEqual(set(result), {"123"})
        self.assertEqual(request.call_args_list[-1].args, ("GET", base + "123"))
        self.assertTrue(all(call.args[0] in {"GET", "PROPFIND"} for call in request.call_args_list))

    def test_missing_native_file_id_fails(self):
        with patch.object(seed, "request", return_value=b'<d:multistatus xmlns:d="DAV:"/>'):
            with self.assertRaises(RuntimeError):
                seed.version_digests("Drawing.svg")

    def test_broken_listed_version_fails_validation(self):
        base = "/remote.php/dav/versions/records-admin/versions/42/"
        metadata = b'<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><oc:fileid>42</oc:fileid></d:multistatus>'
        listing = f'<d:multistatus xmlns:d="DAV:"><d:response><d:href>{base}124</d:href></d:response><d:response><d:href>{base}123</d:href></d:response></d:multistatus>'.encode()
        not_found = b'<?xml version="1.0"?><d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns"><s:exception>Sabre\\DAV\\Exception\\NotFound</s:exception></d:error>'
        with patch.object(seed, "request", side_effect=(metadata, listing, not_found)):
            with self.assertRaises(RuntimeError):
                seed.version_digests("Drawing.svg")

    def test_wrong_or_missing_version_content_fails(self):
        for versions in ({}, {"123": "0" * 64}):
            with self.subTest(versions=versions), patch.object(seed, "version_digests", return_value=versions):
                with self.assertRaises(RuntimeError):
                    seed.verify_versions("Drawing.svg", [b"P1", b"P2"])


if __name__ == "__main__":
    unittest.main()
