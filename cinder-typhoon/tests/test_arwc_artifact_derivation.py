from __future__ import annotations

import ast
import importlib.util
import inspect
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "build" / "arwc" / "tests" / "test_known_solution_live.py"
SPEC = importlib.util.spec_from_file_location("arwc_known_solution_derivation", SUITE)
assert SPEC and SPEC.loader
known_solution = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = known_solution
SPEC.loader.exec_module(known_solution)


def method_node(name: str) -> ast.FunctionDef:
    tree = ast.parse(SUITE.read_text(encoding="utf-8"), filename=str(SUITE))
    matches = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one {name} method, found {len(matches)}")
    return matches[0]


def constants(name: str) -> set[object]:
    return {
        node.value for node in ast.walk(method_node(name))
        if isinstance(node, ast.Constant)
    }


class ARWCArtifactDerivationTests(unittest.TestCase):
    def test_removed_answers_are_absent_from_known_solution_methods(self) -> None:
        forbidden = {
            "test_w22_sealed_viewer": {"elias.vorn-review"},
            "test_w23_estimator_heap": {
                "PROBE-CRR-23", "ALLOC-CASE-CRR-33",
                1129468466, 12.4, 13.4, 40, 48, 64,
            },
            "test_w24_crypto_oracle": {
                0x9E3779B97F4A7C15, 0xBF58476D1CE4E5B9, 23, 17, 26,
            },
            "test_w34_reporting_checkpoint": {
                "REH-REPORT-34", "PLAN-CONSUMER-R8", "VIEW-CRR-34",
                "ALLOC-HOLD-R3", "ALLOC-EXPAND-R2", 1.2,
            },
        }
        for method, answers in forbidden.items():
            with self.subTest(method=method):
                self.assertTrue(answers.isdisjoint(constants(method)))

    def test_w34_has_no_embedded_winning_schedule(self) -> None:
        source = ast.unparse(method_node("test_w34_reporting_checkpoint"))
        self.assertNotIn("reference_release_m3s", source)
        self.assertNotIn("reference_alternate_m3s", source)
        lists = [
            node for node in ast.walk(method_node("test_w34_reporting_checkpoint"))
            if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) == 12
        ]
        self.assertEqual(lists, [])

    def test_w33_uses_native_product_assets_not_known_solution_routes(self) -> None:
        w33 = ROOT / "build" / "arwc-ot" / "challenges" / "W33"
        for relative in (
            "participant/operating-window.csv",
            "participant/schedule-template.json",
            "participant/scheduling-brief.md",
            "participant/run-schedule.py",
            "product_snapshot.sql",
            "corporate_snapshot.sql",
            "check_evidence.py",
        ):
            self.assertTrue((w33 / relative).is_file(), relative)
        self.assertNotIn("test_w33_forecast_scheduling", SUITE.read_text())

    def test_derivation_failures_stop_without_fallbacks(self) -> None:
        with self.assertRaisesRegex(AssertionError, "W22 reviewer derivation failed"):
            known_solution.w22_recover_reviewer(b"not-a-helper", "listed-review")
        with self.assertRaisesRegex(AssertionError, "W23 estimator derivation failed"):
            known_solution.w23_analyze_reproducer("malformed", {}, "Cairn Reach")
        with self.assertRaisesRegex(AssertionError, "W24 selector derivation failed"):
            known_solution.w24_selector_from_disassembly("", [])

    def test_selector_model_is_unique_against_independent_cases(self) -> None:
        disassembly = """
            movabs $0x9e3779b97f4a7c15,%rax
            movabs $0xbf58476d1ce4e5b9,%rdx
            shl $0x17,%rdi
            shr $0x11,%rdi
            shr $0x1a,%rax
            shr $0x3f,%rsi
        """
        mask = (1 << 64) - 1

        def implementation(request_id: int, epoch_bucket: int) -> int:
            x = (request_id ^ 0x9E3779B97F4A7C15) & mask
            y = (epoch_bucket ^ 0xBF58476D1CE4E5B9) & mask
            x = (x ^ ((x << 23) & mask)) & mask
            return ((x ^ y ^ (x >> 17) ^ (y >> 26)) + y) & mask

        inputs = [
            (0x2400000000000001, 0),
            (0x2400000000000042, 1770000039),
            (0x2400000012345678, 1770000040),
            (0x2400ABCDEF000001, 1770000042),
            (0x24FEDCBA98765432, 1770000043),
        ]
        cases = [
            {"request_id": f"{request_id:016x}", "epoch_bucket": bucket,
             "rotation": implementation(request_id, bucket) & 3}
            for request_id, bucket in inputs
        ]
        selector, model = known_solution.w24_selector_from_disassembly(disassembly, cases)
        self.assertEqual(model["epoch_shift"], 26)
        for request_id, bucket in inputs:
            self.assertEqual(selector(request_id, bucket), implementation(request_id, bucket))


if __name__ == "__main__":
    unittest.main()
