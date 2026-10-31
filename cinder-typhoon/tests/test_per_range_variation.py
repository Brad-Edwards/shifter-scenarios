"""Static tests for the per-range seed provisioning system."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEED_SCRIPT = ROOT / "build" / "keplerops" / "provision-seed.py"
SUPPORT_CONFIG = ROOT / "assets" / "keplerops" / "opening" / "k-support" / "support-service.json"


def load_seed_module():
    spec = importlib.util.spec_from_file_location("provision_seed", SEED_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SeedVariationTests(unittest.TestCase):

    def test_different_seeds_produce_different_credentials(self) -> None:
        mod = load_seed_module()
        seeds = [
            "cinder-keplerops-range-001-2026-11-01",
            "cinder-keplerops-range-002-2026-11-01",
            "cinder-keplerops-range-003-2026-11-01",
        ]
        seen_rowan = set()
        seen_talia = set()
        seen_git = set()
        for seed in seeds:
            with self.subTest(seed=seed):
                rowan = mod.derive(seed, "keplerops.support.rowan-session")
                talia = mod.derive(seed, "keplerops.support.talia-session")
                git = mod.derive(seed, "keplerops.git.rowan-secret", length=12)
                seen_rowan.add(rowan)
                seen_talia.add(talia)
                seen_git.add(git)
        self.assertEqual(len(seen_rowan), len(seeds), "rowan sessions are not unique across seeds")
        self.assertEqual(len(seen_talia), len(seeds), "talia sessions are not unique across seeds")
        self.assertEqual(len(seen_git), len(seeds), "git secrets are not unique across seeds")

    def test_same_seed_produces_same_credentials(self) -> None:
        mod = load_seed_module()
        seed = "cinder-keplerops-deterministic-test"
        a = mod.derive(seed, "keplerops.support.rowan-session")
        b = mod.derive(seed, "keplerops.support.rowan-session")
        self.assertEqual(a, b)

    def test_provision_script_runs_and_updates_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SEED_SCRIPT),
                 "--seed", "cinder-keplerops-test-seed-01",
                 "--support-config", str(SUPPORT_CONFIG),
                 "--output-dir", tmp],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            out_config = json.loads((pathlib.Path(tmp) / "support-service.json").read_text())
            self.assertIn("reviewer_session_id", out_config)
            self.assertNotEqual(out_config["reviewer_session_id"],
                                "ksess_talia_review_9Kw4Pn7R",
                                "seed-derived session must differ from the default")
            self.assertIn("ksess_talia_review_", out_config["reviewer_session_id"])
            manifest = json.loads((pathlib.Path(tmp) / "seed-manifest.json").read_text())
            self.assertEqual(manifest["schema"], "fieldkest.seed-manifest/v1")

    def test_three_seeds_all_produce_schema_valid_support_configs(self) -> None:
        mod = load_seed_module()
        seeds = [
            "cinder-keplerops-range-A-2026-11",
            "cinder-keplerops-range-B-2026-11",
            "cinder-keplerops-range-C-2026-11",
        ]
        base_config = json.loads(SUPPORT_CONFIG.read_text())
        for seed in seeds:
            with self.subTest(seed=seed):
                with tempfile.TemporaryDirectory() as tmp:
                    result = subprocess.run(
                        [sys.executable, str(SEED_SCRIPT),
                         "--seed", seed,
                         "--support-config", str(SUPPORT_CONFIG),
                         "--output-dir", tmp],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    config = json.loads((pathlib.Path(tmp) / "support-service.json").read_text())
                    self.assertIn("sessions", config)
                    self.assertTrue(config["sessions"])
                    self.assertIn("reviewer_session_id", config)

    def test_support_service_json_has_reviewer_session_id(self) -> None:
        config = json.loads(SUPPORT_CONFIG.read_text())
        self.assertIn("reviewer_session_id", config,
                      "support-service.json must declare reviewer_session_id for per-range variation")


if __name__ == "__main__":
    unittest.main()
