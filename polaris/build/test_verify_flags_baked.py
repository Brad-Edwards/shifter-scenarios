"""Tests for the bake-time baked-flag verifier.

Run from the repo root:
    python3 polaris/build/test_verify_flags_baked.py
"""

import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "verify_flags_baked", _HERE / "verify_flags_baked.py"
)
vfb = importlib.util.module_from_spec(_SPEC)
sys.modules["verify_flags_baked"] = vfb
_SPEC.loader.exec_module(vfb)

REPO_PLACEMENT = _HERE.parent / "flags" / "placement.yaml"
CANONICAL_FLAG_6 = "FLAG{c6f8d2b3e91a4507}"


def _load_build_pdfs():
    if importlib.util.find_spec("reportlab") is None:
        raise unittest.SkipTest("reportlab is not installed")
    spec = importlib.util.spec_from_file_location(
        "build_pdfs", _HERE / "A0-boreas-website" / "build_pdfs.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_pdfs"] = module
    spec.loader.exec_module(module)
    return module


class VerifyFlagsBakedTests(unittest.TestCase):
    def _placement(self, root: Path, flags):
        path = root / "placement.yaml"
        rows = ["flags:"]
        for flag in flags:
            rows.extend(
                [
                    f"  - flag_id: {flag['flag_id']}",
                    "    source: value",
                    f"    value: \"{flag['value']}\"",
                    "    host: a0-boreas-web",
                    "    path: /tmp/flag",
                ]
            )
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return path

    def test_static_flag_returns_content(self):
        placement = {
            "flags": [
                {
                    "flag_id": "annual-report-supplier",
                    "source": "value",
                    "value": "FLAG{x}",
                }
            ]
        }
        self.assertEqual(
            vfb.static_flag(placement, "annual-report-supplier"),
            "FLAG{x}",
        )

    def test_static_flag_non_static_raises(self):
        board = {
            "flags": [
                {
                    "flag_id": "annual-report-supplier",
                    "source": "generator",
                    "generator": "build/generate.py",
                }
            ]
        }
        with self.assertRaises(ValueError):
            vfb.static_flag(board, "annual-report-supplier")

    def test_verify_passes_when_flag_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board = self._placement(
                root,
                [{"flag_id": "annual-report-supplier", "value": "FLAG{abc99}"}],
            )
            art = root / "art"
            (art / "internal").mkdir(parents=True)
            (art / "internal" / "rep.txt").write_text(
                "expenses... PO ref: FLAG{abc99}\n", encoding="utf-8"
            )
            misses = vfb.verify(
                board,
                art,
                {"internal/rep.txt": "annual-report-supplier"},
            )
        self.assertEqual(misses, [])

    def test_verify_fails_when_flag_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board = self._placement(
                root,
                [{"flag_id": "annual-report-supplier", "value": "FLAG{abc99}"}],
            )
            art = root / "art"
            (art / "internal").mkdir(parents=True)
            (art / "internal" / "rep.txt").write_text("expenses, no flag here\n", encoding="utf-8")
            capture = io.StringIO()
            original = sys.stdout
            sys.stdout = capture
            try:
                misses = vfb.verify(
                    board,
                    art,
                    {"internal/rep.txt": "annual-report-supplier"},
                )
            finally:
                sys.stdout = original
        self.assertEqual(len(misses), 1)
        self.assertNotIn("FLAG{abc99}", capture.getvalue())

    def test_verify_fails_when_artifact_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board = self._placement(
                root,
                [{"flag_id": "annual-report-supplier", "value": "FLAG{abc99}"}],
            )
            art = root / "art"
            art.mkdir()
            misses = vfb.verify(
                board,
                art,
                {"internal/rep.txt": "annual-report-supplier"},
            )
        self.assertEqual(len(misses), 1)

    def test_verify_real_annual_pdf(self):
        build_pdfs = _load_build_pdfs()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            (root / "internal").mkdir(parents=True)
            build_pdfs.make_annual_report(
                str(root / "internal" / "boreas-annual-2025.pdf"), CANONICAL_FLAG_6
            )
            misses = vfb.verify(
                REPO_PLACEMENT,
                root,
                {"internal/boreas-annual-2025.pdf": "annual-report-supplier"},
            )
        self.assertEqual(misses, [])

    def test_main_returns_zero_on_pass(self):
        build_pdfs = _load_build_pdfs()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            (root / "internal").mkdir(parents=True)
            build_pdfs.make_annual_report(
                str(root / "internal" / "boreas-annual-2025.pdf"), CANONICAL_FLAG_6
            )
            result = vfb.main([str(REPO_PLACEMENT), str(root)])
        self.assertEqual(result, 0)

    def test_main_returns_one_on_miss(self):
        build_pdfs = _load_build_pdfs()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            (root / "internal").mkdir(parents=True)
            build_pdfs.make_annual_report(
                str(root / "internal" / "boreas-annual-2025.pdf"), "FLAG{wrongflag}"
            )
            result = vfb.main([str(REPO_PLACEMENT), str(root)])
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
