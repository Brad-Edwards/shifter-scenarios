#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import unittest
import zlib


PACK = Path(__file__).resolve().parents[3]
ASSETS = PACK / "assets/keplerops/opening/k-dev"
BUILD = PACK / "build/keplerops"


class K03NativeDesign(unittest.TestCase):
    def test_layered_bundle_resolves_to_native_s3_object(self) -> None:
        stage = (ASSETS / "staging-FKCOL-2841.bin").read_text()
        self.assertIn("FIELDKEST-STAGE/2", stage)
        values = dict(line.split("=", 1) for line in stage.splitlines() if "=" in line)
        powershell = zlib.decompress(base64.b64decode(values["payload"]))
        self.assertEqual(hashlib.sha256(powershell).hexdigest(), values["payload-sha256"])

        stage2 = re.search(rb"\$Stage2 = '([^']+)'", powershell)
        stage2_digest = re.search(rb"\$Stage2Sha256 = '([0-9a-f]+)'", powershell)
        self.assertIsNotNone(stage2)
        self.assertIsNotNone(stage2_digest)
        javascript = zlib.decompress(base64.b64decode(stage2.group(1)))
        self.assertEqual(hashlib.sha256(javascript).hexdigest(), stage2_digest.group(1).decode())

        encoded = re.search(rb'const encoded = "([^"]+)"', javascript)
        key = re.search(rb'const key = Buffer\.from\("([0-9a-f]+)", "hex"\)', javascript)
        self.assertIsNotNone(encoded)
        self.assertIsNotNone(key)
        cipher = base64.b64decode(encoded.group(1))
        key_bytes = bytes.fromhex(key.group(1).decode())
        compressed = bytes(value ^ key_bytes[index % len(key_bytes)] for index, value in enumerate(cipher))
        manifest = json.loads(zlib.decompress(compressed))

        collection = (ASSETS / "FKCOL-2841.json").read_bytes()
        self.assertEqual(manifest["endpoint"], "https://objects.keplerops.test")
        self.assertEqual(manifest["bucket"], "fieldlink-collections")
        self.assertEqual(manifest["object_key"], "callbacks/CB-17/FKCOL-2841.json")
        self.assertEqual(manifest["object_sha256"], hashlib.sha256(collection).hexdigest())

    def test_collection_is_seeded_into_real_storage_without_listing(self) -> None:
        prepare = (BUILD / "native-platform/prepare.py").read_text()
        seed = (BUILD / "native-platform/seed-objects.sh").read_text()
        self.assertIn("Read:fieldlink-collections", prepare)
        self.assertNotIn("List:fieldlink-collections", prepare)
        self.assertIn("fieldlink-collections", seed)
        self.assertIn("FKCOL-2841.json", seed)

    def test_retired_answer_endpoints_and_duplicate_record_are_absent(self) -> None:
        workbench = (BUILD / "runtime/workbench.py").read_text()
        config = json.loads((ASSETS / "workbench-service.json").read_text())
        helper = (ASSETS / "local-helper.md").read_text()
        for retired in ("/api/reconstruction", "/api/callback/collection"):
            self.assertNotIn(retired, workbench)
            self.assertNotIn(retired, helper)
        self.assertNotIn("reconstruction", config)
        self.assertNotIn("callback_collection", config)
        self.assertFalse((ASSETS / "collection-instructions.json").exists())


if __name__ == "__main__":
    unittest.main()
