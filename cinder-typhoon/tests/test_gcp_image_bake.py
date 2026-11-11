"""Safety contracts for GCP image deployment and baking."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GcpImageBakeTests(unittest.TestCase):
    def test_deploy_archives_exclude_local_bake_receipts(self) -> None:
        exclusion = "--exclude='build/gcp-images/.operator'"
        for phase in ("training", "keplerops", "arwc"):
            with self.subTest(phase=phase):
                deploy = (
                    ROOT / "build" / phase / "gcp" / "deploy.sh"
                ).read_text(encoding="utf-8")
                self.assertIn(exclusion, deploy)


if __name__ == "__main__":
    unittest.main()
