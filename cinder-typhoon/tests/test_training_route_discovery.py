"""Static regressions for Training known-solution route discovery."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "build" / "training" / "tests" / "test_known_solution_live.py"
REQUEST_FUNCTIONS = {"request", "get_text", "get_json"}


def function_name(call: ast.Call) -> str | None:
    return call.func.id if isinstance(call.func, ast.Name) else None


def direct_request_route_literals(source: str) -> list[tuple[int, str]]:
    tree = ast.parse(source)
    findings: list[tuple[int, str]] = []
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if function_name(call) not in REQUEST_FUNCTIONS or not call.args:
            continue
        for node in ast.walk(call.args[0]):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and "/api/" in node.value:
                findings.append((node.lineno, node.value))
    return findings


class TrainingRouteDiscoveryTests(unittest.TestCase):
    def test_known_solution_has_no_direct_request_route_literals(self) -> None:
        source = SUITE.read_text(encoding="utf-8")
        self.assertEqual(direct_request_route_literals(source), [])
        all_api_literals = [
            (node.lineno, node.value)
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "/api/" in node.value
        ]
        self.assertEqual(all_api_literals, [])

    def test_regression_detects_nested_and_direct_literals(self) -> None:
        source = """
request("http://desk.training/api/direct")
get_json(urljoin(base, "/api/nested"))
"""
        self.assertEqual(
            [value for _, value in direct_request_route_literals(source)],
            ["http://desk.training/api/direct", "/api/nested"],
        )


if __name__ == "__main__":
    unittest.main()
