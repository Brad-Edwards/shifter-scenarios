#!/usr/bin/env python3
"""Offline design checks for the native bundle-indexer K04 slice."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ASSETS = Path(__file__).resolve().parents[3] / "assets/keplerops/opening/k-dev"
KEPLEROPS = Path(__file__).resolve().parents[1]
RUNTIME = KEPLEROPS / "runtime"


class K04NativeDesign(unittest.TestCase):
    def test_indexer_client_references_fki_format(self) -> None:
        client = json.loads((ASSETS / "indexer-client.json").read_text())
        self.assertEqual(client["schema"], "fieldkest.bundle-index-client/v1")
        self.assertIn("bundle_format", client)
        self.assertEqual(client["bundle_format"]["magic"], "FKI\\x01")
        binary_name = client["offline_reproducer"].split("/")[-1]
        self.assertEqual(binary_name, "fieldkest-bundle-indexer")
        # Route must be in the native client reference.
        client_ref = json.loads((RUNTIME / "client-references/indexer.json").read_text())
        all_routes = []
        for doc in client_ref.get("documents", {}).values():
            all_routes.extend(r["key"] for r in doc.get("routes", []))
        self.assertIn(client["route_key"], all_routes)

    def test_indexer_service_uses_bundle_hex_not_raw_allocation(self) -> None:
        indexer = (RUNTIME / "indexer.py").read_text()
        # Service must accept bundle_hex.
        self.assertIn("bundle_hex", indexer)
        # Service must NOT expose the allocation directly.
        self.assertNotIn('"allocated_length"', indexer)
        self.assertNotIn("allocated_length", indexer)
        # Service must call the real binary with the bundle.
        self.assertIn("fieldkest-bundle-indexer", indexer)
        self.assertNotIn('"sentinel": "mutated"', indexer)

    def test_binary_source_has_fki_format_not_direct_allocation(self) -> None:
        source = (RUNTIME / "bundle_indexer.c").read_text()
        # Binary must parse .fki magic, not accept raw allocated_length argument.
        self.assertIn("FKI", source)
        self.assertIn("alloc_entries", source)
        self.assertIn("index_entries", source)
        # Must NOT directly expose the boundary value or the sentinel string as a solution hint.
        self.assertNotIn("allocated == sizeof", source)
        self.assertNotIn("allocated == 32", source)

    def test_participant_surface_has_correct_reproducer(self) -> None:
        manifest_path = KEPLEROPS.parent / "participant-surface/manifests/keplerops.json"
        if not manifest_path.exists():
            self.skipTest("participant surface manifest not present in this environment")
        manifest = json.loads(manifest_path.read_text())
        all_paths = []
        for root in manifest.get("filesystem", {}).get("roots", []):
            for entry in root.get("entries", []):
                all_paths.append(entry.get("path", ""))
        self.assertTrue(any("fieldkest-bundle-indexer" in p for p in all_paths))
        self.assertTrue(any("indexer-client.json" in p for p in all_paths))


if __name__ == "__main__":
    unittest.main(verbosity=2)
