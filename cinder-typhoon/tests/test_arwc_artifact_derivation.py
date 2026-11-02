from __future__ import annotations

import ast
import copy
import importlib.util
import inspect
import json
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


def schedule_window() -> dict[str, object]:
    return {
        "schema": "arwc.schedule-window/v1",
        "checkpoint": "REH-SCHED-33",
        "interval_seconds": 300,
        "interval_count": 12,
        "demand_m3s": [0.45, 0.50, 0.55, 0.60, 0.65, 0.70,
                       0.70, 0.65, 0.60, 0.55, 0.50, 0.45],
        "initial_buffer_m3": 180.0,
        "state_bounds_m3": {"min": 120.0, "max": 240.0},
        "terminal_bounds_m3": {"min": 160.0, "max": 200.0},
        "volume_objective_ml": {"min": 0.78, "max": 0.84},
        "ramp_bound_m3s": 0.1,
        "release_bounds_m3s": {"min": 0.0, "max": 0.8},
        "supply_bounds_m3s": {"min": 0.0, "max": 0.5},
        "policy_format": "ARWC-POL1",
        "request_schema": {
            "required": [
                "checkpoint", "interval_seconds", "demand_m3s",
                "reservoir_release_m3s", "alternate_supply_m3s",
            ],
            "series_length": 12,
            "number_type": "finite-real",
        },
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

    def test_w33_and_w34_have_no_embedded_winning_schedule(self) -> None:
        for method in ("test_w33_forecast_scheduling", "test_w34_reporting_checkpoint"):
            source = ast.unparse(method_node(method))
            with self.subTest(method=method):
                self.assertNotIn("reference_release_m3s", source)
                self.assertNotIn("reference_alternate_m3s", source)
                lists = [
                    node for node in ast.walk(method_node(method))
                    if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) == 12
                ]
                self.assertEqual(lists, [])

    def test_derivation_failures_stop_without_fallbacks(self) -> None:
        with self.assertRaisesRegex(AssertionError, "W22 reviewer derivation failed"):
            known_solution.w22_recover_reviewer(b"not-a-helper", "listed-review")
        with self.assertRaisesRegex(AssertionError, "W23 estimator derivation failed"):
            known_solution.w23_analyze_reproducer("malformed", {}, "Cairn Reach")
        with self.assertRaisesRegex(AssertionError, "W24 selector derivation failed"):
            known_solution.w24_selector_from_disassembly("", [])

    def test_three_distinct_schedules_are_derived_from_the_contract(self) -> None:
        window = schedule_window()
        schedules = known_solution.w33_derive_schedules(window)
        self.assertEqual(len(schedules), 3)
        self.assertEqual(len({json.dumps(value, sort_keys=True) for value in schedules}), 3)
        for schedule in schedules:
            result = known_solution.w33_validate_schedule(window, schedule)
            self.assertTrue(
                window["volume_objective_ml"]["min"]
                <= result["reservoir_volume_ml"]
                <= window["volume_objective_ml"]["max"]
            )

    def test_schedule_boundary_failures_are_specific(self) -> None:
        window = schedule_window()
        schedule = known_solution.w33_derive_schedules(window)[1]
        cases: list[tuple[str, dict[str, object], str]] = []

        outside_supply = copy.deepcopy(schedule)
        outside_supply["alternate_supply_m3s"][0] = 0.51
        cases.append(("supply", outside_supply, "alternate supply is outside"))

        ramp = copy.deepcopy(schedule)
        ramp["reservoir_release_m3s"][1] = 0.8
        cases.append(("ramp", ramp, "ramp bound exceeded"))

        state = copy.deepcopy(schedule)
        state["alternate_supply_m3s"] = [value + 0.02 for value in state["alternate_supply_m3s"]]
        cases.append(("state", state, "operating state bound exceeded"))

        volume = copy.deepcopy(schedule)
        volume["reservoir_release_m3s"] = [value - 0.02 for value in volume["reservoir_release_m3s"]]
        volume["alternate_supply_m3s"] = [value + 0.02 for value in volume["alternate_supply_m3s"]]
        cases.append(("volume", volume, "volume objective missed"))

        for name, candidate, message in cases:
            with self.subTest(boundary=name):
                with self.assertRaisesRegex(AssertionError, message):
                    known_solution.w33_validate_schedule(window, candidate)

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
