import copy
import unittest
from validate import load_compose, validate


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.document = load_compose()

    def test_contract(self):
        validate(self.document)

    def test_backend_cannot_join_supervisory(self):
        changed = copy.deepcopy(self.document)
        changed["services"]["backend"]["networks"].append("supervisory")
        with self.assertRaises(AssertionError):
            validate(changed)

    def test_edge_cannot_forward(self):
        changed = copy.deepcopy(self.document)
        changed["services"]["edge"]["sysctls"] = {"net.ipv4.ip_forward": "1"}
        with self.assertRaises(AssertionError):
            validate(changed)

    def test_backend_cannot_publish_host_port(self):
        changed = copy.deepcopy(self.document)
        changed["services"]["backend"]["ports"] = ["8000:8000"]
        with self.assertRaises(AssertionError):
            validate(changed)


if __name__ == "__main__":
    unittest.main()
