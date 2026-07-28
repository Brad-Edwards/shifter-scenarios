"""Tests for the bake-time baked-flag verifier.

Run from the repo root:
    python3 scenarios/polaris/build/test_verify_flags_baked.py
"""

import importlib.util
import json
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

REPO_CHALLENGES = _HERE / "ctfd-challenges.json"
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
    def _board(self, root: Path, challenges):
        path = root / "ctfd-challenges.json"
        path.write_text(json.dumps({"challenges": challenges}), encoding="utf-8")
        return path

    def test_static_flag_returns_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = json.loads(
                self._board(
                    Path(tmp),
                    [{"id": 6, "flags": [{"type": "static", "content": "FLAG{x}"}]}],
                ).read_text(encoding="utf-8")
            )
        self.assertEqual(vfb.static_flag(board, 6), "FLAG{x}")

    def test_static_flag_non_static_raises(self):
        board = {"challenges": [{"id": 6, "flags": [{"type": "regex", "content": "k"}]}]}
        with self.assertRaises(ValueError):
            vfb.static_flag(board, 6)

    def test_verify_passes_when_flag_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board = self._board(
                root, [{"id": 6, "flags": [{"type": "static", "content": "FLAG{abc99}"}]}]
            )
            art = root / "art"
            (art / "internal").mkdir(parents=True)
            (art / "internal" / "rep.txt").write_text(
                "expenses... PO ref: FLAG{abc99}\n", encoding="utf-8"
            )
            misses = vfb.verify(board, art, {"internal/rep.txt": 6})
        self.assertEqual(misses, [])

    def test_verify_fails_when_flag_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board = self._board(
                root, [{"id": 6, "flags": [{"type": "static", "content": "FLAG{abc99}"}]}]
            )
            art = root / "art"
            (art / "internal").mkdir(parents=True)
            (art / "internal" / "rep.txt").write_text("expenses, no flag here\n", encoding="utf-8")
            misses = vfb.verify(board, art, {"internal/rep.txt": 6})
        self.assertEqual(len(misses), 1)

    def test_verify_fails_when_artifact_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board = self._board(
                root, [{"id": 6, "flags": [{"type": "static", "content": "FLAG{abc99}"}]}]
            )
            art = root / "art"
            art.mkdir()
            misses = vfb.verify(board, art, {"internal/rep.txt": 6})
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
                REPO_CHALLENGES, root, {"internal/boreas-annual-2025.pdf": 6}
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
            result = vfb.main([str(REPO_CHALLENGES), str(root)])
        self.assertEqual(result, 0)

    def test_main_returns_one_on_miss(self):
        build_pdfs = _load_build_pdfs()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            (root / "internal").mkdir(parents=True)
            build_pdfs.make_annual_report(
                str(root / "internal" / "boreas-annual-2025.pdf"), "FLAG{wrongflag}"
            )
            result = vfb.main([str(REPO_CHALLENGES), str(root)])
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
