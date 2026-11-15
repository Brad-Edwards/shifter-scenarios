#!/usr/bin/env python3
"""Focused native-product acceptance for W01."""
import unittest

from test_known_solution_live import ARWCKnownSolutionAcceptance


class W01Live(unittest.TestCase):
    def test_native_w01_path(self) -> None:
        ARWCKnownSolutionAcceptance.evidence = {}
        ARWCKnownSolutionAcceptance.setUpClass()
        case = ARWCKnownSolutionAcceptance(methodName="test_w01_customer_copy")
        case.test_w01_customer_copy()


if __name__ == "__main__":
    unittest.main(verbosity=2)
