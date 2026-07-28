"""Tests for the A0 Boreas PDF generator.

Run from the repo root:
    python3 scenarios/polaris/build/A0-boreas-website/test_build_pdfs.py
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REPO_CHALLENGES = _HERE.parent / "ctfd-challenges.json"
CANONICAL_FLAG_6 = "FLAG{c6f8d2b3e91a4507}"


PDF_DEPS_AVAILABLE = (
    importlib.util.find_spec("reportlab") is not None
    and importlib.util.find_spec("pdfminer") is not None
)

if PDF_DEPS_AVAILABLE:
    from pdfminer.high_level import extract_text

    _SPEC = importlib.util.spec_from_file_location("build_pdfs", _HERE / "build_pdfs.py")
    build_pdfs = importlib.util.module_from_spec(_SPEC)
    sys.modules["build_pdfs"] = build_pdfs
    _SPEC.loader.exec_module(build_pdfs)
else:
    extract_text = None
    build_pdfs = None


@unittest.skipUnless(PDF_DEPS_AVAILABLE, "reportlab/pdfminer are not installed")
class BuildPdfsTests(unittest.TestCase):
    def _write_challenges(self, root: Path, challenges):
        path = root / "ctfd-challenges.json"
        path.write_text(json.dumps({"challenges": challenges}), encoding="utf-8")
        return path

    def test_flag_for_returns_static_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_challenges(
                Path(tmp),
                [{"id": 6, "flags": [{"type": "static", "content": "FLAG{abc12345}"}]}],
            )
            result = build_pdfs.flag_for(6, path)
        self.assertEqual(result, "FLAG{abc12345}")

    def test_flag_for_missing_challenge_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_challenges(
                Path(tmp),
                [{"id": 5, "flags": [{"type": "static", "content": "FLAG{x}"}]}],
            )
            with self.assertRaisesRegex(ValueError, "6"):
                build_pdfs.flag_for(6, path)

    def test_flag_for_non_static_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_challenges(
                Path(tmp),
                [{"id": 6, "flags": [{"type": "regex", "content": "(?i)kursk"}]}],
            )
            with self.assertRaisesRegex(ValueError, "static"):
                build_pdfs.flag_for(6, path)

    def test_flag_for_duplicate_challenge_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_challenges(
                Path(tmp),
                [
                    {"id": 6, "flags": [{"type": "static", "content": "FLAG{a}"}]},
                    {"id": 6, "flags": [{"type": "static", "content": "FLAG{b}"}]},
                ],
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                build_pdfs.flag_for(6, path)

    def test_flag_for_multiple_flags_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_challenges(
                Path(tmp),
                [
                    {
                        "id": 6,
                        "flags": [
                            {"type": "static", "content": "FLAG{a}"},
                            {"type": "static", "content": "FLAG{b}"},
                        ],
                    }
                ],
            )
            with self.assertRaises(ValueError):
                build_pdfs.flag_for(6, path)

    def test_repo_challenges_supplies_canonical_flag_6(self):
        self.assertEqual(build_pdfs.flag_for(6, REPO_CHALLENGES), CANONICAL_FLAG_6)

    def test_annual_report_embeds_flag_6(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "boreas-annual-2025.pdf"
            build_pdfs.make_annual_report(str(out), CANONICAL_FLAG_6)
            text = extract_text(str(out))
        self.assertIn("Kursk Heavy Industries", text)
        self.assertIn(CANONICAL_FLAG_6, text)

    def test_main_renders_annual_report_with_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_pdfs.main([str(root), str(REPO_CHALLENGES)])
            text = extract_text(str(root / "internal" / "boreas-annual-2025.pdf"))
        self.assertIn(CANONICAL_FLAG_6, text)


if __name__ == "__main__":
    unittest.main()
