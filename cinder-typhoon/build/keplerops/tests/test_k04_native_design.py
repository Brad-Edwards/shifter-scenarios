#!/usr/bin/env python3
"""Offline design checks for the native bundle-indexer K04 slice."""

from __future__ import annotations

import json
import re
from pathlib import Path
import unittest


ASSETS = Path(__file__).resolve().parents[3] / "assets/keplerops/opening/k-dev"
KEPLEROPS = Path(__file__).resolve().parents[1]
RUNTIME = KEPLEROPS / "runtime"


class K04NativeDesign(unittest.TestCase):
    def test_offline_reproducer_carries_sentinel_marker(self) -> None:
        binary_path = ASSETS / "indexer-client.json"
        client = json.loads(binary_path.read_text())
        self.assertEqual(client["schema"], "fieldkest.bundle-index-client/v1")
        self.assertIn("offline_reproducer", client)
        self.assertIn("route_key", client)
        # The binary must exist in the opening archive (k-dev-home.tar)
        # Its name is referenced by the client JSON
        binary_name = client["offline_reproducer"].split("/")[-1]
        self.assertEqual(binary_name, "fieldkest-bundle-indexer")
        # The route key must resolve in the native client reference
        client_ref = json.loads((RUNTIME / "client-references/indexer.json").read_text())
        all_routes = []
        for doc in client_ref.get("documents", {}).values():
            all_routes.extend(r["key"] for r in doc.get("routes", []))
        self.assertIn(client["route_key"], all_routes)

    def test_indexer_service_has_no_facade_endpoints(self) -> None:
        indexer = (RUNTIME / "indexer.py").read_text()
        # Indexer must call the real binary, not return hardcoded mutations
        self.assertIn("fieldkest-bundle-indexer", indexer)
        self.assertIn("native_result", indexer)
        # No hardcoded mutation sentinel in the response path
        self.assertNotIn('"sentinel": "mutated"', indexer)
        self.assertNotIn("'sentinel': 'mutated'", indexer)
        # Service delegates to the native binary for mutation state
        self.assertIn("native.returncode", indexer)

    def test_participant_surface_has_exact_reproducer(self) -> None:
        manifest_path = KEPLEROPS.parent / "participant-surface/manifests/keplerops.json"
        if not manifest_path.exists():
            self.skipTest("participant surface manifest not present in this environment")
        manifest = json.loads(manifest_path.read_text())
        all_paths = []
        for root in manifest.get("filesystem", {}).get("roots", []):
            for entry in root.get("entries", []):
                all_paths.append(entry.get("path", ""))
        reproducer_paths = [p for p in all_paths if "fieldkest-bundle-indexer" in p]
        self.assertTrue(reproducer_paths, "fieldkest-bundle-indexer not in participant surface")
        client_paths = [p for p in all_paths if "indexer-client.json" in p]
        self.assertTrue(client_paths, "indexer-client.json not in participant surface")


if __name__ == "__main__":
    unittest.main(verbosity=2)
