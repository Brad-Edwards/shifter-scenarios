"""Tests for the A0 Boreas PDF generator.

Run from the repo root:
    python3 polaris/build/A0-boreas-website/test_build_pdfs.py
"""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REPO_PLACEMENT = _HERE.parents[1] / "flags" / "placement.yaml"
CANONICAL_FLAG_6 = "FLAG{c6f8d2b3e91a4507}"
CANONICAL_FLAG_2 = "FLAG{d4e7b1f283a6c950}"


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
    def _write_placement(self, root: Path, body: str):
        path = root / "placement.yaml"
        path.write_text(body, encoding="utf-8")
        return path

    def test_flag_for_returns_static_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_placement(
                Path(tmp),
                """
flags:
  - flag_id: annual-report-supplier
    source: value
    value: FLAG{abc12345}
""",
            )
            result = build_pdfs.flag_for("annual-report-supplier", path)
        self.assertEqual(result, "FLAG{abc12345}")

    def test_flag_for_missing_flag_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_placement(
                Path(tmp),
                """
flags:
  - flag_id: company-registration
    source: value
    value: FLAG{abc12345}
""",
            )
            with self.assertRaisesRegex(ValueError, "annual-report-supplier"):
                build_pdfs.flag_for("annual-report-supplier", path)

    def test_flag_for_non_value_source_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_placement(
                Path(tmp),
                """
flags:
  - flag_id: annual-report-supplier
    source: generator
    generator: build/make_flag.py
""",
            )
            with self.assertRaisesRegex(ValueError, "value"):
                build_pdfs.flag_for("annual-report-supplier", path)

    def test_flag_for_duplicate_flag_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_placement(
                Path(tmp),
                """
flags:
  - flag_id: annual-report-supplier
    source: value
    value: FLAG{aaaaaaaa}
  - flag_id: annual-report-supplier
    source: value
    value: FLAG{bbbbbbbb}
""",
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                build_pdfs.flag_for("annual-report-supplier", path)

    def test_flag_for_duplicate_yaml_key_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_placement(
                Path(tmp),
                """
flags:
  - flag_id: annual-report-supplier
    source: value
    value: FLAG{aaaaaaaa}
    value: FLAG{bbbbbbbb}
""",
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                build_pdfs.flag_for("annual-report-supplier", path)

    def test_repo_placement_supplies_canonical_flag_6(self):
        self.assertEqual(
            build_pdfs.flag_for("annual-report-supplier", REPO_PLACEMENT),
            CANONICAL_FLAG_6,
        )

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
            build_pdfs.main([str(root), str(REPO_PLACEMENT)])
            text = extract_text(str(root / "internal" / "boreas-annual-2025.pdf"))
        self.assertIn(CANONICAL_FLAG_6, text)

    def test_main_sources_org_chart_metadata_flag_from_placement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            placement = self._write_placement(
                root,
                """
flags:
  - flag_id: employee-directory
    source: value
    value: FLAG{bbbbbbbbbbbbbbbb}
  - flag_id: annual-report-supplier
    source: value
    value: FLAG{aaaaaaaaaaaaaaaa}
""",
            )
            build_pdfs.main([str(root), str(placement)])
            raw = (root / "internal" / "org_chart.pdf").read_bytes()

        self.assertIn(b"FLAG{bbbbbbbbbbbbbbbb}", raw)
        self.assertNotIn(CANONICAL_FLAG_2.encode(), raw)


if __name__ == "__main__":
    unittest.main()
