#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("arwc_check_manifest", HERE / "check_manifest.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load ARWC challenge manifest validator")
check_manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_manifest)

class ChallengeManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(check_manifest.MANIFEST.read_text())

    def test_current_contract_is_valid(self) -> None:
        self.assertEqual(check_manifest.validate_manifest(self.manifest), [])

    def test_difficulty_mutation_is_rejected(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["operations"]["W17"]["cards"][3]["difficulty"] = "Easy"
        errors = check_manifest.validate_manifest(changed)
        self.assertTrue(any("difficulties differ" in error for error in errors), errors)

    def test_completion_cannot_make_product_evidence(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["completion_policy"]["may_create_product_evidence"] = True
        errors = check_manifest.validate_manifest(changed)
        self.assertTrue(any("completion policy" in error for error in errors), errors)

    def test_implemented_operation_rejects_a_retired_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            asset = root / "owned" / "W17" / "live.md"
            asset.parent.mkdir(parents=True)
            asset.write_text("participant asset\n")
            legacy = root / "legacy.py"
            legacy.write_text("OLD_FIXED_RECORD = True\n")
            spec = copy.deepcopy(self.manifest["operations"]["W17"])
            spec.update({
                "status": "implemented",
                "asset_root": "owned/W17",
                "assets": [{
                    "path": "owned/W17/live.md",
                    "owner": "W17",
                    "action": "create",
                    "participant_facing": True,
                }],
                "retirements": [{
                    "mode": "remove_markers",
                    "locations": ["legacy.py"],
                    "markers": ["OLD_FIXED_RECORD"],
                }],
            })
            errors = check_manifest.validate_operation(
                "W17", spec, root, {"planned", "implemented"}
            )
            self.assertTrue(any("retired marker" in error for error in errors), errors)

    def test_implemented_operation_rejects_an_unowned_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            asset_root = root / "owned" / "W17"
            asset_root.mkdir(parents=True)
            (asset_root / "live.md").write_text("participant asset\n")
            (asset_root / "dead-note.md").write_text("stale asset\n")
            spec = copy.deepcopy(self.manifest["operations"]["W17"])
            spec.update({
                "status": "implemented",
                "asset_root": "owned/W17",
                "assets": [{
                    "path": "owned/W17/live.md",
                    "owner": "W17",
                    "action": "create",
                    "participant_facing": True,
                }],
                "retirements": [],
            })
            errors = check_manifest.validate_operation(
                "W17", spec, root, {"planned", "implemented"}
            )
            self.assertTrue(any("unowned asset" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
