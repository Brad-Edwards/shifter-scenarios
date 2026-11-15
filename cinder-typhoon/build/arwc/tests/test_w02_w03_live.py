#!/usr/bin/env python3
"""Focused native-product acceptance for W02 and W03."""
import unittest

from test_known_solution_live import ARWCKnownSolutionAcceptance


class W02W03Live(unittest.TestCase):
    def test_native_w02_w03_path(self) -> None:
        ARWCKnownSolutionAcceptance.evidence = {}
        ARWCKnownSolutionAcceptance.setUpClass()
        case = ARWCKnownSolutionAcceptance(methodName="test_w02_asset_association")
        case.test_w01_customer_copy()
        case.test_w02_asset_association()
        case.test_w03_annex_reference()


if __name__ == "__main__":
    unittest.main(verbosity=2)
